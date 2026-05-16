import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quan_ly_ktx.db")


def init_database(db_path: str = DB_PATH) -> None:
    """
    Khởi tạo database SQLite cho hệ thống KTX + bãi xe thông minh.
    - Tạo 3 bảng: SinhVien, PhuongTien, LichSu
    - Chèn sẵn dữ liệu mẫu để test nhanh.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")

        # Bật ràng buộc khóa ngoại trong SQLite.
        cursor.execute("PRAGMA foreign_keys = ON")

        # Bảng SinhVien
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS SinhVien (
                id_sinhvien TEXT PRIMARY KEY,
                ho_ten TEXT NOT NULL,
                duong_dan_anh TEXT NOT NULL
            )
            """
        )

        # Bảng PhuongTien
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS PhuongTien (
                bien_so TEXT PRIMARY KEY,
                id_sinhvien TEXT NOT NULL,
                trang_thai TEXT NOT NULL DEFAULT 'Ngoai_Bai',
                FOREIGN KEY (id_sinhvien) REFERENCES SinhVien(id_sinhvien)
            )
            """
        )

        # Bảng LichSu
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS LichSu (
                id_log INTEGER PRIMARY KEY AUTOINCREMENT,
                thoi_gian DATETIME DEFAULT CURRENT_TIMESTAMP,
                su_kien TEXT NOT NULL,
                doi_tuong TEXT NOT NULL
            )
            """
        )

        # Tạo index để tăng tốc truy vấn theo các cột thường dùng.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sinhvien_duong_dan_anh ON SinhVien(duong_dan_anh)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_phuongtien_id_sinhvien ON PhuongTien(id_sinhvien)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_lichsu_thoi_gian ON LichSu(thoi_gian)"
        )

        # Mock data sinh viên (id gợi ý trùng tên ảnh mẫu).
        # Nếu ảnh chưa tồn tại trong thư mục database_khuonmat, bạn có thể đổi lại tùy ý.
        mock_students = [
            ("IMG_0131", "Nguyen Van A", "IMG_0131.JPG"),
            ("B21DCCN001", "Tran Thi B", "B21DCCN001.jpg"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO SinhVien (id_sinhvien, ho_ten, duong_dan_anh)
            VALUES (?, ?, ?)
            """,
            mock_students,
        )

        mock_vehicles = [
            ("30A12345", "IMG_0131", "Ngoai_Bai"),
            ("29B67890", "B21DCCN001", "Trong_Bai"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO PhuongTien (bien_so, id_sinhvien, trang_thai)
            VALUES (?, ?, ?)
            """,
            mock_vehicles,
        )

        conn.commit()
        print(f"[OK] Đã khởi tạo database thành công: {db_path}")
        print("[OK] Đã tạo bảng: SinhVien, PhuongTien, LichSu")
        print("[OK] Đã chèn dữ liệu mẫu (nếu chưa tồn tại).")

    except sqlite3.Error as db_error:
        print(f"[LOI][SQLite] Không thể khởi tạo DB: {db_error}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    init_database()
