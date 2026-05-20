# Dashboard quan ly he thong

Thu muc `dashboard` chua ung dung Flask dung de quan ly du lieu va theo doi lich su hoat dong cua he thong KTX - bai xe.

## Chuc nang

- Xem tong quan so luong sinh vien, phuong tien va lich su.
- Quan ly sinh vien.
- Quan ly phuong tien da dang ky.
- Xem lich su su kien ra vao KTX va bai xe.
- Lam viec truc tiep voi database SQLite cua server.

## Chay dashboard

Tu thu muc goc du an:

```powershell
python .\dashboard\app.py
```

Sau khi chay, mo trinh duyet tai:

```text
http://127.0.0.1:5001
```

## Bien moi truong

| Bien | Mac dinh | Y nghia |
| --- | --- | --- |
| `DASHBOARD_DB_PATH` | Database mac dinh cua du an | Duong dan file SQLite |
| `DASHBOARD_PORT` | `5001` | Cong chay dashboard |
| `DASHBOARD_SECRET_KEY` | Gia tri phat sinh | Secret key cho Flask session |

Neu khong cau hinh rieng, dashboard se dung database mac dinh cua server.

## Cac trang chinh

| Route | Chuc nang |
| --- | --- |
| `/dashboard` | Man hinh tong quan |
| `/students` | Danh sach sinh vien |
| `/students/<id>/edit` | Sua thong tin sinh vien |
| `/vehicles` | Danh sach phuong tien |
| `/vehicles/<plate>/edit` | Sua thong tin phuong tien |
| `/history` | Lich su hoat dong |

## Luu y

- Nen chay `init_db.py` truoc khi mo dashboard lan dau.
- Dashboard va server nen dung chung mot file database de du lieu dong bo.
- Khong dua database that len GitHub neu database co thong tin sinh vien, bien so xe hoac anh khuon mat.
