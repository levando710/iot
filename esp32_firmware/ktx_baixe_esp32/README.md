# Firmware ESP32 cho he thong KTX va bai xe

Firmware `ktx_baixe_esp32.ino` dieu khien 6 cam bien hong ngoai LM393 va 3 servo MG996R. ESP32 gui trang thai cam bien len server bang MQTT va nhan lenh `OPEN` / `CLOSE` de quay servo.

## Thu vien can cai

Cai trong Arduino IDE Library Manager:

- `PubSubClient`
- `ESP32Servo`

Board su dung: `ESP32 Dev Module`.

## Cau hinh truoc khi nap code

Trong file `.ino`, cap nhat cac gia tri sau bang thong tin cua he thong:

```cpp
const char* WIFI_SSID = "your-wifi-name";
const char* WIFI_PASSWORD = "your-wifi-password";

const char* MQTT_HOST = "your-mqtt-host";
const int MQTT_PORT = 8883;
const char* MQTT_USER = "your-mqtt-user";
const char* MQTT_PASSWORD = "your-mqtt-password";
```

Khong dua thong tin WiFi hoac MQTT that len GitHub.

## So do chan

| Chuc nang | GPIO ESP32 |
| --- | --- |
| Servo cong KTX | GPIO 18 |
| Servo cong vao bai xe | GPIO 19 |
| Servo cong ra bai xe | GPIO 21 |
| Cam bien KTX truoc cong | GPIO 32 |
| Cam bien KTX sau cong | GPIO 33 |
| Cam bien bai xe vao truoc cong | GPIO 25 |
| Cam bien bai xe vao sau cong | GPIO 26 |
| Cam bien bai xe ra truoc cong | GPIO 27 |
| Cam bien bai xe ra sau cong | GPIO 14 |

## Dau noi nguon

Nen cap nguon theo cach tach rieng ESP32 va servo:

```text
Sac du phong / nguon 5V
├── Cong USB 1 -> ESP32
└── Cong USB 2 -> Nguon 5V cho 3 servo

GND ESP32 phai noi chung voi GND nguon servo.
```

Servo MG996R can dong lon, khong nen lay nguon servo truc tiep tu chan 5V cua ESP32 khi chay nhieu servo.

## Dau noi cam bien LM393

Moi cam bien LM393 co cac chan thong dung:

| Chan cam bien | Noi den |
| --- | --- |
| `VCC` | `3V3` hoac `5V` tuy module |
| `GND` | `GND` ESP32 |
| `DO` | GPIO cam bien tuong ung |

Firmware dang cau hinh:

```cpp
const bool SENSOR_ACTIVE_LOW = true;
```

Neu cam bien bao nguoc trang thai, doi thanh:

```cpp
const bool SENSOR_ACTIVE_LOW = false;
```

## MQTT topics

### ESP32 publish len server

| Topic | Payload |
| --- | --- |
| `saban/ktx/sensor_vao` | `DETECTED` |
| `saban/ktx/sensor_ra` | `PASSED` |
| `saban/baixe/vao/sensor1` | `DETECTED` |
| `saban/baixe/vao/sensor2` | `PASSED` |
| `saban/baixe/ra/sensor1` | `DETECTED` |
| `saban/baixe/ra/sensor2` | `PASSED` |

### ESP32 subscribe tu server

| Topic | Payload | Servo |
| --- | --- | --- |
| `saban/ktx/servo` | `OPEN` / `CLOSE` | Servo KTX |
| `saban/baixe/servo_vao` | `OPEN` / `CLOSE` | Servo cong vao bai xe |
| `saban/baixe/servo_ra` | `OPEN` / `CLOSE` | Servo cong ra bai xe |

## Logic hoat dong cua firmware

1. ESP32 ket noi WiFi.
2. ESP32 ket noi MQTT broker.
3. Khi cam bien truoc cong phat hien vat can, ESP32 publish `DETECTED`.
4. Server xu ly AI va gui lenh `OPEN` neu xac thuc thanh cong.
5. ESP32 quay servo tu goc dong sang goc mo.
6. Khi cam bien sau cong phat hien da di qua, ESP32 publish `PASSED`.
7. Server gui `CLOSE`, ESP32 quay servo ve goc dong.

Neu nguoi dung dung truoc cam bien trong thoi gian dai, firmware co co che gui lai `DETECTED` theo chu ky de server co the thu lai xac thuc.

## Kiem tra bang HiveMQ Web Client

1. Mo HiveMQ WebSocket Client.
2. Ket noi toi broker voi dung host, port WebSocket, username va password.
3. Subscribe topic:

```text
saban/#
```

4. Che cam bien va quan sat message `DETECTED` hoac `PASSED`.
5. Test servo bang cach publish:

```text
Topic: saban/ktx/servo
Payload: OPEN
```

Sau do publish:

```text
Topic: saban/ktx/servo
Payload: CLOSE
```

Lam tuong tu voi `saban/baixe/servo_vao` va `saban/baixe/servo_ra`.

## Su co thuong gap

| Hien tuong | Huong xu ly |
| --- | --- |
| Serial Monitor hien ky tu la | Chinh dung baud rate, thuong la `115200` |
| MQTT `rc=5` | Sai tai khoan, mat khau, port, TLS hoac cau hinh broker |
| Khong thay message cam bien | Kiem tra chan `DO`, GND, trang thai `SENSOR_ACTIVE_LOW` |
| Servo khong quay | Kiem tra nguon 5V, dong cap, day signal va GND chung |
| Servo chi quay lan dau | Thu gui `OPEN`/`CLOSE` luan phien, kiem tra nguon va goc servo |
