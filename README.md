# Hệ thống quản lý KTX & Bãi đỗ xe thông minh (Server Python)

Server Python xử lý event từ ESP32 qua MQTT, chạy AI nhận diện khuôn mặt/biển số, xác thực SQLite và điều khiển servo mở/đóng cổng.

Server có hỗ trợ phát âm thanh hướng dẫn tại cổng KTX khi nhận `DETECTED`:
- "Phát hiện có người vào. Hãy đưa mặt vào camera"
- "Phát hiện có người ra. Hãy đưa mặt vào camera"

Khi xác thực khuôn mặt thành công ở cổng KTX, server sẽ phát thêm:
- "Xác thực khuôn mặt thành công. Mời sinh viên <Họ tên> đi qua cổng"

Khi xác thực khuôn mặt thất bại ở cổng KTX, server sẽ phát:
- "Xác thực thất bại. Vui lòng nhìn thẳng camera và thử lại"

## Kiến trúc tổng quan

- **Input event** từ ESP32 qua MQTT (`DETECTED`, `PASSED`)
- **`on_message` nhẹ**: chụp frame + route event vào queue phù hợp
- **2 worker thread tách biệt**:
	- `AI-Worker-KTX` xử lý queue KTX
	- `AI-Worker-Parking` xử lý queue bãi xe
	=> Hai pipeline độc lập, không chặn nhau ở tầng xử lý AI/DB
- **Output control**: publish lệnh servo về ESP32

Luồng này giúp tránh nghẽn callback MQTT và chống tràn RAM khi event dồn dập.

## Cấu trúc chính

- `init_db.py`: tạo DB `quan_ly_ktx.db` + seed dữ liệu mẫu
- `main_server.py`: server MQTT + camera + 2 queue + 2 worker + AI + SQLite
- `smoke_test.py`: kiểm tra nhanh DB/schema/dataset/env trước khi chạy server
- `esp32_mqtt_simulator.py`: giả lập ESP32 gửi tín hiệu cảm biến và nhận lệnh servo
- `database_khuonmat/`: thư mục ảnh mặt mẫu

Ảnh mặt mẫu hỗ trợ 2 dạng trong cột `SinhVien.duong_dan_anh`:
- Tên file/local path (cơ chế cũ)
- URL `http/https` (server sẽ tự tải về `database_khuonmat/` khi khởi động)

## Topics MQTT

### Subscribe
- `saban/ktx/sensor_vao`
- `saban/ktx/sensor_ra`
- `saban/baixe/vao/sensor1` (bãi xe vào - sensor đầu cổng)
- `saban/baixe/vao/sensor2` (bãi xe vào - sensor cuối cổng)
- `saban/baixe/ra/sensor1` (bãi xe ra - sensor đầu cổng)
- `saban/baixe/ra/sensor2` (bãi xe ra - sensor cuối cổng)

> Tương thích ngược: server vẫn chấp nhận `saban/baixe/sensor_vao` và `saban/baixe/sensor_ra` như topic cũ (coi như sensor1).

### Publish
- `saban/ktx/servo` -> `OPEN` / `CLOSE`
- `saban/baixe/servo_vao` -> `OPEN` / `CLOSE`
- `saban/baixe/servo_ra` -> `OPEN` / `CLOSE`

## Quy ước payload cảm biến

- `DETECTED`: cảm biến 1 (đầu vào chiều đó), server chạy xác thực AI.
	- Nếu hợp lệ: publish `OPEN`.
- `PASSED`: cảm biến 2 (cuối cổng), server chỉ publish `CLOSE`.
	- Không chạy AI.

### Rule đặc biệt cổng KTX

Ở cổng KTX, sensor 2 của chiều này là sensor 1 của chiều ngược lại (sensor chéo):

- Nếu cổng **vào KTX** đang mở mà `saban/ktx/sensor_ra` kích hoạt,
	server hiểu đây là xe/người đã qua cổng vào và chỉ gửi `CLOSE`.
- Nếu cổng **ra KTX** đang mở mà `saban/ktx/sensor_vao` kích hoạt,
	server hiểu đây là xe/người đã qua cổng ra và chỉ gửi `CLOSE`.

=> Tránh việc “sensor chéo” kích hoạt nhầm một lượt `DETECTED` mới.

## Chuẩn bị môi trường

Cài package:

```powershell
pip install -r .\requirements.txt
```

Thiết lập biến môi trường MQTT (ví dụ HiveMQ Cloud):

