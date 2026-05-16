"""
SPX Attendance → Google Sheet  |  sync_attendance.py
Chạy trên GitHub Actions - không cần máy tính bật
"""

import os
import json
import time
import math
import requests
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ══════════════════════════════════════════════════════════════
#  CẤU HÌNH - đọc từ GitHub Secrets
# ══════════════════════════════════════════════════════════════
SPX_COOKIE        = os.environ["SPX_COOKIE"]         # Cookie SPX đầy đủ
SPREADSHEET_ID    = os.environ["SPREADSHEET_ID"]      # ID Google Sheet
SHEET_NAME        = os.environ.get("SHEET_NAME", "Att Reco")
GCP_SA_KEY        = os.environ["GCP_SERVICE_ACCOUNT"] # JSON service account (string)

# Lấy ngày hôm qua (N-1) theo giờ VN
VN_TZ   = timezone(timedelta(hours=7))
TODAY   = datetime.now(VN_TZ)
TARGET  = TODAY - timedelta(days=1)          # N-1
DATE_STR = TARGET.strftime("%Y-%m-%d")       # "2026-05-15"

SPX_BASE = "https://spx.shopee.vn"
API_PATH = "/api/wfm/admin/attendance/clock/statistic_data_list"

# Header row khớp với sheet Att Reco của bạn
HEADERS = [
    "Date", "Ops ID", "Ops Name", "Staff Email",
    "Profile Station", "Event Station", "Agency",
    "Contract Type", "Department", "Slot (Shift)",
    "Clock-in Status", "Clock-out Status",
    "Clock-in Time", "Clock-out Time",
    "Clock-in Date", "Clock-out Date",
    "Planned Hours", "Actual Hours", "Fulfill Working Hours?",
    "Break Time", "OT Applied", "OT Worked",
    "Out of Event", "Sick/Leave", "Event ID",
    "Clock-in Match Type", "Clock-out Match Type"
]

# ══════════════════════════════════════════════════════════════
#  BƯỚC 1: Tính timestamp VN → Unix (giờ server SPX)
# ══════════════════════════════════════════════════════════════
def get_vn_unix_range(date_str):
    """Chuyển '2026-05-15' → (start_unix, end_unix) theo giờ VN"""
    y, m, d = map(int, date_str.split("-"))
    # Đầu ngày VN (UTC+7) = UTC - 7 giờ
    start_vn = datetime(y, m, d, 0,  0,  0, tzinfo=VN_TZ)
    end_vn   = datetime(y, m, d, 23, 59, 59, tzinfo=VN_TZ)
    return int(start_vn.timestamp()), int(end_vn.timestamp())


# ══════════════════════════════════════════════════════════════
#  BƯỚC 2: Gọi API SPX lấy data attendance
# ══════════════════════════════════════════════════════════════
def get_csrf_from_cookie(cookie_str):
    """Lấy csrftoken từ chuỗi cookie"""
    for part in cookie_str.split(";"):
        part = part.strip()
        if part.startswith("csrftoken="):
            return part.split("=", 1)[1].strip()
    return ""


