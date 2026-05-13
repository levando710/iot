from __future__ import annotations

import os
import re
import uuid
import queue
import sqlite3
import logging
import threading
from urllib.parse import urlsplit
from urllib.request import urlopen
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import cv2
import numpy as np
from dotenv import load_dotenv

try:
    import paho.mqtt.client as mqtt
except Exception as mqtt_import_error:
    mqtt = None
    MQTT_IMPORT_ERROR = mqtt_import_error
else:
    MQTT_IMPORT_ERROR = None

try:
    import easyocr
except Exception as easyocr_import_error:
    easyocr = None
    EASYOCR_IMPORT_ERROR = easyocr_import_error
else:
    EASYOCR_IMPORT_ERROR = None

try:
    from deepface import DeepFace
except Exception as deepface_import_error:
    DeepFace = None
    DEEPFACE_IMPORT_ERROR = deepface_import_error
else:
    DEEPFACE_IMPORT_ERROR = None

try:
    from ultralytics import YOLO
except Exception as yolo_import_error:
    YOLO = None
    YOLO_IMPORT_ERROR = yolo_import_error
else:
    YOLO_IMPORT_ERROR = None

try:
    import pyttsx3
except Exception as pyttsx3_import_error:
    pyttsx3 = None
    PYTTSX3_IMPORT_ERROR = pyttsx3_import_error
else:
    PYTTSX3_IMPORT_ERROR = None


# ==========================
# CẤU HÌNH CHUNG
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

DB_PATH = os.path.join(BASE_DIR, "quan_ly_ktx.db")
FACE_DB_DIR = os.path.join(BASE_DIR, "database_khuonmat")
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
CAMERA_URL = os.getenv("CAMERA_URL", "").strip()


def _read_int_env(key: str) -> Optional[int]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _resolve_camera_source(url_value: str, index_value: Optional[int]) -> object:
    if url_value:
        return url_value
    if index_value is not None:
        return index_value
    if CAMERA_URL:
        return CAMERA_URL
    return CAMERA_INDEX


CAMERA_KTX_IN_URL = os.getenv("CAMERA_KTX_IN_URL", "").strip()
CAMERA_KTX_IN_INDEX = _read_int_env("CAMERA_KTX_IN_INDEX")
CAMERA_KTX_OUT_URL = os.getenv("CAMERA_KTX_OUT_URL", "").strip()
CAMERA_KTX_OUT_INDEX = _read_int_env("CAMERA_KTX_OUT_INDEX")

CAMERA_PARK_IN_PLATE_URL = os.getenv("CAMERA_PARK_IN_PLATE_URL", "").strip()
CAMERA_PARK_IN_PLATE_INDEX = _read_int_env("CAMERA_PARK_IN_PLATE_INDEX")
CAMERA_PARK_OUT_PLATE_URL = os.getenv("CAMERA_PARK_OUT_PLATE_URL", "").strip()
CAMERA_PARK_OUT_PLATE_INDEX = _read_int_env("CAMERA_PARK_OUT_PLATE_INDEX")
CAMERA_PARK_OUT_FACE_URL = os.getenv("CAMERA_PARK_OUT_FACE_URL", "").strip()
CAMERA_PARK_OUT_FACE_INDEX = _read_int_env("CAMERA_PARK_OUT_FACE_INDEX")

CAMERA_KTX_IN_SNAPSHOT_URL = os.getenv("CAMERA_KTX_IN_SNAPSHOT_URL", "").strip()
CAMERA_KTX_OUT_SNAPSHOT_URL = os.getenv("CAMERA_KTX_OUT_SNAPSHOT_URL", "").strip()
CAMERA_PARK_IN_PLATE_SNAPSHOT_URL = os.getenv("CAMERA_PARK_IN_PLATE_SNAPSHOT_URL", "").strip()
CAMERA_PARK_OUT_PLATE_SNAPSHOT_URL = os.getenv("CAMERA_PARK_OUT_PLATE_SNAPSHOT_URL", "").strip()
CAMERA_PARK_OUT_FACE_SNAPSHOT_URL = os.getenv("CAMERA_PARK_OUT_FACE_SNAPSHOT_URL", "").strip()
CAMERA_SNAPSHOT_TIMEOUT_MS = int(os.getenv("CAMERA_SNAPSHOT_TIMEOUT_MS", "5000"))
CAMERA_SNAPSHOT_FIRST = os.getenv("CAMERA_SNAPSHOT_FIRST", "0").strip().lower() in {"1", "true", "yes", "on"}
CAMERA_DISABLE_STREAM_KEYS = {
    key.strip().lower()
    for key in os.getenv("CAMERA_DISABLE_STREAM_KEYS", "").split(",")
    if key.strip()
}

CAMERA_OPEN_TIMEOUT_MS = int(os.getenv("CAMERA_OPEN_TIMEOUT_MS", "10000"))
CAMERA_READ_TIMEOUT_MS = int(os.getenv("CAMERA_READ_TIMEOUT_MS", "10000"))
CAMERA_BUFFER_SIZE = int(os.getenv("CAMERA_BUFFER_SIZE", "1"))

CAMERA_SOURCES: Dict[str, object] = {
    "ktx_in": _resolve_camera_source(CAMERA_KTX_IN_URL, CAMERA_KTX_IN_INDEX),
    "ktx_out": _resolve_camera_source(CAMERA_KTX_OUT_URL, CAMERA_KTX_OUT_INDEX),
    "parking_in_plate": _resolve_camera_source(CAMERA_PARK_IN_PLATE_URL, CAMERA_PARK_IN_PLATE_INDEX),
    "parking_out_plate": _resolve_camera_source(CAMERA_PARK_OUT_PLATE_URL, CAMERA_PARK_OUT_PLATE_INDEX),
    "parking_out_face": _resolve_camera_source(CAMERA_PARK_OUT_FACE_URL, CAMERA_PARK_OUT_FACE_INDEX),
}