```powershell
$env:MQTT_HOST="your-broker-host"
$env:MQTT_PORT="8883"
$env:MQTT_USER="your-username"
$env:MQTT_PASSWORD="your-password"
$env:MQTT_CLIENT_ID="ktx-server-local"
$env:MQTT_USE_TLS="1"
$env:MQTT_TLS_INSECURE="0"
$env:CAMERA_INDEX="0"
$env:CAMERA_URL=""
$env:CAMERA_KTX_IN_URL=""
$env:CAMERA_KTX_IN_INDEX=""
$env:CAMERA_KTX_OUT_URL=""
$env:CAMERA_KTX_OUT_INDEX=""
$env:CAMERA_PARK_IN_PLATE_URL=""
$env:CAMERA_PARK_IN_PLATE_INDEX=""
$env:CAMERA_PARK_OUT_PLATE_URL=""
$env:CAMERA_PARK_OUT_PLATE_INDEX=""
$env:CAMERA_PARK_OUT_FACE_URL=""
$env:CAMERA_PARK_OUT_FACE_INDEX=""
$env:QUEUE_MAXSIZE="20"
$env:YOLO_MODEL_PATH="yolov8n.pt"
$env:VOICE_GUIDE_ENABLED="1"
$env:VOICE_GUIDE_RATE="160"
$env:VOICE_GUIDE_VOLUME="1.0"
$env:FACE_RETRY_COUNT="3"
$env:FACE_RETRY_INTERVAL_MS="2500"
```

Hoặc dùng file mẫu `.env.example` để copy sang file cấu hình của riêng bạn.

Tạo file `.env` nhanh từ mẫu:

```powershell
Copy-Item .\.env.example .\.env
```

Sau đó mở `.env` và điền thông tin broker thật (`MQTT_HOST`, `MQTT_USER`, `MQTT_PASSWORD`...).

> Với HiveMQ Cloud, mặc định nên dùng `MQTT_PORT=8883` và `MQTT_USE_TLS=1`.

> Với cấu hình 5 camera: đặt từng URL/INDEX cho KTX vào/ra, bãi xe vào (biển số), bãi xe ra (biển số + khuôn mặt). Nếu không set, hệ thống sẽ fallback về `CAMERA_URL` hoặc `CAMERA_INDEX`.

> Nếu muốn dùng IP Webcam, đặt `CAMERA_URL=http://<ip>:8080/video` hoặc từng `CAMERA_*_URL` theo camera cụ thể.

> Nếu không muốn phát âm thanh hướng dẫn, đặt `VOICE_GUIDE_ENABLED=0`.

> Retry khuôn mặt mặc định: `FACE_RETRY_COUNT=3`, cách nhau `FACE_RETRY_INTERVAL_MS=2500` (ms).

> Gợi ý: với production, nên dùng model YOLO đã train detect biển số thay vì `yolov8n.pt` mặc định.

## Cách chạy

### 1) Khởi tạo DB

```powershell
python .\init_db.py
```

### 2) Smoke test nhanh

```powershell
.\venv\Scripts\python.exe .\smoke_test.py
```

### 3) Chạy server

```powershell
.\venv\Scripts\python.exe .\main_server.py
```

## Test thực tế khi chưa có ESP32 (khuyến nghị)

Mục tiêu: mô phỏng đúng luồng ESP32 -> Server -> Servo command.

### Bước 1: mở Terminal A chạy server

```powershell
.\venv\Scripts\python.exe .\main_server.py
```

### Bước 2: mở Terminal B chạy ESP32 simulator

```powershell
.\venv\Scripts\python.exe .\esp32_mqtt_simulator.py
```

> Simulator sẽ tự đọc cấu hình MQTT từ file `.env`.

### Bước 3: trong simulator nhập lệnh test

- `1`: gửi `DETECTED` ở `saban/ktx/sensor_vao` (sensor1)
- `2`: gửi `DETECTED` ở `saban/ktx/sensor_ra` (sensor1)
- `3`: gửi `DETECTED` ở `saban/baixe/vao/sensor1` (sensor1)
- `4`: gửi `DETECTED` ở `saban/baixe/ra/sensor1` (sensor1)
- `c1`: gửi `PASSED` ở `saban/ktx/sensor_vao` (sensor2)
- `c2`: gửi `PASSED` ở `saban/ktx/sensor_ra` (sensor2)
- `c3`: gửi `PASSED` ở `saban/baixe/vao/sensor2` (sensor2)
- `c4`: gửi `PASSED` ở `saban/baixe/ra/sensor2` (sensor2)
- `all`: gửi tuần tự 4 lệnh `DETECTED`

Nếu nhận diện hợp lệ, simulator sẽ in lệnh từ server, ví dụ:
- `Topic=saban/ktx/servo | Payload=OPEN`
- `Topic=saban/baixe/servo_vao | Payload=OPEN`
- `Topic=saban/baixe/servo_ra | Payload=OPEN`

