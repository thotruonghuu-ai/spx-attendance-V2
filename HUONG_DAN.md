# 📋 HƯỚNG DẪN SETUP - SPX ATTENDANCE GITHUB ACTIONS
### Tắt máy vẫn tự động chạy mỗi ngày | Hoàn toàn miễn phí

---

## 🗺️ TỔNG QUAN HỆ THỐNG

```
Mỗi ngày lúc 7:00 sáng (kể cả khi máy tắt):

   GitHub Actions (cloud miễn phí)
        │
        ├─► Dùng Cookie SPX → gọi API SPX lấy data ngày hôm qua (N-1)
        │
        ├─► Ghi data vào Google Sheet "Att Reco"
        │
        └─► Google Apps Script (đã có sẵn) → gửi mail thông báo miss công

Bạn chỉ cần: cập nhật Cookie 1 lần/tháng (mất 2 phút)
```

---

## ✅ CHECKLIST TRƯỚC KHI BẮT ĐẦU

Bạn cần có:
- [ ] Tài khoản GitHub (miễn phí) → https://github.com
- [ ] Tài khoản Google (đã có sẵn)
- [ ] Trình duyệt Chrome đang đăng nhập spx.shopee.vn
- [ ] Bộ file này (đã có trong tay)

---

## BƯỚC 1: TẠO TÀI KHOẢN GITHUB (nếu chưa có)

1. Vào https://github.com → bấm **Sign up**
2. Nhập Email → mật khẩu → username (tên hiển thị)
3. Xác nhận email
4. Đăng nhập vào GitHub

---

## BƯỚC 2: TẠO REPOSITORY TRÊN GITHUB

> Repository = thư mục chứa code trên GitHub

1. Sau khi đăng nhập, bấm nút **"+"** ở góc trên phải → chọn **"New repository"**

2. Điền thông tin:
   - **Repository name**: `spx-attendance-sync`
   - **Description**: `SPX Attendance Auto Sync`  *(tuỳ ý)*
   - Chọn **Private** *(bắt buộc - để bảo mật cookie)*
   - **KHÔNG** tích vào "Add a README file"

3. Bấm nút xanh **"Create repository"**

4. GitHub sẽ hiện trang trống. **Giữ nguyên trang này**, sang bước tiếp.

---

## BƯỚC 3: UPLOAD CODE LÊN GITHUB

### Cách A: Dùng GitHub web (dễ nhất, không cần cài gì)

1. Trên trang repository vừa tạo, bấm **"uploading an existing file"**

2. Kéo thả **toàn bộ các file** trong thư mục `spx-github-actions` vào:
   ```
   spx-github-actions/
   ├── .github/
   │   └── workflows/
   │       └── sync.yml          ← kéo vào đây
   ├── scripts/
   │   ├── sync_attendance.py    ← kéo vào đây
   │   ├── requirements.txt      ← kéo vào đây
   │   └── get_cookie.py         ← kéo vào đây (không bắt buộc)
   └── .gitignore                ← kéo vào đây
   ```

   ⚠️ **Quan trọng**: File `sync.yml` phải nằm trong thư mục `.github/workflows/`
   Khi upload, GitHub tự tạo thư mục nếu bạn giữ nguyên cấu trúc.

3. Cuộn xuống → bấm **"Commit changes"** (màu xanh)

---

## BƯỚC 4: TẠO GOOGLE SERVICE ACCOUNT

> Service Account = tài khoản robot để GitHub tự động ghi vào Google Sheet mà không cần bạn đăng nhập

### 4.1 - Tạo project Google Cloud

1. Vào https://console.cloud.google.com
2. Bấm vào **"Select a project"** (góc trên trái) → **"NEW PROJECT"**
3. Đặt tên: `spx-attendance` → bấm **"CREATE"**
4. Chờ 10 giây → bấm vào project vừa tạo

### 4.2 - Bật Google Sheets API

1. Menu trái → **"APIs & Services"** → **"Library"**
2. Tìm kiếm: `Google Sheets API`
3. Bấm vào kết quả → bấm nút **"ENABLE"** (màu xanh)

### 4.3 - Tạo Service Account

1. Menu trái → **"APIs & Services"** → **"Credentials"**
2. Bấm **"+ CREATE CREDENTIALS"** → chọn **"Service account"**
3. Điền:
   - **Service account name**: `spx-sync-bot`
   - **Service account ID**: tự điền (giữ nguyên)
