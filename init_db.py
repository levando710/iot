import os
import sqlite3


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quan_ly_ktx.db")


def init_database(db_path: str = DB_PATH) -> None:
    """Create the SQLite schema and seed demo data for the project."""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA foreign_keys = ON")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS SinhVien (
                id_sinhvien TEXT PRIMARY KEY,
                ho_ten TEXT NOT NULL,
                duong_dan_anh TEXT NOT NULL
            )
            """
        )

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

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sinhvien_duong_dan_anh ON SinhVien(duong_dan_anh)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_phuongtien_id_sinhvien ON PhuongTien(id_sinhvien)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_lichsu_thoi_gian ON LichSu(thoi_gian)"
        )

        demo_students = [
            ("IMG_0131", "Nguyen Van A", "IMG_0131.JPG"),
            ("B21DCCN001", "Tran Thi B", "B21DCCN001.jpg"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO SinhVien (id_sinhvien, ho_ten, duong_dan_anh)
            VALUES (?, ?, ?)
            """,
            demo_students,
        )

        demo_vehicles = [
            ("30A12345", "IMG_0131", "Ngoai_Bai"),
            ("29B67890", "B21DCCN001", "Trong_Bai"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO PhuongTien (bien_so, id_sinhvien, trang_thai)
            VALUES (?, ?, ?)
            """,
            demo_vehicles,
        )

        conn.commit()
        print(f"[OK] Database initialized: {db_path}")
        print("[OK] Tables ready: SinhVien, PhuongTien, LichSu")
        print("[OK] Demo data inserted when missing.")

    except sqlite3.Error as db_error:
        print(f"[ERROR][SQLite] Cannot initialize database: {db_error}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    init_database()
