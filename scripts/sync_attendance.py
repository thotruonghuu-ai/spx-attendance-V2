"""
SPX Attendance → Google Sheet | sync_attendance.py
Chạy trên GitHub Actions - không cần máy tính bật
Logic ghi: append xuống dưới tiêu đề (hàng 1), không đè dữ liệu cũ.
Ngày đã tồn tại thì bỏ qua (không ghi đè).
Hỗ trợ: 1 ngày cụ thể, khoảng ngày (from→to), hoặc N-1 tự động.
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ============================================================
# CẤU HÌNH
# ============================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
ICT = timezone(timedelta(hours=7))

# API đúng từ Network capture (GET, wfm/admin path)
SPX_API_URL = "https://spx.shopee.vn/api/wfm/admin/attendance/clock/statistic_data_list"
PAGE_SIZE    = 100  # Tăng để giảm số lần gọi API

# ============================================================
# BƯỚC 1: LẤY DATA TỪ SPX API
# ============================================================
def fetch_spx_data(cookie: str, target_date: str) -> list[dict]:
    """Lấy toàn bộ bản ghi chấm công cho target_date (YYYY-MM-DD)."""
    headers = {
        "cookie": cookie,
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9,vi;q=0.8",
        "app": "FMS Portal",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "referer": "https://spx.shopee.vn/",
    }

    date_obj  = datetime.strptime(target_date, "%Y-%m-%d")
    ts_start  = int(datetime(date_obj.year, date_obj.month, date_obj.day,
                              0, 0, 0, tzinfo=ICT).timestamp())
    ts_end    = int(datetime(date_obj.year, date_obj.month, date_obj.day,
                              23, 59, 59, tzinfo=ICT).timestamp())

    all_records: list[dict] = []
    page = 1

    while True:
        params = {
            "pageno":     page,
            "count":      PAGE_SIZE,
            "staff_type": 2,
            "start_time": ts_start,
            "end_time":   ts_end,
        }
        print(f"  → Gọi API trang {page} ...")
        resp = requests.get(SPX_API_URL, params=params, headers=headers, timeout=30)

        # Debug: in ra status và response nếu lỗi
        print(f"     HTTP {resp.status_code}")
        if resp.status_code != 200:
            resp.raise_for_status()

        body = resp.json()

        # Kiểm tra session hết hạn
        if body.get("code") in (401, 403) or "login" in str(body).lower():
            raise RuntimeError(
                "Session SPX hết hạn! Lấy lại cookie và cập nhật GitHub Secret SPX_COOKIE."
            )

        # Thử nhiều cấu trúc response khác nhau
        data = body.get("data") or body.get("result") or body.get("response") or {}
        if isinstance(data, list):
            items = data
            total = len(data)
        else:
            items = (data.get("list") or data.get("items") or
                     data.get("records") or data.get("data") or [])
            total = (data.get("total") or data.get("total_count") or
                     data.get("count") or body.get("total") or 0)

        # Nếu vẫn rỗng, thử lấy thẳng từ body
        if not items and isinstance(body.get("list"), list):
            items = body["list"]
            total = body.get("total", len(items))

        all_records.extend(items)
        fetched = len(all_records)
        print(f"     Trang {page}: {len(items)} bản ghi | Tổng đã lấy: {fetched}/{total}")

        if not items or (total > 0 and fetched >= total):
            break
        page += 1
        time.sleep(0.3)

    print(f"  ✅ Lấy được {len(all_records)} bản ghi từ SPX")
    return all_records

# ============================================================
# BƯỚC 2: ĐỌC SHEET ĐỂ XÁC ĐỊNH HÀNG TIẾP THEO + NGÀY ĐÃ CÓ
# ============================================================
def get_sheet_state(service, spreadsheet_id: str, sheet_name: str):
    """
    Trả về:
      - next_row (int): hàng tiếp theo để ghi (sau hàng cuối có dữ liệu)
      - existing_dates (set): tập hợp các ngày (chuỗi YYYY-MM-DD) đã có trong sheet
    Hàng 1 là tiêu đề → luôn bắt đầu ghi từ hàng 2 trở xuống.
    """
    range_check = f"{sheet_name}!A:A"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_check)
        .execute()
    )
    values = result.get("values", [])

    existing_dates = set()
    next_row = 2  # Mặc định bắt đầu từ hàng 2 nếu sheet chỉ có tiêu đề

    for i, row in enumerate(values):
        if i == 0:
            # Hàng đầu là tiêu đề, bỏ qua
            continue
        cell = row[0].strip() if row else ""
        if cell:
            # Chuẩn hóa về YYYY-MM-DD
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    d = datetime.strptime(cell, fmt)
                    existing_dates.add(d.strftime("%Y-%m-%d"))
                    break
                except ValueError:
                    pass
            next_row = i + 2  # i là 0-based, hàng Google Sheets là 1-based, +1 cho tiêu đề

    print(f"  📋 Sheet hiện có {len(existing_dates)} ngày dữ liệu | Ghi từ hàng: {next_row}")
    return next_row, existing_dates

# ============================================================
# BƯỚC 3: CHUYỂN ĐỔI BẢN GHI SPX → HÀNG SHEET
# ============================================================
def record_to_row(rec: dict, target_date: str) -> list:
    """Chuyển 1 bản ghi SPX thành 1 hàng cho Google Sheet.
    Cột khớp với tiêu đề sheet thực tế (ảnh):
    A=Date, B=Ops ID, C=Ops Name, D=Staff Email, E=Profile Station,
    F=Event Station, G=Agency, H=Contract Type, I=Department, J=Slot(Shift),
    K=Clock-in Status, L=Clock-out Status, M=Clock-in Time, N=Clock-out Time,
    O=Clock-in Date, P=Clock-out Date, Q=Planned Hours, R=Actual Hours,
    S=Fulfill Working Hours, T=Break Time, U=OT Applied, V=OT Worked,
    W=Out of Event, X=Sick/Leave, Y=Event ID, Z=Clock-in Match Type,
    AA=Clock-out Match Type
    """

    def safe(val, default=""):
        if val in (None, ""):
            return default
        return str(val) if not isinstance(val, str) else val

    def safe_num(val, default=""):
        if val in (None, ""):
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    row = [
        target_date,                                              # A: Date
        safe(rec.get("biz_staff_id")),                           # B: Ops ID
        safe(rec.get("staff_name")),                             # C: Ops Name
        safe(rec.get("staff_email")),                            # D: Staff Email
        safe(rec.get("profile_station_name")),                   # E: Profile Station
        safe(rec.get("event_station_name")),                     # F: Event Station
        safe(rec.get("agency")),                                 # G: Agency
        safe(rec.get("contract_type")),                          # H: Contract Type
        safe(rec.get("department_name")),                        # I: Department
        safe(rec.get("slot_code")),                              # J: Slot (Shift)
        safe(rec.get("clock_in_status_name")),                   # K: Clock-in Status
        safe(rec.get("clock_out_status_name")),                  # L: Clock-out Status
        safe(rec.get("clock_in_time_str")),                      # M: Clock-in Time
        safe(rec.get("clock_out_time_str")),                     # N: Clock-out Time
        safe(rec.get("clock_in_date_str")),                      # O: Clock-in Date
        safe(rec.get("clock_out_date_str")),                     # P: Clock-out Date
        safe_num(rec.get("planned_hours")),                      # Q: Planned Hours
        safe_num(rec.get("actual_hours")),                       # R: Actual Hours
        safe(rec.get("fulfill_working_hours")),                  # S: Fulfill Working Hours
        safe_num(rec.get("break_time")),                         # T: Break Time
        safe(rec.get("ot_applied")),                             # U: OT Applied
        safe_num(rec.get("ot_worked")),                          # V: OT Worked
        safe(rec.get("out_of_event_name") or rec.get("out_of_event")),  # W: Out of Event
        safe(rec.get("sick_or_leave")),                          # X: Sick/Leave
        safe(rec.get("event_id")),                               # Y: Event ID
        safe(rec.get("clock_in_matching_type_str")),             # Z: Clock-in Match Type
        safe(rec.get("clock_out_matching_type_str")),            # AA: Clock-out Match Type
    ]
    return row

# ============================================================
# BƯỚC 4: GHI VÀO GOOGLE SHEET (APPEND XUỐNG DƯỚI)
# ============================================================
def append_rows_to_sheet(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[list],
    start_row: int,
):
    """
    Ghi rows vào sheet bắt đầu từ start_row.
    Không đụng đến hàng 1 (tiêu đề).
    """
    if not rows:
        print("  ⚠ Không có hàng nào để ghi.")
        return

    range_start = f"{sheet_name}!A{start_row}"
    body = {"values": rows}

    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_start,
            valueInputOption="USER_ENTERED",
            body=body,
        )
        .execute()
    )
    updated = result.get("updatedRows", len(rows))
    print(f"  ✅ Đã ghi {updated} hàng vào sheet (từ hàng {start_row})")

# ============================================================
# MAIN
# ============================================================
def build_date_list(date_from: str, date_to: str) -> list[str]:
    """Tạo danh sách ngày từ date_from đến date_to (bao gồm cả 2 đầu)."""
    d_from = datetime.strptime(date_from, "%Y-%m-%d")
    d_to   = datetime.strptime(date_to,   "%Y-%m-%d")
    dates  = []
    cur = d_from
    while cur <= d_to:
        dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return dates


def main():
    # --- Đọc biến môi trường ---
    cookie         = os.environ["SPX_COOKIE"]
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet_name     = os.environ.get("SHEET_NAME", "Att Reco")
    gcp_json       = os.environ["GCP_SERVICE_ACCOUNT"]
    date_from      = os.environ.get("DATE_FROM",  "").strip()
    date_to        = os.environ.get("DATE_TO",    "").strip()
    date_override  = os.environ.get("DATE_OVERRIDE", "").strip()

    # --- Xác định danh sách ngày cần quét ---
    today_ict = datetime.now(ICT)
    yesterday = (today_ict - timedelta(days=1)).strftime("%Y-%m-%d")

    if date_from and date_to:
        # Chế độ khoảng ngày
        target_dates = build_date_list(date_from, date_to)
        mode_label = f"Khoảng ngày: {date_from} → {date_to} ({len(target_dates)} ngày)"
    elif date_override:
        # Chế độ 1 ngày cụ thể
        target_dates = [date_override]
        mode_label = f"Ngày cụ thể: {date_override}"
    else:
        # Chế độ tự động N-1
        target_dates = [yesterday]
        mode_label = f"Tự động N-1: {yesterday}"

    print("=" * 60)
    print(f"SPX Attendance Sync  |  {mode_label}")
    print(f"Sheet: {sheet_name}")
    print("=" * 60)

    # --- Xác thực Google Sheets ---
    print("\n[1/3] Xác thực Google Sheets API...")
    creds_info = json.loads(gcp_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    print("  ✅ Xác thực thành công")

    # --- Đọc trạng thái sheet 1 lần ---
    print("\n[2/3] Đọc trạng thái Google Sheet...")
    next_row, existing_dates = get_sheet_state(service, spreadsheet_id, sheet_name)

    # --- Lặp qua từng ngày ---
    print(f"\n[3/3] Bắt đầu đồng bộ {len(target_dates)} ngày...")
    total_written = 0
    skipped = []

    for i, target_date in enumerate(target_dates, 1):
        print(f"\n--- Ngày {i}/{len(target_dates)}: {target_date} ---")

        if target_date in existing_dates:
            print(f"  ⚠ Đã có trong sheet, bỏ qua.")
            skipped.append(target_date)
            continue

        try:
            records = fetch_spx_data(cookie, target_date)
        except RuntimeError as e:
            print(f"  ❌ Lỗi session: {e}")
            raise
        except Exception as e:
            print(f"  ❌ Lỗi khi lấy data ngày {target_date}: {e}")
            print(f"  → Bỏ qua ngày này, tiếp tục...")
            continue

        if not records:
            print(f"  ⚠ Không có bản ghi nào.")
            continue

        rows = [record_to_row(rec, target_date) for rec in records]
        append_rows_to_sheet(service, spreadsheet_id, sheet_name, rows, next_row)
        existing_dates.add(target_date)
        next_row += len(rows)
        total_written += len(rows)

        if i < len(target_dates):
            time.sleep(1)  # Tránh rate limit khi chạy nhiều ngày

    print("\n" + "=" * 60)
    print(f"✅ HOÀN THÀNH: Đã ghi {total_written} bản ghi")
    if skipped:
        print(f"   Bỏ qua {len(skipped)} ngày đã có: {', '.join(skipped)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
