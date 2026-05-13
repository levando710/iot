# Dashboard quản trị KTX

Dashboard web (Flask, server-rendered) để:
- Xem lịch sử ra/vào (`LichSu`)
- CRUD sinh viên (`SinhVien`)
- CRUD phương tiện (`PhuongTien`)

## Chạy nhanh

```powershell
.\venv\Scripts\python.exe .\dashboard\app.py
```

Mở trình duyệt tại: `http://127.0.0.1:5001`

## Biến môi trường tùy chọn

- `DASHBOARD_DB_PATH`: đường dẫn tới file SQLite (mặc định: `quan_ly_ktx.db` tại thư mục project)
- `DASHBOARD_PORT`: cổng chạy web (mặc định `5001`)
- `DASHBOARD_SECRET_KEY`: khóa session cho Flask

## Route chính

- `/dashboard`: tổng quan + log gần nhất
- `/students`: danh sách + thêm/xóa sinh viên
- `/students/<id>/edit`: sửa sinh viên
- `/vehicles`: danh sách + thêm/xóa phương tiện
- `/vehicles/<plate>/edit`: sửa phương tiện
- `/history`: lọc lịch sử theo sự kiện/từ khóa/limit
