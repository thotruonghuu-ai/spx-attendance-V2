"""
get_cookie.py  —  Lấy cookie SPX từ Chrome và hiển thị để copy lên GitHub Secrets
Chạy trên máy tính của bạn, KHÔNG phải trên GitHub Actions

Cách dùng:
  1. Mở Chrome → đăng nhập spx.shopee.vn
  2. Mở Terminal / CMD tại thư mục này
  3. Chạy: python get_cookie.py
  4. Copy kết quả → dán vào GitHub Secret SPX_COOKIE
"""

import sqlite3
import os
import sys
import shutil
import tempfile

def get_chrome_cookies(domain=".shopee.vn"):
    """Đọc cookie từ Chrome trên Windows"""

    # Đường dẫn Chrome cookie database (Windows)
    chrome_path = os.path.expanduser(
        r"~\AppData\Local\Google\Chrome\User Data\Default\Network\Cookies"
    )

    if not os.path.exists(chrome_path):
        # Thử đường dẫn khác
        chrome_path = os.path.expanduser(
            r"~\AppData\Local\Google\Chrome\User Data\Default\Cookies"
        )

    if not os.path.exists(chrome_path):
        print("❌ Không tìm thấy file Cookie của Chrome.")
        print("   Hãy chắc chắn Chrome đã cài và đã đăng nhập spx.shopee.vn")
        sys.exit(1)

    # Copy file vì Chrome đang lock
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(chrome_path, tmp)

    try:
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT name, value, encrypted_value, host_key, path, expires_utc
            FROM cookies
            WHERE host_key LIKE ?
            ORDER BY name
        """, (f"%{domain}%",))

        rows = cur.fetchall()
        conn.close()

        cookies = {}
        for row in rows:
            name = row["name"]
            value = row["value"]
            # Chrome mã hoá cookie trên Windows - lấy value text (không mã hoá)
            if value:
                cookies[name] = value

        return cookies

    finally:
        os.remove(tmp)


def main():
    print("=" * 60)
    print("SPX Cookie Extractor")
    print("=" * 60)
    print()
    print("⚠️  Lưu ý: Script này chỉ lấy được cookie TEXT (không mã hoá).")
    print("   Nếu kết quả trống, dùng cách thủ công bên dưới.")
    print()

    # Thử đọc tự động
    try:
        cookies = get_chrome_cookies()
        if cookies:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            print("✅ Cookie tìm thấy:")
            print()
            print("-" * 60)
            print(cookie_str)
            print("-" * 60)
            print()
            print("→ Copy toàn bộ dòng trên → dán vào GitHub Secret: SPX_COOKIE")
        else:
            print("⚠️  Không tìm thấy cookie text. Dùng cách thủ công bên dưới.")
    except Exception as e:
        print(f"⚠️  Lỗi đọc tự động: {e}")

    print()
    print("=" * 60)
    print("CÁCH LẤY COOKIE THỦ CÔNG (CHẮC CHẮN ĐÚNG HƠN):")
    print("=" * 60)
    print()
    print("1. Mở Chrome → vào https://spx.shopee.vn/#/attendanceNew/index")
    print("2. Nhấn F12 → tab 'Network'")
    print("3. Bấm nút Search/Tìm kiếm bất kỳ trên trang để tạo request")
    print("4. Trong Network tab, click vào bất kỳ request nào đến spx.shopee.vn")
    print("5. Cuộn xuống phần 'Request Headers'")
    print("6. Tìm dòng 'cookie:' → copy TOÀN BỘ giá trị (rất dài)")
    print("7. Dán vào GitHub Secret: SPX_COOKIE")
    print()


if __name__ == "__main__":
    main()