def fetch_attendance(date_str):
    """Lấy toàn bộ dữ liệu attendance cho 1 ngày, tự phân trang"""
    start_ts, end_ts = get_vn_unix_range(date_str)
    csrf = get_csrf_from_cookie(SPX_COOKIE)

    headers = {
        "accept": "application/json, text/plain, */*",
        "app": "FMS Portal",
        "x-csrftoken": csrf,
        "cookie": SPX_COOKIE,
        "referer": f"{SPX_BASE}/#/attendanceNew/index",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    all_rows = []
    page = 1

    while True:
        url = (
            f"{SPX_BASE}{API_PATH}"
            f"?pageno={page}&count=100&staff_type=2"
            f"&start_time={start_ts}&end_time={end_ts}"
        )
        print(f"  → Gọi API trang {page} ...")
        resp = requests.get(url, headers=headers, timeout=30)

        if resp.status_code in (401, 403):
            raise Exception(
                f"❌ Session SPX hết hạn (HTTP {resp.status_code}). "
                "Cần cập nhật SPX_COOKIE trong GitHub Secrets."
            )
        if resp.status_code != 200:
            raise Exception(f"❌ API trả về HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if data.get("retcode") != 0:
            raise Exception(f"❌ SPX API lỗi: retcode={data.get('retcode')} msg={data.get('message')}")

        records = data.get("data", {}).get("list", [])
        total   = data.get("data", {}).get("total", 0)

        for r in records:
            all_rows.append(build_row(r))

        print(f"     Trang {page}: {len(records)} bản ghi | Tổng đã lấy: {len(all_rows)}/{total}")

        # Hết trang → dừng
        if len(all_rows) >= total or len(records) < 100:
            break

        page += 1
        time.sleep(0.5)  # Tránh spam API

    return all_rows


def safe(v):
    """Làm sạch giá trị trả về"""
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s == "-" else s


def fmt_timestamp(ts):
    """Unix timestamp → chuỗi ngày giờ VN"""
    if not ts or int(ts) <= 0:
        return ""
    dt = datetime.fromtimestamp(int(ts), tz=VN_TZ)
    return dt.strftime("%H:%M %d/%m/%Y")


def build_row(r):
    """Chuyển 1 record API → 1 dòng list khớp với HEADERS"""
    return [
        safe(r.get("date")),
        safe(r.get("biz_staff_id")),
        safe(r.get("staff_name")),
        safe(r.get("staff_email")),
        safe(r.get("profile_station_name")),
        safe(r.get("event_station_name")),
        safe(r.get("agency")),
        safe(r.get("contract_type")),
        safe(r.get("department_name")),
        safe(r.get("slot_code")),
        safe(r.get("clock_in_status_name")),
        safe(r.get("clock_out_status_name")),
        fmt_timestamp(r.get("clock_in_time")),
        fmt_timestamp(r.get("clock_out_time")),
        safe(r.get("clock_in_date_str")),
        safe(r.get("clock_out_date_str")),
        safe(r.get("planned_hours")),
        safe(r.get("actual_hours")),
        safe(r.get("fulfill_working_hours")),
        safe(r.get("break_time")),
        safe(r.get("ot_applied")),
        safe(r.get("ot_worked")),
        safe(r.get("out_of_event_name")),
        safe(r.get("sick_or_leave")),
        safe(r.get("event_id")),
        safe(r.get("clock_in_matching_type_str")),
        safe(r.get("clock_out_matching_type_str")),
    ]


# ══════════════════════════════════════════════════════════════
#  BƯỚC 3: Kết nối Google Sheets qua Service Account
# ══════════════════════════════════════════════════════════════
def get_sheets_service():
    """Tạo Google Sheets client từ Service Account JSON"""
    sa_info = json.loads(GCP_SA_KEY)
    creds = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def read_existing_rows(service):
    """Đọc toàn bộ dữ liệu hiện có trong sheet (bỏ qua header)"""
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2:AA"
    ).execute()
    return result.get("values", [])


def dedup_rows(new_rows, existing_rows):
    """Lọc bỏ các dòng đã có trong sheet"""
    existing_keys = set("|".join(str(c) for c in row) for row in existing_rows)
    unique = []
    dupes  = 0
    for row in new_rows:
        key = "|".join(str(c) for c in row)
        if key in existing_keys:
            dupes += 1
        else:
            unique.append(row)
            existing_keys.add(key)
    return unique, dupes


def ensure_header(service, existing_rows):
    """Nếu sheet trống, ghi header row trước"""
    if not existing_rows:
        # Kiểm tra hàng đầu
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1:AA1"
        ).execute()
        header_in_sheet = result.get("values", [])
        if not header_in_sheet:
            print("  → Sheet chưa có header → tự động ghi header...")
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS]}
            ).execute()


def append_to_sheet(service, rows):
    """Append các dòng mới vào sheet"""
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:AA",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}
    ).execute()


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print(f"SPX Attendance Sync  |  Ngày quét: {DATE_STR} (N-1)")
    print(f"Sheet: {SHEET_NAME}")
    print("=" * 60)

    # 1. Lấy data từ SPX API
    print(f"\n[1/3] Gọi API SPX lấy data ngày {DATE_STR}...")
    new_rows = fetch_attendance(DATE_STR)
    print(f"  ✅ Lấy được {len(new_rows)} bản ghi từ SPX")

    if not new_rows:
        print("  ⚠️  Không có dữ liệu cho ngày này. Kết thúc.")
        return

    # 2. Kết nối Google Sheets
    print("\n[2/3] Kết nối Google Sheets...")
    service = get_sheets_service()
    existing = read_existing_rows(service)
    print(f"  ✅ Sheet hiện có {len(existing)} dòng data")

    # Đảm bảo có header
    ensure_header(service, existing)

    # 3. Dedup và ghi
    print("\n[3/3] Lọc trùng và ghi vào sheet...")
    unique_rows, dupe_count = dedup_rows(new_rows, existing)
    print(f"  → Trùng (bỏ qua): {dupe_count} dòng")
    print(f"  → Mới (sẽ ghi):   {len(unique_rows)} dòng")

    if unique_rows:
        append_to_sheet(service, unique_rows)
        print(f"  ✅ Đã ghi {len(unique_rows)} dòng vào sheet '{SHEET_NAME}'")
    else:
        print("  ℹ️  Không có dòng mới nào cần ghi.")

    print("\n" + "=" * 60)
    print(f"✅ HOÀN TẤT: {len(unique_rows)} dòng mới | {dupe_count} trùng bỏ qua")
    print("=" * 60)


if __name__ == "__main__":
    main()
