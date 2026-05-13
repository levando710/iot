import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

DB_PATH = BASE_DIR / "quan_ly_ktx.db"
FACE_DIR = BASE_DIR / "database_khuonmat"

REQUIRED_TABLES = {"SinhVien", "PhuongTien", "LichSu"}


def _db_has_face_url() -> tuple[bool, int]:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*)
            FROM SinhVien
            WHERE LOWER(TRIM(duong_dan_anh)) LIKE 'http://%'
               OR LOWER(TRIM(duong_dan_anh)) LIKE 'https://%'
            """
        )
        count = int(cur.fetchone()[0])
        return count > 0, count
    except sqlite3.Error:
        return False, 0
    finally:
        conn.close()


def check_db_schema() -> tuple[bool, str]:
    if not DB_PATH.exists():
        return False, f"Thiếu DB: {DB_PATH}"

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        missing = REQUIRED_TABLES - tables
        if missing:
            return False, f"Thiếu bảng trong DB: {sorted(missing)}"
        return True, "DB schema hợp lệ"
    finally:
        conn.close()


def check_face_dir() -> tuple[bool, str]:
    if not FACE_DIR.exists():
        has_url, url_count = _db_has_face_url()
        if has_url:
            return True, (
                f"Chưa có thư mục ảnh local ({FACE_DIR}), nhưng DB có {url_count} URL ảnh mặt; "
                "server sẽ đồng bộ khi khởi động"
            )
        return False, f"Thiếu thư mục ảnh mặt: {FACE_DIR}"

    image_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = [p for p in FACE_DIR.rglob("*") if p.suffix.lower() in image_ext]
    if not images:
        has_url, url_count = _db_has_face_url()
        if has_url:
            return True, (
                f"Chưa có ảnh local trong database_khuonmat, nhưng DB có {url_count} URL ảnh mặt; "
                "server sẽ đồng bộ khi khởi động"
            )
        return False, "Thư mục database_khuonmat chưa có ảnh mẫu"

    return True, f"Tìm thấy {len(images)} ảnh mẫu"


def check_env() -> tuple[bool, str]:
    # Các biến bắt buộc tối thiểu để chạy main_server.py
    required = ["MQTT_HOST", "MQTT_PORT"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        return False, f"Thiếu biến môi trường: {missing}"

    host = os.getenv("MQTT_HOST", "").strip().lower()
    if host in {"your-cloudmqtt-host", "your-broker-host", "example.com", "localhost.localdomain"}:
        return False, "MQTT_HOST vẫn là giá trị mẫu, chưa phải broker thật"

    port = os.getenv("MQTT_PORT", "1883").strip()
    use_tls = os.getenv("MQTT_USE_TLS", "0").strip().lower() in {"1", "true", "yes", "on"}
    if port == "8883" and not use_tls:
        return False, "MQTT_PORT=8883 nhưng MQTT_USE_TLS chưa bật"

    return True, "Biến môi trường MQTT hợp lệ"


def run_smoke() -> int:
    checks = [
        ("SQLite schema", check_db_schema),
        ("Face dataset", check_face_dir),
        ("MQTT env", check_env),
    ]

    failed = 0
    print("=== SMOKE TEST DỰ ÁN KTX MANAGER ===")
    for name, fn in checks:
        ok, msg = fn()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {msg}")
        if not ok:
            failed += 1

    print("====================================")
    if failed:
        print(f"Kết luận: FAIL ({failed} hạng mục lỗi)")
        return 1

    print("Kết luận: PASS (sẵn sàng chạy server)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_smoke())
