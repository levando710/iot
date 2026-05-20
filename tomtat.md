# Tom tat phan cung va dau noi

Tai lieu nay tom tat cac thanh phan phan cung, cach dau noi va luong hoat dong cua he thong quan ly ra vao KTX va bai xe thong minh.

## Thanh phan chinh

| Nhom | Thanh phan | So luong | Chuc nang |
| --- | --- | --- | --- |
| Vi dieu khien | ESP32 DevKit V1 | 1 | Doc cam bien, giao tiep MQTT, dieu khien servo |
| Cam bien | Cam bien hong ngoai LM393 | 6 | Phat hien nguoi/xe truoc va sau cong |
| Co cau chap hanh | Servo MG996R | 3 | Mo/dong cong KTX, cong vao bai xe, cong ra bai xe |
| Camera | Dien thoai/IP camera/Webcam | 5 | Chup anh khuon mat va bien so |
| Server | May tinh chay Python | 1 | Xu ly MQTT, camera, AI, database va dashboard |
| Nguon | Sac du phong hoac nguon 5V | 1-2 cong USB | Cap nguon cho ESP32 va servo |
| Phu kien | Breadboard, day dupont, nut bam, LED | Tuy chon | Dau noi va ho tro demo |

## Phan bo camera

| Vi tri | Chuc nang |
| --- | --- |
| Cong vao KTX | Chup khuon mat sinh vien khi vao |
| Cong ra KTX | Chup khuon mat sinh vien khi ra |
| Cong vao bai xe | Chup bien so xe khi gui xe |
| Cong ra bai xe | Chup bien so xe khi lay xe |
| Cong ra bai xe | Chup khuon mat nguoi lay xe |

## Phan bo servo

| Servo | Vi tri | MQTT topic dieu khien |
| --- | --- | --- |
| Servo KTX | Cong KTX | `saban/ktx/servo` |
| Servo bai xe vao | Cong vao bai xe | `saban/baixe/servo_vao` |
| Servo bai xe ra | Cong ra bai xe | `saban/baixe/servo_ra` |

Moi servo nhan payload `OPEN` de mo cong va `CLOSE` de dong cong.

## Phan bo cam bien

| Cam bien | Vi tri | GPIO | MQTT topic |
| --- | --- | --- | --- |
| KTX truoc cong | Phat hien nguoi can xac thuc | GPIO 32 | `saban/ktx/sensor_vao` |
| KTX sau cong | Xac nhan da di qua cong | GPIO 33 | `saban/ktx/sensor_ra` |
| Bai xe vao truoc cong | Phat hien xe can gui | GPIO 25 | `saban/baixe/vao/sensor1` |
| Bai xe vao sau cong | Xac nhan xe da vao | GPIO 26 | `saban/baixe/vao/sensor2` |
| Bai xe ra truoc cong | Phat hien xe can lay | GPIO 27 | `saban/baixe/ra/sensor1` |
| Bai xe ra sau cong | Xac nhan xe da ra | GPIO 14 | `saban/baixe/ra/sensor2` |

## Dau noi nguon

He thong nen tach nguon ESP32 va servo de tranh sut ap khi servo quay:

```text
Sac du phong / nguon 5V
|-- USB 1 -> Cap nguon cho ESP32
`-- USB 2 -> Cap nguon 5V cho 3 servo

GND ESP32 -------- GND nguon servo
```

Luu y quan trong:

- GND cua ESP32 va GND cua nguon servo phai noi chung.
- Servo MG996R can dong cao, nen dung nguon 5V co dong du lon.
- Khong nen cap nguon ca 3 servo truc tiep tu ESP32.

## Dau noi servo

| Day servo | Noi den |
| --- | --- |
| Do | 5V nguon servo |
| Nau/Den | GND nguon servo va GND ESP32 |
| Vang/Cam | GPIO dieu khien servo |

GPIO dieu khien:

| Servo | GPIO |
| --- | --- |
| KTX | 18 |
| Bai xe vao | 19 |
| Bai xe ra | 21 |

## Dau noi cam bien LM393

| Chan LM393 | Noi den |
| --- | --- |
| `VCC` | `3V3` hoac `5V` tuy module |
| `GND` | `GND` ESP32 |
| `DO` | GPIO cam bien tuong ung |

Neu cam bien bao trang thai nguoc, can doi cau hinh `SENSOR_ACTIVE_LOW` trong firmware ESP32.

## Luong hoat dong phan cung

```text
Nguoi/xe den truoc cong
        |
        v
Cam bien truoc cong phat hien
        |
        v
ESP32 publish MQTT DETECTED
        |
        v
Server chup anh va xu ly AI
        |
        v
Server publish MQTT OPEN neu xac thuc thanh cong
        |
        v
ESP32 quay servo mo cong
        |
        v
Nguoi/xe di qua cong
        |
        v
Cam bien sau cong publish PASSED
        |
        v
Server publish MQTT CLOSE
        |
        v
ESP32 quay servo dong cong
```

Neu khong co tin hieu `PASSED`, server se tu dong gui `CLOSE` sau thoi gian timeout de tranh cong bi mo qua lau.

## Luong xu ly tai server

Server Python dam nhan cac nhiem vu:

- Ket noi MQTT broker va lang nghe su kien cam bien.
- Tao hang doi rieng cho cac luong KTX, bai xe vao va bai xe ra.
- Chup anh tu camera phu hop voi tung su kien.
- Xac thuc khuon mat bang DeepFace.
- Phat hien bien so bang YOLO va doc ky tu bang EasyOCR.
- Chuan hoa bien so truoc khi so sanh voi database.
- Ghi lich su vao SQLite.
- Publish lenh `OPEN`/`CLOSE` ve ESP32.
- Tu dong dong cong neu qua thoi gian timeout.

## Goi y hinh anh cho bao cao

Co the bo sung cac hinh sau vao bao cao:

| Hinh | Noi dung de xuat |
| --- | --- |
| Kien truc he thong | MQTT Client, Camera Worker, Queue, AI Worker, SQLite, Publish OPEN/CLOSE |
| So do dau noi | ESP32 ket noi 6 cam bien IR va 3 servo MG996R |
| Luong KTX | Cam bien -> chup mat -> xac thuc -> mo cong -> dong cong |
| Luong bai xe vao | Cam bien -> chup bien so -> OCR -> mo cong -> dong cong |
| Luong bai xe ra | Bien so + khuon mat -> xac thuc chu xe -> mo cong |
| Anh demo AI | Nhan dien khuon mat thanh cong/that bai va OCR bien so |

## Ghi chu trien khai

- Khi test MQTT tren web client, subscribe `saban/#` de xem tat ca message.
- Khi test servo rieng, publish `OPEN` va `CLOSE` vao topic servo tuong ung.
- Khi test cam bien, mo Serial Monitor voi baud rate `115200`.