CAMERA_SNAPSHOT_URLS: Dict[str, str] = {
    "ktx_in": CAMERA_KTX_IN_SNAPSHOT_URL,
    "ktx_out": CAMERA_KTX_OUT_SNAPSHOT_URL,
    "parking_in_plate": CAMERA_PARK_IN_PLATE_SNAPSHOT_URL,
    "parking_out_plate": CAMERA_PARK_OUT_PLATE_SNAPSHOT_URL,
    "parking_out_face": CAMERA_PARK_OUT_FACE_SNAPSHOT_URL,
}
QUEUE_MAXSIZE = int(os.getenv("QUEUE_MAXSIZE", "20"))
DETECTED_PAYLOAD = "DETECTED"
PASSED_PAYLOAD = "PASSED"
VOICE_GUIDE_ENABLED = os.getenv("VOICE_GUIDE_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
VOICE_GUIDE_RATE = int(os.getenv("VOICE_GUIDE_RATE", "160"))
VOICE_GUIDE_VOLUME = float(os.getenv("VOICE_GUIDE_VOLUME", "1.0"))
FACE_RETRY_COUNT = max(1, int(os.getenv("FACE_RETRY_COUNT", "3")))
FACE_RETRY_INTERVAL_MS = max(0, int(os.getenv("FACE_RETRY_INTERVAL_MS", "2500")))

# CloudMQTT config (đặt qua biến môi trường để không hard-code bí mật)
MQTT_HOST = os.getenv("MQTT_HOST", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", f"ktx-server-{uuid.uuid4().hex[:8]}")
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "0").strip().lower() in {"1", "true", "yes", "on"}
MQTT_TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "0").strip().lower() in {"1", "true", "yes", "on"}
MQTT_TLS_CA_CERT = os.getenv("MQTT_TLS_CA_CERT", "").strip()

# Model biển số: nên trỏ tới model đã huấn luyện detect biển số.
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")

# Topics subscribe
TOPIC_KTX_SENSOR_VAO = "saban/ktx/sensor_vao"
TOPIC_KTX_SENSOR_RA = "saban/ktx/sensor_ra"
TOPIC_BAIXE_SENSOR_VAO = "saban/baixe/sensor_vao"
TOPIC_BAIXE_SENSOR_RA = "saban/baixe/sensor_ra"

# Topic mới cho bãi xe tách 2 cảm biến mỗi cổng (sensor1: AUTH, sensor2: CLOSE)
TOPIC_BAIXE_VAO_SENSOR1 = "saban/baixe/vao/sensor1"
TOPIC_BAIXE_VAO_SENSOR2 = "saban/baixe/vao/sensor2"
TOPIC_BAIXE_RA_SENSOR1 = "saban/baixe/ra/sensor1"
TOPIC_BAIXE_RA_SENSOR2 = "saban/baixe/ra/sensor2"

BAIXE_VAO_SENSOR1_TOPICS = {TOPIC_BAIXE_SENSOR_VAO, TOPIC_BAIXE_VAO_SENSOR1}
BAIXE_RA_SENSOR1_TOPICS = {TOPIC_BAIXE_SENSOR_RA, TOPIC_BAIXE_RA_SENSOR1}
BAIXE_SENSOR2_TOPICS = {TOPIC_BAIXE_VAO_SENSOR2, TOPIC_BAIXE_RA_SENSOR2}

SUBSCRIBE_TOPICS = [
    TOPIC_KTX_SENSOR_VAO,
    TOPIC_KTX_SENSOR_RA,
    TOPIC_BAIXE_SENSOR_VAO,
    TOPIC_BAIXE_SENSOR_RA,
    TOPIC_BAIXE_VAO_SENSOR1,
    TOPIC_BAIXE_VAO_SENSOR2,
    TOPIC_BAIXE_RA_SENSOR1,
    TOPIC_BAIXE_RA_SENSOR2,
]

# Topics publish servo
TOPIC_KTX_SERVO = "saban/ktx/servo"
TOPIC_BAIXE_SERVO_VAO = "saban/baixe/servo_vao"
TOPIC_BAIXE_SERVO_RA = "saban/baixe/servo_ra"

SERVO_TOPIC_MAP = {
    TOPIC_KTX_SENSOR_VAO: TOPIC_KTX_SERVO,
    TOPIC_KTX_SENSOR_RA: TOPIC_KTX_SERVO,
    TOPIC_BAIXE_SENSOR_VAO: TOPIC_BAIXE_SERVO_VAO,
    TOPIC_BAIXE_SENSOR_RA: TOPIC_BAIXE_SERVO_RA,
}


@dataclass
class SensorEvent:
    """Gói dữ liệu sự kiện nhận từ MQTT để đẩy vào Queue."""

    topic: str
    frame: Any
    timestamp: datetime
    action: str  # AUTH | CLOSE
    camera_key: Optional[str] = None