4. Bấm **"CREATE AND CONTINUE"**
5. Phần "Grant this service account access": bỏ qua → bấm **"CONTINUE"**
6. Bấm **"DONE"**

### 4.4 - Tạo key JSON

1. Trong trang Credentials, bấm vào service account vừa tạo (`spx-sync-bot@...`)
2. Bấm tab **"KEYS"**
3. Bấm **"ADD KEY"** → **"Create new key"**
4. Chọn **JSON** → bấm **"CREATE"**
5. File JSON tự động tải về máy (ví dụ: `spx-attendance-xxxxx.json`)

   ⚠️ **Giữ file này cẩn thận, KHÔNG chia sẻ với ai!**

6. Mở file JSON đó bằng Notepad, **copy toàn bộ nội dung** (sẽ dùng ở Bước 6)

### 4.5 - Lấy email của Service Account

1. Trong tab **"DETAILS"** của service account
2. Copy dòng email dạng: `spx-sync-bot@spx-attendance-xxxxx.iam.gserviceaccount.com`
3. **Giữ lại email này** (dùng ở bước tiếp)

---

## BƯỚC 5: CẤP QUYỀN CHO SERVICE ACCOUNT VÀO GOOGLE SHEET

1. Mở Google Sheet của bạn (sheet chứa "Att Reco")
2. Bấm nút **"Share"** (Chia sẻ) ở góc trên phải
3. Dán email service account vào ô email: `spx-sync-bot@spx-attendance-xxxxx.iam.gserviceaccount.com`
4. Đổi quyền thành **"Editor"** (Chỉnh sửa)
5. Bấm **"Send"** (bỏ qua cảnh báo "not in organization")

---

## BƯỚC 6: LẤY COOKIE SPX

> Cookie = chìa khoá để vào SPX mà không cần đăng nhập lại

1. Mở Chrome → vào https://spx.shopee.vn/#/attendanceNew/index
2. Nhấn **F12** để mở DevTools
3. Bấm tab **"Network"** (Mạng)
4. Trên trang SPX, bấm nút **Search** hoặc thay đổi ngày bất kỳ để tạo request
5. Trong cột danh sách Network bên trái, tìm request có tên chứa `statistic_data_list`
   - Nếu không thấy: gõ `statistic` vào ô Filter
6. Bấm vào request đó
7. Bấm tab **"Headers"** bên phải
8. Cuộn xuống phần **"Request Headers"**
9. Tìm dòng **`cookie:`**
10. **Bấm chuột phải** vào giá trị cookie → **"Copy value"**
    (giá trị rất dài, khoảng 500-1000 ký tự)

---

## BƯỚC 7: LẤY ID CỦA GOOGLE SHEET

1. Mở Google Sheet của bạn
2. Nhìn vào URL trên trình duyệt:
   ```
   https://docs.google.com/spreadsheets/d/1WsaBKU6Tl6kJ0Dhsm6diJqSQtUVId.../edit
                                          ↑ đây là SPREADSHEET_ID
   ```
3. Copy phần ID (chuỗi chữ số và chữ dài nằm giữa `/d/` và `/edit`)

---

## BƯỚC 8: CẤU HÌNH SECRETS TRÊN GITHUB

> Secrets = kho lưu trữ bí mật, mã hoá an toàn trên GitHub

1. Vào repository GitHub của bạn (`spx-attendance-sync`)
2. Bấm tab **"Settings"** (Cài đặt)
3. Menu trái → **"Secrets and variables"** → **"Actions"**
4. Bấm **"New repository secret"**

Lần lượt tạo **4 secrets** sau:

---

### Secret 1: SPX_COOKIE
- **Name**: `SPX_COOKIE`
- **Secret**: Dán toàn bộ cookie SPX đã copy ở Bước 6
- Bấm **"Add secret"**

---

### Secret 2: SPREADSHEET_ID
- **Name**: `SPREADSHEET_ID`
- **Secret**: ID Google Sheet đã copy ở Bước 7
  (ví dụ: `1WsaBKU6Tl6kJ0Dhsm6diJqSQtUVIdSSQOuSS5J7BwH0`)
- Bấm **"Add secret"**

---

