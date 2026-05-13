import argparse
import os
import sys
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "0").strip().lower() in {"1", "true", "yes", "on"}
MQTT_TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "0").strip().lower() in {"1", "true", "yes", "on"}
MQTT_TLS_CA_CERT = os.getenv("MQTT_TLS_CA_CERT", "").strip()


TOPIC_KTX_SENSOR_VAO = "saban/ktx/sensor_vao"
TOPIC_KTX_SENSOR_RA = "saban/ktx/sensor_ra"
TOPIC_BAIXE_SENSOR_VAO = "saban/baixe/sensor_vao"
TOPIC_BAIXE_SENSOR_RA = "saban/baixe/sensor_ra"
TOPIC_BAIXE_VAO_SENSOR1 = "saban/baixe/vao/sensor1"
TOPIC_BAIXE_VAO_SENSOR2 = "saban/baixe/vao/sensor2"
TOPIC_BAIXE_RA_SENSOR1 = "saban/baixe/ra/sensor1"
TOPIC_BAIXE_RA_SENSOR2 = "saban/baixe/ra/sensor2"

TOPIC_KTX_SERVO = "saban/ktx/servo"
TOPIC_BAIXE_SERVO_VAO = "saban/baixe/servo_vao"
TOPIC_BAIXE_SERVO_RA = "saban/baixe/servo_ra"

ALL_SENSOR_TOPICS = {
    "ktx_vao": TOPIC_KTX_SENSOR_VAO,
    "ktx_ra": TOPIC_KTX_SENSOR_RA,
    "baixe_vao": TOPIC_BAIXE_VAO_SENSOR1,
    "baixe_ra": TOPIC_BAIXE_RA_SENSOR1,
    "baixe_vao_close": TOPIC_BAIXE_VAO_SENSOR2,
    "baixe_ra_close": TOPIC_BAIXE_RA_SENSOR2,
}

ALL_SERVO_TOPICS = [
    TOPIC_KTX_SERVO,
    TOPIC_BAIXE_SERVO_VAO,
    TOPIC_BAIXE_SERVO_RA,
]

PAYLOAD_DETECTED = "DETECTED"
PAYLOAD_PASSED = "PASSED"


class ESP32MqttSimulator:
    """
    Mô phỏng ESP32 để test end-to-end:
    - Publish sự kiện cảm biến DETECTED
    - Subscribe topic servo để nhận lệnh OPEN từ server
    """

    def __init__(self, host: str, port: int, username: str, password: str, client_id: str) -> None:
        self.host = host
        self.port = port
        self.stop_event = threading.Event()

        self.client = self._build_mqtt_client(client_id)
        if username:
            self.client.username_pw_set(username, password)
        self._configure_tls_if_needed()

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    @staticmethod
    def _build_mqtt_client(client_id: str):
        """Tương thích cả paho-mqtt 1.x và 2.x (tránh warning callback API)."""
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

    def _configure_tls_if_needed(self) -> None:
        if not MQTT_USE_TLS:
            return

        if MQTT_TLS_CA_CERT:
            self.client.tls_set(ca_certs=MQTT_TLS_CA_CERT)
        else:
            self.client.tls_set()

        if MQTT_TLS_INSECURE:
            self.client.tls_insecure_set(True)

        print(
            f"[INFO] MQTT TLS enabled (insecure={MQTT_TLS_INSECURE}, ca_cert={'set' if MQTT_TLS_CA_CERT else 'default'})"
        )

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = self._reason_code_to_int(reason_code)
        if rc == 0:
            print(f"[OK] Kết nối MQTT thành công tới {self.host}:{self.port}")
            for topic in ALL_SERVO_TOPICS:
                client.subscribe(topic, qos=1)
                print(f"[SUB] {topic}")
        else:
            print(f"[LOI] Kết nối MQTT thất bại, rc={rc}, reason={reason_code}")

    def on_disconnect(self, client, userdata, disconnect_flags=None, reason_code=0, properties=None):
        rc = self._reason_code_to_int(reason_code)
        print(f"[WARN] MQTT ngắt kết nối, rc={rc}, reason={reason_code}")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="ignore").strip()
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [SERVO<-SERVER] Topic={msg.topic} | Payload={payload}")

    def start(self) -> None:
        try:
            self.client.connect(self.host, self.port, keepalive=60)
        except OSError as error:
            if getattr(error, "errno", None) == 11001:
                raise RuntimeError(
                    f"Không phân giải được MQTT host '{self.host}'. "
                    "Bạn đang dùng host mẫu hoặc host sai. Hãy điền host CloudMQTT thật trong .env hoặc --host."
                ) from error
            raise
        self.client.loop_start()

    def stop(self) -> None:
        self.stop_event.set()
        self.client.loop_stop()
        self.client.disconnect()

    def send_sensor_event(self, sensor_key: str, payload: str) -> None:
        topic = ALL_SENSOR_TOPICS[sensor_key]
        info = self.client.publish(topic, payload=payload, qos=1)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[SENT] {payload} -> {topic}")
        else:
            print(f"[LOI] Publish thất bại -> {topic}, rc={info.rc}")



