# He thong quan ly ra vao KTX va bai xe thong minh

Du an mo phong he thong kiem soat ra vao ky tuc xa va bai do xe bang ESP32, MQTT, camera va xu ly AI tren server Python. He thong nhan tin hieu tu cam bien hong ngoai, chup anh bang camera, xac thuc khuon mat hoac bien so, sau do gui lenh dieu khien servo mo/dong cong.

## Tinh nang chinh

- Kiem soat cong KTX bang nhan dien khuon mat.
- Kiem soat cong vao bai xe bang nhan dien bien so xe.
- Kiem soat cong ra bai xe bang bien so xe ket hop xac thuc khuon mat chu xe.
- Giao tiep giua ESP32 va server bang MQTT.
- Dieu khien 3 servo rieng biet: cong KTX, cong vao bai xe, cong ra bai xe.
- Tu dong dong cong khi xe/nguoi da di qua cam bien sau cong hoac khi het thoi gian timeout.
- Luu lich su su kien vao SQLite.
- Dashboard Flask de quan ly sinh vien, phuong tien va xem lich su.
- Co simulator MQTT de test luong server khi chua co phan cung that.

## Kien truc tong quan

```text
Cam bien IR / ESP32
        |
        | MQTT DETECTED / PASSED
        v
MQTT Broker
        |
        v
Server Python
  - MQTT Client
  - Camera Worker
  - AI Worker
  - Queue xu ly su kien
  - SQLite
        |
        | MQTT OPEN / CLOSE
        v
ESP32 dieu khien Servo
```

## Cau truc thu muc

```text
.
|-- main_server.py                  # Server xu ly MQTT, camera, AI va dieu khien cong
|-- init_db.py                      # Tao database SQLite ban dau
|-- smoke_test.py                   # Kiem tra nhanh cau hinh va cac module chinh
|-- esp32_mqtt_simulator.py         # Gia lap ESP32 bang MQTT
|-- ai_visual_test.py               # Test minh hoa AI de chup anh bao cao
|-- face_capture_report_test.py     # Test chup khuon mat cho bao cao
|-- dashboard/
|   |-- app.py                      # Dashboard Flask
|   `-- README.md
|-- esp32_firmware/
|   `-- ktx_baixe_esp32/
|       |-- ktx_baixe_esp32.ino     # Firmware nap vao ESP32
|       `-- README.md
|-- data/                           # Du lieu mau, anh khuon mat, database
|-- requirements.txt
|-- .env.example
`-- tomtat.md                       # Tom tat phan cung va dau noi
```

## Cau hinh moi truong

Tao file `.env` tu file mau:

```powershell
Copy-Item .\.env.example .\.env
```

Cap nhat cac bien can thiet trong `.env`:

| Bien | Y nghia |
| --- | --- |
| `MQTT_HOST` | Dia chi MQTT broker |
| `MQTT_PORT` | Cong MQTT, thuong la `8883` neu dung TLS |
| `MQTT_USER` | Tai khoan MQTT |
| `MQTT_PASSWORD` | Mat khau MQTT |
| `MQTT_USE_TLS` | `1` neu broker dung TLS |
| `CAMERA_KTX_IN_URL` | Camera nhan dien mat cong vao KTX |
| `CAMERA_KTX_OUT_URL` | Camera nhan dien mat cong ra KTX |
| `CAMERA_PARK_IN_PLATE_URL` | Camera bien so cong vao bai xe |
| `CAMERA_PARK_OUT_PLATE_URL` | Camera bien so cong ra bai xe |
| `CAMERA_PARK_OUT_FACE_URL` | Camera khuon mat cong ra bai xe |
| `YOLO_MODEL_PATH` | Duong dan model phat hien bien so |
| `FACE_RETRY_COUNT` | So lan thu lai khi xac thuc khuon mat that bai |
| `GATE_AUTO_CLOSE_TIMEOUT_SEC` | Thoi gian tu dong dong cong neu khong co tin hieu di qua |

Khong commit file `.env` len GitHub vi file nay co the chua tai khoan MQTT, URL camera va cac thong tin rieng tu.

## MQTT topics

### ESP32 gui len server

| Topic | Payload | Y nghia |
| --- | --- | --- |
| `saban/ktx/sensor_vao` | `DETECTED` | Cam bien truoc cong KTX phat hien nguoi |
| `saban/ktx/sensor_ra` | `PASSED` | Cam bien sau cong KTX xac nhan da di qua |
| `saban/baixe/vao/sensor1` | `DETECTED` | Cam bien truoc cong vao bai xe phat hien xe |
| `saban/baixe/vao/sensor2` | `PASSED` | Cam bien sau cong vao bai xe xac nhan xe da qua |
| `saban/baixe/ra/sensor1` | `DETECTED` | Cam bien truoc cong ra bai xe phat hien xe |
| `saban/baixe/ra/sensor2` | `PASSED` | Cam bien sau cong ra bai xe xac nhan xe da qua |