Khi cảm biến 2 kích hoạt (`PASSED`), simulator sẽ nhận:
- `Topic=saban/ktx/servo | Payload=CLOSE`
- `Topic=saban/baixe/servo_vao | Payload=CLOSE`
- `Topic=saban/baixe/servo_ra | Payload=CLOSE`

### Kịch bản test demo khuyến nghị

#### 1) Người vào KTX
1. Gửi `1` (`DETECTED` vào KTX) -> kỳ vọng `OPEN`.
2. Sau khi qua cổng, gửi `c2` (sensor chéo chiều ra) -> kỳ vọng `CLOSE`.

#### 2) Người ra KTX
1. Gửi `2` (`DETECTED` ra KTX) -> kỳ vọng `OPEN`.
2. Sau khi qua cổng, gửi `c1` (sensor chéo chiều vào) -> kỳ vọng `CLOSE`.

#### 3) Xe vào bãi
1. Gửi `3` (`DETECTED` tại `saban/baixe/vao/sensor1`) -> kỳ vọng `OPEN`.
2. Xe qua cảm biến 2, gửi `c3` (`PASSED` tại `saban/baixe/vao/sensor2`) -> kỳ vọng `CLOSE`.

#### 4) Xe ra bãi
1. Gửi `4` (`DETECTED` tại `saban/baixe/ra/sensor1`) -> kỳ vọng `OPEN`.
2. Xe qua cảm biến 2, gửi `c4` (`PASSED` tại `saban/baixe/ra/sensor2`) -> kỳ vọng `CLOSE`.

## Test khi có ESP32 thật

1. ESP32 publish payload `DETECTED` từ cảm biến 1 theo chiều vào/ra.
	- Bãi xe vào: `saban/baixe/vao/sensor1`
	- Bãi xe ra: `saban/baixe/ra/sensor1`
2. Server nhận sự kiện, xử lý AI, kiểm tra SQLite.
3. Nếu hợp lệ, server publish `OPEN` về topic servo tương ứng.
4. Khi đối tượng qua cảm biến 2, ESP32 publish payload `PASSED`.
	- Bãi xe vào: `saban/baixe/vao/sensor2`
	- Bãi xe ra: `saban/baixe/ra/sensor2`
5. Server publish `CLOSE` để đóng barie.

Checklist ESP32 firmware:
- Subscribe: `saban/ktx/servo`, `saban/baixe/servo_vao`, `saban/baixe/servo_ra`
- Publish khi sensor1 trigger: `DETECTED`
- Publish khi sensor2 trigger: `PASSED`
- Parse payload servo: `OPEN` để mở cổng, `CLOSE` để đóng cổng

## Edge cases đã xử lý

- Queue đầy: drop event và ghi log DB (`QUEUE_FULL_DROP`)
- Camera lỗi frame: bỏ event, không treo callback
- Lỗi AI (DeepFace/YOLO/OCR): ghi log và tiếp tục xử lý event sau
- Lỗi DB cục bộ: catch `sqlite3.Error`, không làm sập toàn bộ server

## Troubleshooting nhanh

- **`Thiếu MQTT_HOST`**: chưa set env CloudMQTT
- **`Không tìm thấy DB`**: chưa chạy `init_db.py`
- **`No item found in database_khuonmat`**: ảnh mặt mẫu chưa đủ rõ/không detect được
- **Import lỗi `paho.mqtt.client`**: chưa cài dependencies

## Gợi ý nâng cấp tiếp

- Dùng 2 camera riêng cho KTX/Bãi xe (thay camera dùng chung)
- Thêm retry + reconnect MQTT có backoff
- Dùng cache embedding khuôn mặt và batch OCR để tăng tốc
- Bổ sung test tự động cho topic routing và DB transaction

## Dashboard quản trị (mới)

Bạn có thể dùng dashboard web để:
- Xem lịch sử ra/vào (`LichSu`)
- Thêm/sửa/xóa sinh viên (`SinhVien`)
- Thêm/sửa/xóa phương tiện (`PhuongTien`)

Mã nguồn dashboard nằm ở thư mục `dashboard/`.

Chạy dashboard:

```powershell
.\venv\Scripts\python.exe .\dashboard\app.py
```

Mở trình duyệt tại: `http://127.0.0.1:5001`

Biến môi trường tùy chọn:
- `DASHBOARD_DB_PATH`: đường dẫn SQLite (mặc định `quan_ly_ktx.db`)
- `DASHBOARD_PORT`: cổng chạy web (mặc định `5001`)
- `DASHBOARD_SECRET_KEY`: secret key cho session Flask