def interactive_mode(sim: ESP32MqttSimulator) -> None:
    help_text = """
=== ESP32 MQTT SIMULATOR ===
Nhập lệnh:
    1  -> DETECTED: KTX vào (sensor1)
    2  -> DETECTED: KTX ra (sensor1)
    3  -> DETECTED: Bãi xe vào (topic mới: vao/sensor1)
    4  -> DETECTED: Bãi xe ra (topic mới: ra/sensor1)
    c1 -> PASSED: KTX vào (sensor2)
    c2 -> PASSED: KTX ra (sensor2)
    c3 -> PASSED: Bãi xe vào (topic mới: vao/sensor2)
    c4 -> PASSED: Bãi xe ra (topic mới: ra/sensor2)
    all -> Gửi tuần tự 4 DETECTED
  q  -> Thoát
===========================
"""
    print(help_text)

    mapping = {
        "1": "ktx_vao",
        "2": "ktx_ra",
        "3": "baixe_vao",
        "4": "baixe_ra",
    }

    while not sim.stop_event.is_set():
        cmd = input("Lenh> ").strip().lower()
        if cmd == "q":
            break
        if cmd == "all":
            for key in ["ktx_vao", "ktx_ra", "baixe_vao", "baixe_ra"]:
                sim.send_sensor_event(key, PAYLOAD_DETECTED)
                time.sleep(0.3)
            continue

        if cmd.startswith("c") and len(cmd) == 2 and cmd[1] in mapping:
            if cmd[1] in {"3", "4"}:
                close_key = "baixe_vao_close" if cmd[1] == "3" else "baixe_ra_close"
                sim.send_sensor_event(close_key, PAYLOAD_PASSED)
            else:
                sim.send_sensor_event(mapping[cmd[1]], PAYLOAD_PASSED)
            continue

        if cmd in mapping:
            sim.send_sensor_event(mapping[cmd], PAYLOAD_DETECTED)
            continue
        print("Lệnh không hợp lệ. Nhập 1/2/3/4/c1/c2/c3/c4/all/q")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mô phỏng ESP32 gửi sensor MQTT và nhận lệnh servo từ server"
    )
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", ""), help="MQTT host")
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")), help="MQTT port")
    parser.add_argument("--user", default=os.getenv("MQTT_USER", ""), help="MQTT username")
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD", ""), help="MQTT password")
    parser.add_argument(
        "--client-id",
        default=f"esp32-sim-{int(time.time())}",
        help="MQTT client id",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.host:
        print("[LOI] Thiếu MQTT host. Hãy truyền --host hoặc set biến môi trường MQTT_HOST")
        return 1
    if args.host.strip().lower() in {"your-cloudmqtt-host", "example.com", "localhost.localdomain"}:
        print("[LOI] Bạn đang dùng host mẫu. Hãy thay bằng host CloudMQTT thật.")
        return 1

    sim = ESP32MqttSimulator(
        host=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        client_id=args.client_id,
    )

    try:
        sim.start()
        interactive_mode(sim)
        return 0
    except KeyboardInterrupt:
        print("\n[INFO] Người dùng dừng simulator.")
        return 0
    except Exception as error:
        print(f"[LOI] Simulator gặp lỗi: {error}")
        return 1
    finally:
        sim.stop()


if __name__ == "__main__":
    sys.exit(main())