Server van ho tro cac topic cu `saban/baixe/sensor_vao` va `saban/baixe/sensor_ra` de tuong thich nguoc.

### Server gui len ESP32

| Topic | Payload | Y nghia |
| --- | --- | --- |
| `saban/ktx/servo` | `OPEN` / `CLOSE` | Mo hoac dong cong KTX |
| `saban/baixe/servo_vao` | `OPEN` / `CLOSE` | Mo hoac dong cong vao bai xe |
| `saban/baixe/servo_ra` | `OPEN` / `CLOSE` | Mo hoac dong cong ra bai xe |

## Luong hoat dong

### Cong KTX

1. Cam bien truoc cong KTX phat hien nguoi va gui `DETECTED`.
2. Server chup anh tu camera KTX.
3. Server xac thuc khuon mat bang anh trong database.
4. Neu hop le, server publish `OPEN` toi `saban/ktx/servo`.
5. ESP32 quay servo mo cong.
6. Khi cam bien sau cong phat hien nguoi da di qua, ESP32 gui `PASSED`.
7. Server publish `CLOSE` de dong cong.
8. Neu khong co `PASSED`, server tu dong dong cong sau timeout.

### Cong vao bai xe

1. Cam bien truoc cong vao bai xe gui `DETECTED`.
2. Server chup anh bien so.
3. Server phat hien vung bien so bang YOLO va doc ky tu bang OCR.
4. Bien so doc duoc duoc chuan hoa truoc khi so sanh voi database.
5. Neu bien so da dang ky, server mo servo cong vao bai xe.
6. Cam bien sau cong gui `PASSED` khi xe di qua.
7. Server dong cong va cap nhat lich su.

### Cong ra bai xe

1. Cam bien truoc cong ra gui `DETECTED`.
2. Server doc bien so xe.
3. Server xac dinh sinh vien so huu phuong tien trong database.
4. Server chup va xac thuc khuon mat nguoi lay xe.
5. Neu bien so va khuon mat khop, server mo servo cong ra.
6. Cam bien sau cong gui `PASSED`, server dong cong va ghi lich su.

## Cai dat va chay server

Cai dat thu vien:

```powershell
pip install -r .\requirements.txt
```

Khoi tao database:

```powershell
python .\init_db.py
```

Chay kiem tra nhanh:

```powershell
python .\smoke_test.py
```

Chay server chinh:

```powershell
python .\main_server.py
```

## Chay dashboard

```powershell
python .\dashboard\app.py
```

Mo trinh duyet tai:

```text
http://127.0.0.1:5001
```

Dashboard dung de xem lich su ra vao, them/sua/xoa sinh vien va quan ly phuong tien.

## Test khong can phan cung

Co the dung file simulator de gia lap ESP32:

```powershell
python .\esp32_mqtt_simulator.py
```

Lenh trong simulator:

| Lenh | Chuc nang |
| --- | --- |
| `1` | Gia lap cam bien KTX phat hien nguoi |
| `2` | Gia lap cam bien KTX xac nhan da di qua |
| `3` | Gia lap cam bien cong vao bai xe phat hien xe |
| `4` | Gia lap cam bien cong ra bai xe phat hien xe |
| `c1` | Gui tin hieu dong cong KTX |
| `c2` | Gui tin hieu dong cong vao bai xe |
| `c3` | Gui tin hieu dong cong ra bai xe |
| `all` | Gui nhieu su kien test lien tiep |

## Luu y khi dua len GitHub

- Khong dua file `.env`, database that, anh khuon mat that hoac URL camera noi bo len repository cong khai.
- Dung `.env.example` de mo ta cau hinh can thiet.
- Neu can dua anh minh hoa len bao cao, nen dung anh demo hoac anh da che thong tin ca nhan.
- Neu su dung model AI rieng, nen ghi ro cach tai model thay vi commit file model dung luong lon.

## Su co thuong gap

| Hien tuong | Huong kiem tra |
| --- | --- |
| MQTT bao `rc=5` | Sai username/password, sai port, sai TLS hoac broker chua cho phep ket noi |
| Khong thay message tren HiveMQ | Kiem tra topic subscribe `saban/#`, WiFi ESP32 va MQTT broker |
| Servo chi quay mot lan | Kiem tra nguon servo, noi chung GND voi ESP32, test topic `OPEN`/`CLOSE` dung servo |
| Cam bien LM393 bi nguoc trang thai | Doi gia tri `SENSOR_ACTIVE_LOW` trong firmware |
| Bien so doc sai chu cai/so | Kiem tra anh co ro net, goc chup, anh sang va logic chuan hoa bien so |