class SmartDormParkingServer:
    """
    Server quản lý KTX + bãi xe theo mô hình event-driven:
    - MQTT callback chỉ làm việc nhẹ: đọc frame và đẩy queue
    - Worker thread xử lý AI + DB + publish lệnh servo
    """

    def __init__(self) -> None:
        self.logger = self._setup_logger()
        self.ktx_event_queue: queue.Queue[SensorEvent] = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self.parking_event_queue: queue.Queue[SensorEvent] = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self.stop_event = threading.Event()
        self.gate_state_lock = threading.Lock()
        self.gate_state = {
            "ktx_vao_open": False,
            "ktx_ra_open": False,
            "baixe_vao_open": False,
            "baixe_ra_open": False,
        }

        # Voice guide (không block luồng chính)
        self.voice_queue: queue.Queue[str] = queue.Queue(maxsize=20)
        self.voice_enabled_runtime = VOICE_GUIDE_ENABLED and pyttsx3 is not None
        self.voice_thread = threading.Thread(target=self._voice_worker_loop, name="Voice-Worker", daemon=True)

        # Kiểm tra dependency tối thiểu trước khi khởi tạo MQTT client.
        self._validate_python_dependencies()

        # Camera: mỗi cổng có thể dùng nguồn riêng
        self.camera_locks = {name: threading.Lock() for name in CAMERA_SOURCES}
        self.camera_caps: Dict[str, Optional[cv2.VideoCapture]] = {name: None for name in CAMERA_SOURCES}

        # Tải model theo kiểu lazy (chỉ load khi cần để giảm thời gian startup)
        self.plate_detector: Optional[Any] = None
        self.ocr_reader: Optional[Any] = None

        # Khởi tạo MQTT client
        self.mqtt_client = self._build_mqtt_client(MQTT_CLIENT_ID)
        if MQTT_USER:
            self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self._configure_mqtt_tls_if_needed()

        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect

        # Worker xử lý tác vụ AI tách riêng theo domain
        self.ktx_worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(self.ktx_event_queue, "ktx"),
            name="AI-Worker-KTX",
            daemon=True,
        )
        self.parking_worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(self.parking_event_queue, "parking"),
            name="AI-Worker-Parking",
            daemon=True,
        )

        if VOICE_GUIDE_ENABLED and pyttsx3 is None:
            self.logger.warning("Đã bật VOICE_GUIDE nhưng thiếu pyttsx3 (%s). Bỏ qua phát âm thanh.", PYTTSX3_IMPORT_ERROR)

    @staticmethod
    def _setup_logger() -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
        )
        return logging.getLogger("SmartDormParkingServer")

    @staticmethod
    def _validate_python_dependencies() -> None:
        missing_deps = []
        if mqtt is None:
            missing_deps.append(f"paho-mqtt ({MQTT_IMPORT_ERROR})")
        if DeepFace is None:
            missing_deps.append(f"deepface ({DEEPFACE_IMPORT_ERROR})")
        if YOLO is None:
            missing_deps.append(f"ultralytics ({YOLO_IMPORT_ERROR})")
        if easyocr is None:
            missing_deps.append(f"easyocr ({EASYOCR_IMPORT_ERROR})")

        if missing_deps:
            joined = "\n- ".join(missing_deps)
            raise RuntimeError(
                "Thiếu dependency Python cần thiết.\n"
                f"- {joined}\n"
                "Hãy cài thư viện bằng requirements.txt trước khi chạy server."
            )

    @staticmethod
    def _build_mqtt_client(client_id: str):
        """Tương thích paho-mqtt 1.x/2.x và tránh warning callback API cũ."""
        if hasattr(mqtt, "CallbackAPIVersion"):
            return mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
                protocol=mqtt.MQTTv311,
            )
        return mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)

    @staticmethod
    def _reason_code_to_int(reason_code) -> int:
        try:
            return int(reason_code)
        except Exception:
            try:
                return int(getattr(reason_code, "value", 1))
            except Exception:
                return 1

    def _configure_mqtt_tls_if_needed(self) -> None:
        """Bật TLS cho MQTT nếu được cấu hình qua biến môi trường."""
        if not MQTT_USE_TLS:
            return

        if MQTT_TLS_CA_CERT:
            self.mqtt_client.tls_set(ca_certs=MQTT_TLS_CA_CERT)
        else:
            self.mqtt_client.tls_set()

        if MQTT_TLS_INSECURE:
            self.mqtt_client.tls_insecure_set(True)

        self.logger.info(
            "MQTT TLS enabled (insecure=%s, ca_cert=%s)",
            MQTT_TLS_INSECURE,
            "set" if MQTT_TLS_CA_CERT else "default",
        )

    # ==========================
    # PHẦN CHẠY CHÍNH
    # ==========================
    def start(self) -> None:
        """Khởi động camera, worker và kết nối MQTT."""
        try:
            self._validate_startup_requirements()
            self._open_cameras()
            self.ktx_worker_thread.start()
            self.parking_worker_thread.start()
            if self.voice_enabled_runtime:
                self.voice_thread.start()

            self.logger.info("Đang kết nối MQTT tới %s:%s ...", MQTT_HOST, MQTT_PORT)
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

            # loop_forever chạy event loop MQTT ở luồng chính, không cần time.sleep().
            self.mqtt_client.loop_forever()

        except KeyboardInterrupt:
            self.logger.warning("Nhận Ctrl+C, đang tắt server...")
        except Exception as error:
            self.logger.exception("Lỗi nghiêm trọng khi khởi động server: %s", error)
            raise
        finally:
            self.stop()

    def stop(self) -> None:
        """Giải phóng tài nguyên hệ thống an toàn."""
        self.stop_event.set()

        try:
            if self.mqtt_client is not None:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
        except Exception as mqtt_error:
            self.logger.warning("Lỗi khi đóng MQTT: %s", mqtt_error)

        if self.ktx_worker_thread.is_alive():
            self.ktx_worker_thread.join(timeout=3)

        if self.parking_worker_thread.is_alive():
            self.parking_worker_thread.join(timeout=3)

        if self.voice_thread.is_alive():
            self.voice_thread.join(timeout=2)

        for name, lock in self.camera_locks.items():
            with lock:
                cap = self.camera_caps.get(name)
                if cap is not None:
                    cap.release()
                    self.camera_caps[name] = None

        cv2.destroyAllWindows()
        self.logger.info("Server đã dừng.")

    def _validate_startup_requirements(self) -> None:
        if not MQTT_HOST:
            raise ValueError("Thiếu MQTT_HOST. Hãy set biến môi trường CloudMQTT trước khi chạy.")

        if MQTT_HOST.strip().lower() in {"your-cloudmqtt-host", "example.com", "localhost.localdomain"}:
            raise ValueError("MQTT_HOST đang là giá trị mẫu. Hãy thay bằng host broker thật.")

        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(
                f"Không tìm thấy DB: {DB_PATH}. Hãy chạy init_db.py trước."
            )

        os.makedirs(FACE_DB_DIR, exist_ok=True)

        self._validate_db_schema()
        self._dong_bo_anh_mau_tu_db()

    @staticmethod
    def _la_url_http(value: str) -> bool:
        lower = value.strip().lower()
        return lower.startswith("http://") or lower.startswith("https://")

    @staticmethod
    def _suy_ra_duoi_anh_tu_url(url_value: str) -> str:
        path = urlsplit(url_value).path or ""
        ext = os.path.splitext(path)[1].lower()
        if ext in VALID_IMAGE_EXTENSIONS:
            return ext
        return ".jpg"

    @staticmethod
    def _tai_anh_url_ve_file(url_value: str, output_path: str) -> None:
        temp_path = f"{output_path}.download"
        with urlopen(url_value, timeout=10) as response:
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if content_type and not content_type.startswith("image/"):
                raise ValueError(f"URL không trả về ảnh (content-type={content_type})")

            data = response.read()
            if not data:
                raise ValueError("URL trả về dữ liệu rỗng")

        with open(temp_path, "wb") as fw:
            fw.write(data)
        os.replace(temp_path, output_path)

    def _dong_bo_anh_mau_tu_db(self) -> None:
        """
        Đồng bộ ảnh mẫu từ DB về thư mục local cho DeepFace:
        - Nếu duong_dan_anh là URL => tải về FACE_DB_DIR với tên <id_sinhvien>.<ext>
        - Nếu là local path/file name => giữ nguyên cơ chế cũ
        """
        conn = None
        tai_moi = 0
        that_bai = 0
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id_sinhvien, duong_dan_anh FROM SinhVien"
            ).fetchall()

            for row in rows:
                student_id = str(row["id_sinhvien"]).strip()
                duong_dan_anh = str(row["duong_dan_anh"] or "").strip()
                if not student_id or not duong_dan_anh:
                    continue

                if not self._la_url_http(duong_dan_anh):
                    continue

                ext = self._suy_ra_duoi_anh_tu_url(duong_dan_anh)
                output_path = os.path.join(FACE_DB_DIR, f"{student_id}{ext}")

                if os.path.exists(output_path):
                    continue

                try:
                    self._tai_anh_url_ve_file(duong_dan_anh, output_path)
                    tai_moi += 1
                except Exception as error:
                    that_bai += 1
                    self.logger.warning(
                        "Không tải được ảnh URL cho %s (%s): %s",
                        student_id,
                        duong_dan_anh,
                        error,
                    )

            if tai_moi > 0:
                self.logger.info("Đồng bộ ảnh URL từ DB thành công: %s ảnh mới", tai_moi)
            elif that_bai == 0:
                self.logger.info("Không có ảnh URL mới cần đồng bộ từ DB.")

            if that_bai > 0:
                self.logger.warning("Đồng bộ ảnh URL có lỗi: %s ảnh tải thất bại", that_bai)
        except sqlite3.Error as db_error:
            self.logger.error("Lỗi truy vấn DB khi đồng bộ ảnh URL: %s", db_error)
        finally:
            if conn:
                conn.close()

    def _validate_db_schema(self) -> None:
        """Đảm bảo DB đã được khởi tạo đúng 3 bảng nghiệp vụ."""
        required_tables = {"SinhVien", "PhuongTien", "LichSu"}
        conn = None
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            existing_tables = {row["name"] for row in rows}
            missing_tables = required_tables - existing_tables
            if missing_tables:
                raise RuntimeError(
                    f"DB thiếu bảng bắt buộc: {sorted(missing_tables)}. Hãy chạy init_db.py trước."
                )
        finally:
            if conn:
                conn.close()

    def _open_cameras(self) -> None:
        for name, source in CAMERA_SOURCES.items():
            if name.lower() in CAMERA_DISABLE_STREAM_KEYS:
                self.camera_caps[name] = None
                self.logger.info("Bỏ qua mở camera %s (disable stream).", name)
                continue
            lock = self.camera_locks[name]
            with lock:
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                if CAMERA_BUFFER_SIZE > 0:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
                if CAMERA_OPEN_TIMEOUT_MS > 0:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CAMERA_OPEN_TIMEOUT_MS)
                if CAMERA_READ_TIMEOUT_MS > 0:
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, CAMERA_READ_TIMEOUT_MS)
                if not cap.isOpened():
                    self.camera_caps[name] = None
                    self.logger.warning("Không mở được camera '%s' source=%s. Bỏ qua camera này.", name, source)
                    continue
                self.camera_caps[name] = cap
            self.logger.info("Đã mở camera %s source=%s", name, source)

    # ==========================
    # MQTT CALLBACKS
    # ==========================
    def on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        rc = self._reason_code_to_int(reason_code)
        if rc == 0:
            self.logger.info("Kết nối MQTT thành công.")
            for topic in SUBSCRIBE_TOPICS:
                client.subscribe(topic, qos=1)
                self.logger.info("Đã subscribe topic: %s", topic)
        else:
            self.logger.error("Kết nối MQTT thất bại, rc=%s, reason=%s", rc, reason_code)

    def on_disconnect(self, client, userdata, disconnect_flags=None, reason_code=0, properties=None) -> None:
        rc = self._reason_code_to_int(reason_code)
        self.logger.warning("MQTT bị ngắt kết nối (rc=%s, reason=%s)", rc, reason_code)

    def on_message(self, client, userdata, msg) -> None:
        """
        Callback MQTT chỉ làm tác vụ nhẹ:
        1) Kiểm tra payload
        2) Chụp frame hiện tại
        3) Đưa event vào queue
        """
        topic = msg.topic
        normalized_topic = self._normalize_sensor_topic(topic)
        payload = msg.payload.decode("utf-8", errors="ignore").strip()

        if topic not in SUBSCRIBE_TOPICS:
            self.logger.debug("Bỏ qua topic không quan tâm: %s", topic)
            return

        event_action = self._phan_loai_su_kien_sensor(topic, payload)
        if event_action is None:
            self.logger.info("Bỏ qua payload '%s' tại topic '%s'", payload, topic)
            return

        if event_action == "AUTH" and normalized_topic in {TOPIC_KTX_SENSOR_VAO, TOPIC_KTX_SENSOR_RA}:
            self._enqueue_voice_prompt(normalized_topic)

        if event_action == "CLOSE":
            event = SensorEvent(topic=normalized_topic, frame=None, timestamp=datetime.now(), action="CLOSE")
            target_queue, queue_name = self._resolve_event_queue(normalized_topic)
            try:
                target_queue.put_nowait(event)
                self.logger.info(
                    "Đã đưa CLOSE event vào queue(%s): raw=%s, normalized=%s | queue_size=%s",
                    queue_name,
                    topic,
                    normalized_topic,
                    target_queue.qsize(),
                )
            except queue.Full:
                self.logger.error("Queue %s đầy! Bỏ CLOSE event để tránh kẹt RAM: %s", queue_name, topic)
                self._insert_log("QUEUE_FULL_DROP", f"{queue_name}:CLOSE:{topic}")
            return

        camera_key = self._camera_key_for_topic(normalized_topic)
        frame = self._capture_frame_fallback(camera_key)
        if frame is None:
            self.logger.error("Không chụp được frame từ camera, bỏ qua event: %s", topic)
            return

        event = SensorEvent(
            topic=normalized_topic,
            frame=frame,
            timestamp=datetime.now(),
            action="AUTH",
            camera_key=camera_key,
        )
        target_queue, queue_name = self._resolve_event_queue(normalized_topic)

        try:
            target_queue.put_nowait(event)
            self.logger.info(
                "Đã đưa AUTH event vào queue(%s): raw=%s, normalized=%s | queue_size=%s",
                queue_name,
                topic,
                normalized_topic,
                target_queue.qsize(),
            )
        except queue.Full:
            self.logger.error("Queue %s đầy! Bỏ event để tránh kẹt RAM: %s", queue_name, topic)
            self._insert_log("QUEUE_FULL_DROP", f"{queue_name}:{topic}")

    def _resolve_event_queue(self, normalized_topic: str) -> Tuple[queue.Queue[SensorEvent], str]:
        if normalized_topic.startswith("saban/ktx/"):
            return self.ktx_event_queue, "ktx"
        if normalized_topic.startswith("saban/baixe/"):
            return self.parking_event_queue, "parking"
        # Fallback an toàn
        return self.ktx_event_queue, "ktx"

    @staticmethod
    def _normalize_sensor_topic(topic: str) -> str:
        """Map topic bãi xe mới (sensor1/sensor2) về topic canonical theo chiều vào/ra."""
        if topic in BAIXE_VAO_SENSOR1_TOPICS or topic == TOPIC_BAIXE_VAO_SENSOR2:
            return TOPIC_BAIXE_SENSOR_VAO
        if topic in BAIXE_RA_SENSOR1_TOPICS or topic == TOPIC_BAIXE_RA_SENSOR2:
            return TOPIC_BAIXE_SENSOR_RA
        return topic

    def _phan_loai_su_kien_sensor(self, topic: str, payload: str) -> Optional[str]:
        """
        Trả về loại sự kiện:
        - AUTH: cần chạy AI xác thực và mở cổng
        - CLOSE: chỉ đóng cổng, không chạy AI
        - None: bỏ qua payload
        """
        if topic in BAIXE_SENSOR2_TOPICS:
            # Bãi xe sensor2 luôn là tín hiệu đóng cổng, dù payload là DETECTED/PASSED.
            if payload in {DETECTED_PAYLOAD, PASSED_PAYLOAD}:
                return "CLOSE"
            return None

        if payload == PASSED_PAYLOAD:
            return "CLOSE"

        if payload != DETECTED_PAYLOAD:
            return None

        # Rule đặc biệt cổng KTX: sensor chéo chỉ đóng cổng nếu chiều đối diện đang mở.
        if topic == TOPIC_KTX_SENSOR_RA and self._is_gate_open("ktx_vao_open"):
            return "CLOSE"
        if topic == TOPIC_KTX_SENSOR_VAO and self._is_gate_open("ktx_ra_open"):
            return "CLOSE"

        return "AUTH"

    @staticmethod
    def _camera_key_for_topic(topic: str) -> str:
        if topic == TOPIC_KTX_SENSOR_VAO:
            return "ktx_in"
        if topic == TOPIC_KTX_SENSOR_RA:
            return "ktx_out"
        if topic == TOPIC_BAIXE_SENSOR_VAO:
            return "parking_in_plate"
        if topic == TOPIC_BAIXE_SENSOR_RA:
            return "parking_out_plate"
        return "ktx_in"

    def _is_gate_open(self, key: str) -> bool:
        with self.gate_state_lock:
            return bool(self.gate_state.get(key, False))

    def _set_gate_state(self, key: str, value: bool) -> None:
        with self.gate_state_lock:
            self.gate_state[key] = value

    def _enqueue_voice_prompt(self, topic: str) -> None:
        if not self.voice_enabled_runtime:
            return

        if topic == TOPIC_KTX_SENSOR_VAO:
            text = "Phát hiện có người vào. Hãy đưa mặt vào camera"
        elif topic == TOPIC_KTX_SENSOR_RA:
            text = "Phát hiện có người ra. Hãy đưa mặt vào camera"
        else:
            return

        try:
            self.voice_queue.put_nowait(text)
        except queue.Full:
            self.logger.warning("Voice queue đầy, bỏ qua thông báo âm thanh.")

    def _enqueue_voice_text(self, text: str) -> None:
        if not self.voice_enabled_runtime:
            return
        if not text:
            return
        try:
            self.voice_queue.put_nowait(text)
        except queue.Full:
            self.logger.warning("Voice queue đầy, bỏ qua thông báo âm thanh tùy biến.")

    def _voice_worker_loop(self) -> None:
        """Luồng phát âm thanh hướng dẫn bằng pyttsx3."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", VOICE_GUIDE_RATE)
            engine.setProperty("volume", max(0.0, min(1.0, VOICE_GUIDE_VOLUME)))
        except Exception as error:
            self.logger.warning("Không khởi tạo được pyttsx3, tắt voice guide: %s", error)
            self.voice_enabled_runtime = False
            return

        while not self.stop_event.is_set():
            try:
                text = self.voice_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as error:
                self.logger.warning("Lỗi phát voice guide: %s", error)
            finally:
                self.voice_queue.task_done()

    def _capture_frame(self, camera_key: str):
        """Chụp nhanh 1 frame từ camera được gán theo key."""
        if CAMERA_SNAPSHOT_FIRST:
            snapshot_frame = self._capture_snapshot_frame(camera_key)
            if snapshot_frame is not None:
                return snapshot_frame
        if camera_key.lower() in CAMERA_DISABLE_STREAM_KEYS:
            return self._capture_snapshot_frame(camera_key)
        lock = self.camera_locks.get(camera_key)
        cap = self.camera_caps.get(camera_key)
        if lock is None or cap is None:
            return None
        with lock:
            ok, frame = cap.read()
            if ok:
                return frame.copy()

            # Nếu đọc fail, thử mở lại stream và đọc lần nữa (mjpeg đôi khi timeout).
            try:
                source = CAMERA_SOURCES.get(camera_key)
                if source is None:
                    return None
                cap.release()
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                if CAMERA_BUFFER_SIZE > 0:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
                if CAMERA_OPEN_TIMEOUT_MS > 0:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CAMERA_OPEN_TIMEOUT_MS)
                if CAMERA_READ_TIMEOUT_MS > 0:
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, CAMERA_READ_TIMEOUT_MS)
                if not cap.isOpened():
                    self.camera_caps[camera_key] = None
                    return None
                self.camera_caps[camera_key] = cap
                ok, frame = cap.read()
                if ok:
                    return frame.copy()
                return self._capture_snapshot_frame(camera_key)
            except Exception:
                return self._capture_snapshot_frame(camera_key)

    def _capture_snapshot_frame(self, camera_key: str):
        snapshot_url = CAMERA_SNAPSHOT_URLS.get(camera_key, "").strip()
        if not snapshot_url:
            return None
        try:
            with urlopen(snapshot_url, timeout=CAMERA_SNAPSHOT_TIMEOUT_MS / 1000) as response:
                data = response.read()
            if not data:
                return None
            image_array = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if frame is None:
                return None
            return frame.copy()
        except Exception:
            return None

    def _capture_frame_fallback(self, camera_key: str, fallback_key: str = "ktx_in"):
        frame = self._capture_frame(camera_key)
        if frame is not None:
            return frame
        return self._capture_frame(fallback_key)

    # ==========================
    # WORKER + XỬ LÝ NGHIỆP VỤ
    # ==========================
    def _worker_loop(self, event_queue: queue.Queue[SensorEvent], pipeline: str) -> None:
        """Luồng worker chạy liên tục để xử lý tác vụ AI/DB theo queue riêng từng pipeline."""
        self.logger.info("Worker thread đã khởi động cho pipeline=%s.", pipeline)

        while not self.stop_event.is_set():
            try:
                event = event_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self._handle_event(event)
            except Exception as error:
                self.logger.exception("Lỗi xử lý event %s: %s", event.topic, error)
                self._insert_log("PROCESS_ERROR", f"{event.topic} | {error}")
            finally:
                event_queue.task_done()

    def _handle_event(self, event: SensorEvent) -> None:
        """Điểm điều phối: chọn pipeline AI theo topic cảm biến."""
        topic = event.topic

        if event.action == "CLOSE":
            da_dong = self._publish_close(topic)
            if da_dong:
                self._insert_log("BARRIER_CLOSED", topic)
            else:
                self._insert_log("BARRIER_CLOSE_SKIPPED", topic)
            return

        if topic.startswith("saban/ktx/"):
            is_valid, identity = self._process_ktx_access(event.frame, event.camera_key)
            if is_valid:
                self._publish_open(topic)
                self._insert_log("KTX_ACCESS_GRANTED", identity)
                student = self._get_student(identity)
                ho_ten = student["ho_ten"] if student and "ho_ten" in student else identity
                self._enqueue_voice_text(
                    f"Xác thực khuôn mặt thành công. Mời sinh viên {ho_ten} đi qua cổng"
                )
            else:
                self._insert_log("KTX_ACCESS_DENIED", identity)
                self._enqueue_voice_text(
                    "Xác thực thất bại. Vui lòng nhìn thẳng camera và thử lại"
                )
            return

        if topic.startswith("saban/baixe/"):
            face_frame = None
            if topic == TOPIC_BAIXE_SENSOR_RA:
                face_frame = self._capture_frame_fallback("parking_out_face")
            is_valid, plate_no = self._process_parking_access(topic, event.frame, face_frame)
            if is_valid:
                self._publish_open(topic)
                self._insert_log("PARKING_ACCESS_GRANTED", plate_no)
            else:
                self._insert_log("PARKING_ACCESS_DENIED", plate_no)
            return

        self.logger.warning("Topic không có pipeline xử lý: %s", topic)

    # ==========================
    # AI KHUÔN MẶT (KTX)
    # ==========================
    def _process_ktx_access(self, frame, camera_key: Optional[str]) -> Tuple[bool, str]:
        """
        Nhận diện khuôn mặt bằng DeepFace.find với model Facenet.
        Trả về:
        - (True, id_sinhvien) nếu hợp lệ
        - (False, ly_do_hoac_id) nếu từ chối
        """
        student_id = self._recognize_face_with_retry(frame, camera_key)
        if not student_id:
            return False, "UNKNOWN_FACE"

        student = self._get_student(student_id)
        if not student:
            return False, f"NOT_IN_DB:{student_id}"

        return True, student["id_sinhvien"]

    def _recognize_face_with_retry(self, frame, camera_key: Optional[str]) -> Optional[str]:
        """Thử nhận diện khuôn mặt nhiều lần trước khi kết luận thất bại."""
        current_frame = frame

        for lan_thu in range(FACE_RETRY_COUNT):
            student_id = self._recognize_face_student_id(current_frame)
            if student_id:
                if lan_thu > 0:
                    self.logger.info("Face match thành công ở lần thử %s/%s", lan_thu + 1, FACE_RETRY_COUNT)
                return student_id

            if lan_thu < FACE_RETRY_COUNT - 1:
                self.logger.info(
                    "Face match thất bại lần %s/%s. Sẽ thử lại sau %sms...",
                    lan_thu + 1,
                    FACE_RETRY_COUNT,
                    FACE_RETRY_INTERVAL_MS,
                )
                if FACE_RETRY_INTERVAL_MS > 0:
                    self.stop_event.wait(FACE_RETRY_INTERVAL_MS / 1000.0)
                if camera_key:
                    frame_moi = self._capture_frame_fallback(camera_key)
                else:
                    frame_moi = None
                if frame_moi is not None:
                    current_frame = frame_moi

        return None

    def _recognize_face_student_id(self, frame) -> Optional[str]:
        temp_path = os.path.join(BASE_DIR, f"temp_face_{uuid.uuid4().hex}.jpg")

        try:
            if not self._co_anh_mau_khuon_mat():
                self.logger.error(
                    "Không có ảnh mẫu hợp lệ trong %s. Hãy thêm ảnh .jpg/.png có khuôn mặt rõ.",
                    FACE_DB_DIR,
                )
                return None

            cv2.imwrite(temp_path, frame)

            try:
                results = self._deepface_find_with_retry(temp_path)
            except Exception as error:
                if "No item found in" in str(error):
                    self.logger.warning(
                        "DeepFace.find không tạo được datasource. Chuyển sang verify từng ảnh mẫu..."
                    )
                    ket_qua_verify = self._tim_khop_khuon_mat_theo_verify(temp_path)
                    if ket_qua_verify:
                        return ket_qua_verify
                raise

            # DeepFace.find trả list DataFrame; kiểm tra có match hay không.
            if not results or len(results[0]) == 0:
                return None

            matched_identity_path = str(results[0]["identity"][0])
            filename = os.path.basename(matched_identity_path)
            student_id = self._resolve_student_id_from_face_filename(filename)
            return student_id

        except Exception as error:
            self.logger.error("Lỗi DeepFace: %s", error)
            return None
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    @staticmethod
    def _lay_danh_sach_anh_khuon_mat() -> list[str]:
        ds_anh: list[str] = []
        for root, _, files in os.walk(FACE_DB_DIR):
            for file_name in files:
                if os.path.splitext(file_name)[1].lower() in VALID_IMAGE_EXTENSIONS:
                    ds_anh.append(os.path.join(root, file_name))
        return ds_anh

    def _tim_khop_khuon_mat_theo_verify(self, temp_path: str) -> Optional[str]:
        ds_anh = self._lay_danh_sach_anh_khuon_mat()
        if not ds_anh:
            return None

        ung_vien_tot_nhat = None
        for anh_mau in ds_anh:
            try:
                kq = DeepFace.verify(
                    img1_path=temp_path,
                    img2_path=anh_mau,
                    model_name="Facenet",
                    detector_backend="opencv",
                    enforce_detection=False,
                    silent=True,
                )

                if kq.get("verified"):
                    distance = float(kq.get("distance", 999))
                    if ung_vien_tot_nhat is None or distance < ung_vien_tot_nhat["distance"]:
                        ung_vien_tot_nhat = {"path": anh_mau, "distance": distance}
            except Exception:
                continue

        if not ung_vien_tot_nhat:
            return None

        file_name = os.path.basename(ung_vien_tot_nhat["path"])
        return self._resolve_student_id_from_face_filename(file_name)

    @staticmethod
    def _co_anh_mau_khuon_mat() -> bool:
        try:
            for root, _, files in os.walk(FACE_DB_DIR):
                for file_name in files:
                    if os.path.splitext(file_name)[1].lower() in VALID_IMAGE_EXTENSIONS:
                        return True
        except OSError:
            return False
        return False

    @staticmethod
    def _xoa_cache_deepface() -> bool:
        da_xoa = False
        try:
            for file_name in os.listdir(FACE_DB_DIR):
                if file_name.startswith("ds_model_") and file_name.endswith(".pkl"):
                    os.remove(os.path.join(FACE_DB_DIR, file_name))
                    da_xoa = True
        except OSError:
            return False
        return da_xoa

    def _deepface_find_with_retry(self, temp_path: str):
        for lan_thu in range(2):
            try:
                return DeepFace.find(
                    img_path=temp_path,
                    db_path=FACE_DB_DIR,
                    model_name="Facenet",
                    enforce_detection=False,
                    detector_backend="opencv",
                    silent=True,
                )
            except Exception as error:
                noi_dung_loi = str(error)
                la_loi_db_rong = "No item found in" in noi_dung_loi
                if la_loi_db_rong and lan_thu == 0:
                    da_xoa = self._xoa_cache_deepface()
                    if da_xoa:
                        self.logger.warning(
                            "DeepFace báo DB rỗng. Đã xóa cache embedding và thử lại..."
                        )
                    else:
                        self.logger.warning(
                            "DeepFace báo DB rỗng. Không tìm thấy cache để xóa, vẫn thử lại..."
                        )
                    continue

                if la_loi_db_rong:
                    self.logger.error(
                        "DeepFace không thấy ảnh hợp lệ trong %s. Kiểm tra lại ảnh mẫu khuôn mặt.",
                        FACE_DB_DIR,
                    )
                raise

    # ==========================
    # AI BIỂN SỐ (BÃI XE)
    # ==========================
    def _process_parking_access(self, topic: str, plate_frame, face_frame=None) -> Tuple[bool, str]:
        """
        Nhận diện biển số bằng YOLOv8 + EasyOCR.
        Kiểm tra DB + cập nhật trạng thái xe theo luồng vào/ra.
        """
        plate = self._recognize_plate(plate_frame)
        if not plate:
            return False, "NO_PLATE"

        vehicle = self._get_vehicle(plate)
        if not vehicle:
            return False, f"PLATE_NOT_REGISTERED:{plate}"

        current_status = vehicle["trang_thai"]

        if topic == TOPIC_BAIXE_SENSOR_VAO:
            if current_status == "Trong_Bai":
                return False, f"ALREADY_IN:{plate}"
            self._update_vehicle_status(plate, "Trong_Bai")
            return True, plate

        if topic == TOPIC_BAIXE_SENSOR_RA:
            if current_status == "Ngoai_Bai":
                return False, f"ALREADY_OUT:{plate}"
            if face_frame is None:
                return False, f"NO_FACE_FRAME:{plate}"

            face_student_id = self._recognize_face_with_retry(face_frame, "parking_out_face")
            if not face_student_id:
                return False, f"UNKNOWN_FACE:{plate}"

            if face_student_id != vehicle["id_sinhvien"]:
                return False, f"FACE_PLATE_MISMATCH:{plate}:{face_student_id}"
            self._update_vehicle_status(plate, "Ngoai_Bai")
            return True, plate

        return False, f"INVALID_TOPIC:{topic}"

    def _recognize_plate(self, frame) -> Optional[str]:
        """
        Pipeline OCR biển số:
        1) Dùng YOLO detect vùng biển số (nếu có)
        2) OCR từng vùng bằng EasyOCR
        3) Chuẩn hóa chuỗi biển số
        """
        try:
            detector = self._get_plate_detector()
            ocr = self._get_ocr_reader()

            candidates = []

            # Dự đoán YOLO: kỳ vọng model được train để detect plate.
            detections = detector.predict(source=frame, conf=0.25, verbose=False)

            for det in detections:
                if det.boxes is None:
                    continue
                for box in det.boxes.xyxy.tolist():
                    x1, y1, x2, y2 = [int(v) for v in box]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = max(x1 + 1, x2), max(y1 + 1, y2)
                    plate_crop = frame[y1:y2, x1:x2]
                    text = self._read_plate_text(ocr, plate_crop)
                    if text:
                        candidates.append(text)

            # Fallback: nếu YOLO không tìm thấy box, OCR toàn frame (demo).
            if not candidates:
                fallback_text = self._read_plate_text(ocr, frame)
                if fallback_text:
                    candidates.append(fallback_text)

            if not candidates:
                return None

            # Chọn candidate dài nhất (thường chứa đủ ký tự biển số hơn).
            candidates.sort(key=len, reverse=True)
            return candidates[0]

        except Exception as error:
            self.logger.error("Lỗi nhận diện biển số: %s", error)
            return None

    @staticmethod
    def _read_plate_text(ocr_reader, img) -> Optional[str]:
        results = ocr_reader.readtext(img)
        if not results:
            return None

        texts = [item[1] for item in results if len(item) >= 2]
        if not texts:
            return None

        joined = "".join(texts)
        normalized = re.sub(r"[^A-Za-z0-9]", "", joined).upper()

        # Biển số Việt Nam thường >= 6 ký tự sau khi normalize.
        if len(normalized) < 6:
            return None
        return normalized

    def _get_plate_detector(self):
        if self.plate_detector is None:
            self.logger.info("Đang load YOLO model: %s", YOLO_MODEL_PATH)
            self.plate_detector = YOLO(YOLO_MODEL_PATH)
        return self.plate_detector

    def _get_ocr_reader(self):
        if self.ocr_reader is None:
            self.logger.info("Đang khởi tạo EasyOCR reader...")
            self.ocr_reader = easyocr.Reader(["en"], gpu=False)
        return self.ocr_reader

    # ==========================
    # MQTT PUBLISH
    # ==========================
    def _publish_open(self, sensor_topic: str) -> None:
        servo_topic = SERVO_TOPIC_MAP.get(sensor_topic)
        if not servo_topic:
            self.logger.error("Không có servo topic cho sensor topic: %s", sensor_topic)
            return

        info = self.mqtt_client.publish(servo_topic, payload="OPEN", qos=1)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            self.logger.info("Đã publish OPEN -> %s", servo_topic)
            self._cap_nhat_trang_thai_cong_mo(sensor_topic)
        else:
            self.logger.error("Publish thất bại tới %s, rc=%s", servo_topic, info.rc)

    def _publish_close(self, sensor_topic: str) -> bool:
        servo_topic = SERVO_TOPIC_MAP.get(sensor_topic)
        if not servo_topic:
            self.logger.error("Không có servo topic cho sensor topic: %s", sensor_topic)
            return False

        huong_dong = self._xac_dinh_huong_dong(sensor_topic)
        if huong_dong is None:
            self.logger.info("Bỏ qua CLOSE vì không có cổng nào đang mở phù hợp tại topic: %s", sensor_topic)
            return False

        info = self.mqtt_client.publish(servo_topic, payload="CLOSE", qos=1)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            self.logger.info("Đã publish CLOSE -> %s (huong=%s)", servo_topic, huong_dong)
            self._set_gate_state(huong_dong, False)
            return True

        self.logger.error("Publish CLOSE thất bại tới %s, rc=%s", servo_topic, info.rc)
        return False

    def _cap_nhat_trang_thai_cong_mo(self, sensor_topic: str) -> None:
        if sensor_topic == TOPIC_KTX_SENSOR_VAO:
            self._set_gate_state("ktx_vao_open", True)
        elif sensor_topic == TOPIC_KTX_SENSOR_RA:
            self._set_gate_state("ktx_ra_open", True)
        elif sensor_topic == TOPIC_BAIXE_SENSOR_VAO:
            self._set_gate_state("baixe_vao_open", True)
        elif sensor_topic == TOPIC_BAIXE_SENSOR_RA:
            self._set_gate_state("baixe_ra_open", True)

    def _xac_dinh_huong_dong(self, sensor_topic: str) -> Optional[str]:
        """
        Chọn cổng cần đóng dựa trên topic cảm biến và trạng thái hiện tại.
        Rule KTX đặc biệt:
        - sensor_ra có thể là sensor2 của chiều vào => đóng ktx_vao_open nếu đang mở
        - sensor_vao có thể là sensor2 của chiều ra => đóng ktx_ra_open nếu đang mở
        """
        if sensor_topic == TOPIC_KTX_SENSOR_RA:
            if self._is_gate_open("ktx_vao_open"):
                return "ktx_vao_open"
            if self._is_gate_open("ktx_ra_open"):
                return "ktx_ra_open"
            return None

        if sensor_topic == TOPIC_KTX_SENSOR_VAO:
            if self._is_gate_open("ktx_ra_open"):
                return "ktx_ra_open"
            if self._is_gate_open("ktx_vao_open"):
                return "ktx_vao_open"
            return None

        if sensor_topic == TOPIC_BAIXE_SENSOR_VAO:
            return "baixe_vao_open" if self._is_gate_open("baixe_vao_open") else None

        if sensor_topic == TOPIC_BAIXE_SENSOR_RA:
            return "baixe_ra_open" if self._is_gate_open("baixe_ra_open") else None

        return None

    # ==========================
    # SQLITE HELPERS
    # ==========================
    @staticmethod
    def _get_conn() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT id_sinhvien, ho_ten, duong_dan_anh FROM SinhVien WHERE id_sinhvien = ?",
                (student_id,),
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as db_error:
            self.logger.error("Lỗi truy vấn SinhVien: %s", db_error)
            return None
        finally:
            if conn:
                conn.close()

    def _resolve_student_id_from_face_filename(self, filename: str) -> Optional[str]:
        """
        Mapping kết quả DeepFace -> id_sinhvien.
        Ưu tiên khớp theo id_sinhvien, fallback theo duong_dan_anh.
        """
        stem = os.path.splitext(filename)[0]
        conn = None
        try:
            conn = self._get_conn()
            row = conn.execute(
                """
                SELECT id_sinhvien
                FROM SinhVien
                WHERE id_sinhvien = ?
                   OR LOWER(duong_dan_anh) = LOWER(?)
                   OR LOWER(duong_dan_anh) LIKE LOWER(?)
                   OR LOWER(duong_dan_anh) LIKE LOWER(?)
                LIMIT 1
                """,
                (stem, filename, f"%/{filename}", f"%\\{filename}"),
            ).fetchone()

            if row:
                return row["id_sinhvien"]
            return stem
        except sqlite3.Error as db_error:
            self.logger.error("Lỗi resolve student_id từ filename: %s", db_error)
            return stem
        finally:
            if conn:
                conn.close()

    def _get_vehicle(self, plate: str) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT bien_so, id_sinhvien, trang_thai FROM PhuongTien WHERE bien_so = ?",
                (plate,),
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as db_error:
            self.logger.error("Lỗi truy vấn PhuongTien: %s", db_error)
            return None
        finally:
            if conn:
                conn.close()

    def _update_vehicle_status(self, plate: str, new_status: str) -> None:
        conn = None
        try:
            conn = self._get_conn()
            conn.execute(
                "UPDATE PhuongTien SET trang_thai = ? WHERE bien_so = ?",
                (new_status, plate),
            )
            conn.commit()
            self.logger.info("Đã cập nhật trạng thái xe %s -> %s", plate, new_status)
        except sqlite3.Error as db_error:
            self.logger.error("Lỗi cập nhật trạng thái xe: %s", db_error)
        finally:
            if conn:
                conn.close()

    def _insert_log(self, su_kien: str, doi_tuong: str) -> None:
        conn = None
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO LichSu (su_kien, doi_tuong) VALUES (?, ?)",
                (su_kien, doi_tuong),
            )
            conn.commit()
        except sqlite3.Error as db_error:
            self.logger.error("Lỗi ghi log SQLite: %s", db_error)
        finally:
            if conn:
                conn.close()


def main() -> None:
    server = SmartDormParkingServer()
    server.start()


if __name__ == "__main__":
    main()
