import os
import io
import sqlite3
import tempfile
from pathlib import Path

from dashboard.app import create_app


# PNG 1x1 pixel hợp lệ để test upload ảnh multipart
PNG_1X1_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c``\x00\x00\x00\x04\x00\x01"
    b"\x0b\xe7\x02\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


def create_test_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE SinhVien (
                id_sinhvien TEXT PRIMARY KEY,
                ho_ten TEXT NOT NULL,
                duong_dan_anh TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE PhuongTien (
                bien_so TEXT PRIMARY KEY,
                id_sinhvien TEXT NOT NULL,
                trang_thai TEXT NOT NULL DEFAULT 'Ngoai_Bai',
                FOREIGN KEY (id_sinhvien) REFERENCES SinhVien(id_sinhvien)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE LichSu (
                id_log INTEGER PRIMARY KEY AUTOINCREMENT,
                thoi_gian DATETIME DEFAULT CURRENT_TIMESTAMP,
                su_kien TEXT NOT NULL,
                doi_tuong TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO SinhVien (id_sinhvien, ho_ten, duong_dan_anh) VALUES (?, ?, ?)",
            ("SV001", "Nguyen Van A", "SV001.jpg"),
        )
        conn.execute(
            "INSERT INTO PhuongTien (bien_so, id_sinhvien, trang_thai) VALUES (?, ?, ?)",
            ("30A12345", "SV001", "Ngoai_Bai"),
        )
        conn.execute(
            "INSERT INTO LichSu (su_kien, doi_tuong) VALUES (?, ?)",
            ("KTX_ACCESS_GRANTED", "SV001"),
        )
        conn.commit()
    finally:
        conn.close()


def run_smoke() -> int:
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_dashboard.db"
        create_test_db(db_path)

        app = create_app(str(db_path))
        app.testing = True
        client = app.test_client()

        # 1) Load dashboard
        res = client.get("/dashboard")
        if res.status_code != 200:
            print(f"[FAIL] GET /dashboard trả về {res.status_code}")
            return 1

        # 2) Add student
        res = client.post(
            "/students",
            data={
                "id_sinhvien": "SV002",
                "ho_ten": "Tran Thi B",
                "face_image": (io.BytesIO(PNG_1X1_BYTES), "portrait.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        if res.status_code != 200 or b"SV002" not in res.data:
            print("[FAIL] Không thêm được sinh viên SV002")
            return 1

        # 3) Add vehicle
        res = client.post(
            "/vehicles",
            data={
                "bien_so": "29B67890",
                "id_sinhvien": "SV002",
                "trang_thai": "Trong_Bai",
            },
            follow_redirects=True,
        )
        if res.status_code != 200 or b"29B67890" not in res.data:
            print("[FAIL] Không thêm được xe 29B67890")
            return 1

        # 4) History page
        res = client.get("/history?limit=50")
        if res.status_code != 200:
            print(f"[FAIL] GET /history trả về {res.status_code}")
            return 1

        print("[PASS] Dashboard smoke test thành công")
        return 0


if __name__ == "__main__":
    raise SystemExit(run_smoke())