### Secret 3: SHEET_NAME
- **Name**: `SHEET_NAME`
- **Secret**: Tên sheet tab chứa data (mặc định là `Att Reco`)
- Bấm **"Add secret"**

---

### Secret 4: GCP_SERVICE_ACCOUNT
- **Name**: `GCP_SERVICE_ACCOUNT`
- **Secret**: Dán **toàn bộ nội dung** file JSON đã tải ở Bước 4.4
  (bắt đầu bằng `{` và kết thúc bằng `}`)
- Bấm **"Add secret"**

---

Kết quả: bạn sẽ thấy 4 secrets trong danh sách:
```
✅ GCP_SERVICE_ACCOUNT
✅ SHEET_NAME
✅ SPREADSHEET_ID
✅ SPX_COOKIE
```

---

## BƯỚC 9: CHẠY THỬ LẦN ĐẦU

1. Vào tab **"Actions"** trên repository GitHub
2. Bấm vào workflow **"SPX Attendance Daily Sync"** bên trái
3. Bấm nút **"Run workflow"** (bên phải) → **"Run workflow"** (xác nhận)
4. Bấm F5 refresh trang → thấy workflow đang chạy (vòng tròn vàng)
5. Bấm vào workflow đó để xem log chi tiết
6. Chờ 1-2 phút → nếu thấy ✅ xanh = thành công!

### Nếu thất bại (❌ đỏ):
Bấm vào workflow → bấm "sync" → đọc phần lỗi màu đỏ:

| Lỗi | Cách xử lý |
|-----|------------|
| `Session SPX hết hạn` | Lấy lại cookie (Bước 6) → cập nhật Secret SPX_COOKIE |
| `invalid_grant` | Service account key hết hạn → tạo key mới (Bước 4.4) |
| `PERMISSION_DENIED` | Chưa cấp quyền Editor cho service account (Bước 5) |
| `Sheet not found` | Kiểm tra lại tên sheet trong Secret SHEET_NAME |

---

## BƯỚC 10: XÁC NHẬN LỊCH TỰ ĐỘNG

Sau khi chạy thử thành công, hệ thống sẽ **tự động chạy mỗi ngày lúc 7:00 sáng** mà không cần bất kỳ thao tác nào.

Để kiểm tra lịch:
- Vào tab **"Actions"** → xem cột "Scheduled" trong lịch sử chạy

---

## 🔄 BẢO TRÌ HÀNG THÁNG (chỉ mất 2 phút)

Cookie SPX hết hạn sau khoảng 30 ngày. Khi hết hạn, bạn sẽ thấy workflow lỗi `Session SPX hết hạn`.

**Cách cập nhật cookie:**
1. Lấy cookie mới (lặp lại Bước 6)
2. Vào GitHub → Settings → Secrets → bấm **"Update"** bên cạnh `SPX_COOKIE`
3. Dán cookie mới → **"Update secret"**
4. Xong! Ngày hôm sau tự chạy bình thường.

---

## 📊 THEO DÕI HOẠT ĐỘNG

- **Xem log mỗi ngày**: GitHub → Actions → chọn ngày muốn xem
- **Email thông báo lỗi**: GitHub tự gửi email nếu workflow thất bại
  (Settings → Notifications → Actions)
- **Hạn mức miễn phí GitHub**: 2,000 phút/tháng → script chạy ~2 phút/ngày = ~60 phút/tháng → **dư sức**

---

## ❓ CÂU HỎI THƯỜNG GẶP

**Q: Cần bật máy không?**
A: Không. GitHub chạy trên server của họ, máy bạn tắt hoàn toàn vẫn OK.

**Q: Mất phí không?**
A: Hoàn toàn miễn phí. GitHub Actions free 2000 phút/tháng. Google Sheets API free.

**Q: Cookie có bị lộ không?**
A: Không. GitHub Secrets mã hoá, không ai đọc được kể cả bạn sau khi lưu.

**Q: Chạy lúc mấy giờ?**
A: 7:00 sáng giờ VN mỗi ngày, lấy data của ngày hôm qua (N-1).

**Q: Nếu muốn lấy data nhiều ngày?**
A: Bấm "Run workflow" thủ công → nhập ngày vào ô "date_override".

---

*Hướng dẫn này dành cho người mới, không cần biết code. Mọi thắc mắc hãy đọc lại từng bước.*
