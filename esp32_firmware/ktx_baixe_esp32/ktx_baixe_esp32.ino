#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// =========================
// WIFI + MQTT CONFIG
// =========================
// Dien thong tin Wi-Fi va MQTT truoc khi nap vao ESP32.
// Khong commit thong tin Wi-Fi/MQTT that len repository cong khai.
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Thong tin MQTT phai khop voi file .env cua server.
const char* MQTT_HOST = "YOUR_MQTT_HOST";
const int MQTT_PORT = 8883;
const char* MQTT_USER = "YOUR_MQTT_USER";
const char* MQTT_PASSWORD = "YOUR_MQTT_PASSWORD";
const char* MQTT_CLIENT_ID = "esp32-ktx-baixe-01";

// Neu dung HiveMQ Cloud TLS va khong cai CA cert tren ESP32, tam thoi cho phep insecure.
// Khi lam that nen cai CA certificate thay vi setInsecure().
WiFiClientSecure wifiClient;
PubSubClient mqttClient(wifiClient);

// =========================
// MQTT TOPICS
// =========================
const char* TOPIC_KTX_SENSOR_VAO = "saban/ktx/sensor_vao";
const char* TOPIC_KTX_SENSOR_RA = "saban/ktx/sensor_ra";
const char* TOPIC_BAIXE_VAO_SENSOR1 = "saban/baixe/vao/sensor1";
const char* TOPIC_BAIXE_VAO_SENSOR2 = "saban/baixe/vao/sensor2";
const char* TOPIC_BAIXE_RA_SENSOR1 = "saban/baixe/ra/sensor1";
const char* TOPIC_BAIXE_RA_SENSOR2 = "saban/baixe/ra/sensor2";

const char* TOPIC_KTX_SERVO = "saban/ktx/servo";
const char* TOPIC_BAIXE_SERVO_VAO = "saban/baixe/servo_vao";
const char* TOPIC_BAIXE_SERVO_RA = "saban/baixe/servo_ra";

const char* PAYLOAD_DETECTED = "DETECTED";
const char* PAYLOAD_PASSED = "PASSED";
const char* PAYLOAD_OPEN = "OPEN";
const char* PAYLOAD_CLOSE = "CLOSE";

// =========================
// PIN CONFIG
// =========================
const int PIN_SERVO_KTX = 18;
const int PIN_SERVO_BAIXE_VAO = 19;
const int PIN_SERVO_BAIXE_RA = 21;

const int PIN_SENSOR_KTX_1 = 32;
const int PIN_SENSOR_KTX_2 = 33;
const int PIN_SENSOR_BAIXE_VAO_1 = 25;
const int PIN_SENSOR_BAIXE_VAO_2 = 26;
const int PIN_SENSOR_BAIXE_RA_1 = 27;
const int PIN_SENSOR_BAIXE_RA_2 = 14;

// Nhieu module IR obstacle output LOW khi bi che.
// Neu module cua ban output HIGH khi bi che, doi thanh false.
const bool SENSOR_ACTIVE_LOW = true;

// Goc servo tuy theo co khi mo hinh.
const int SERVO_CLOSE_ANGLE = 0;
const int SERVO_OPEN_ANGLE = 90;

// Gui lai DETECTED neu sensor1 van bi che ma chua nhan OPEN.
const unsigned long AUTH_RETRY_INTERVAL_MS = 4000;
const int AUTH_MAX_RETRY = 5;

// Chong rung sensor.
const unsigned long SENSOR_DEBOUNCE_MS = 80;

Servo servoKtx;
Servo servoBaixeVao;
Servo servoBaixeRa;

struct SensorChannel {
  const char* name;
  int pin;
  const char* topic;
  bool isAuthSensor;
  bool lastRawActive;
  bool stableActive;
  unsigned long lastChangeMs;
  unsigned long lastPublishMs;
  int sentCount;
  bool waitingOpen;
};

SensorChannel sensors[] = {
  {"KTX_1", PIN_SENSOR_KTX_1, TOPIC_KTX_SENSOR_VAO, true, false, false, 0, 0, 0, false},
  {"KTX_2", PIN_SENSOR_KTX_2, TOPIC_KTX_SENSOR_RA, true, false, false, 0, 0, 0, false},
  {"BAIXE_VAO_1", PIN_SENSOR_BAIXE_VAO_1, TOPIC_BAIXE_VAO_SENSOR1, true, false, false, 0, 0, 0, false},
  {"BAIXE_VAO_2", PIN_SENSOR_BAIXE_VAO_2, TOPIC_BAIXE_VAO_SENSOR2, false, false, false, 0, 0, 0, false},
  {"BAIXE_RA_1", PIN_SENSOR_BAIXE_RA_1, TOPIC_BAIXE_RA_SENSOR1, true, false, false, 0, 0, 0, false},
  {"BAIXE_RA_2", PIN_SENSOR_BAIXE_RA_2, TOPIC_BAIXE_RA_SENSOR2, false, false, false, 0, 0, 0, false},
};

const int SENSOR_COUNT = sizeof(sensors) / sizeof(sensors[0]);

bool ktxGateOpen = false;
bool baixeVaoGateOpen = false;
bool baixeRaGateOpen = false;

// =========================
// HELPERS
// =========================
bool readSensorActive(int pin) {
  int value = digitalRead(pin);
  return SENSOR_ACTIVE_LOW ? (value == LOW) : (value == HIGH);
}

void publishSensor(const char* topic, const char* payload, const char* name) {
  if (!mqttClient.connected()) {
    return;
  }
  bool ok = mqttClient.publish(topic, payload, false);
  Serial.print("[MQTT->SERVER] ");
  Serial.print(name);
  Serial.print(" | ");
  Serial.print(topic);
  Serial.print(" | ");
  Serial.print(payload);
  Serial.print(" | ");
  Serial.println(ok ? "OK" : "FAIL");
}

void setServo(Servo& servo, const char* name, bool open) {
  servo.write(open ? SERVO_OPEN_ANGLE : SERVO_CLOSE_ANGLE);
  Serial.print("[SERVO] ");
  Serial.print(name);
  Serial.print(" -> ");
  Serial.println(open ? "OPEN" : "CLOSE");
}

void clearAuthWaitingForTopic(const char* servoTopic) {
  // Khi server da chap nhan va gui OPEN, dung gui lai DETECTED cho nhom lien quan.
  for (int i = 0; i < SENSOR_COUNT; i++) {
    if (!sensors[i].isAuthSensor) continue;

    bool sameGroup =
      (strcmp(servoTopic, TOPIC_KTX_SERVO) == 0 && (strcmp(sensors[i].topic, TOPIC_KTX_SENSOR_VAO) == 0 || strcmp(sensors[i].topic, TOPIC_KTX_SENSOR_RA) == 0)) ||
      (strcmp(servoTopic, TOPIC_BAIXE_SERVO_VAO) == 0 && strcmp(sensors[i].topic, TOPIC_BAIXE_VAO_SENSOR1) == 0) ||
      (strcmp(servoTopic, TOPIC_BAIXE_SERVO_RA) == 0 && strcmp(sensors[i].topic, TOPIC_BAIXE_RA_SENSOR1) == 0);

    if (sameGroup) {
      sensors[i].waitingOpen = false;
      sensors[i].sentCount = 0;
    }
  }
}

// =========================
// MQTT
// =========================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  char messageBuffer[32];
  unsigned int copyLength = min(length, sizeof(messageBuffer) - 1);
  memcpy(messageBuffer, payload, copyLength);
  messageBuffer[copyLength] = '\0';

  String message = String(messageBuffer);
  message.trim();
  message.toUpperCase();

  Serial.print("[SERVER->MQTT] ");
  Serial.print(topic);
  Serial.print(" | ");
  Serial.print("len=");
  Serial.print(length);
  Serial.print(" | payload=");
  Serial.println(message);

  if (strcmp(topic, TOPIC_KTX_SERVO) == 0) {
    if (message == PAYLOAD_OPEN) {
      ktxGateOpen = true;
      setServo(servoKtx, "KTX", true);
      clearAuthWaitingForTopic(topic);
    } else if (message == PAYLOAD_CLOSE) {
      ktxGateOpen = false;
      setServo(servoKtx, "KTX", false);
    }
    return;
  }

  if (strcmp(topic, TOPIC_BAIXE_SERVO_VAO) == 0) {
    if (message == PAYLOAD_OPEN) {
      baixeVaoGateOpen = true;
      setServo(servoBaixeVao, "BAIXE_VAO", true);
      clearAuthWaitingForTopic(topic);
    } else if (message == PAYLOAD_CLOSE) {
      baixeVaoGateOpen = false;
      setServo(servoBaixeVao, "BAIXE_VAO", false);
    }
    return;
  }

  if (strcmp(topic, TOPIC_BAIXE_SERVO_RA) == 0) {
    if (message == PAYLOAD_OPEN) {
      baixeRaGateOpen = true;
      setServo(servoBaixeRa, "BAIXE_RA", true);
      clearAuthWaitingForTopic(topic);
    } else if (message == PAYLOAD_CLOSE) {
      baixeRaGateOpen = false;
      setServo(servoBaixeRa, "BAIXE_RA", false);
    }
    return;
  }

  Serial.println("[MQTT] Topic khong dung servo topic, bo qua.");
}

void connectWiFi() {
  Serial.print("[WIFI] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("[WIFI] Connected. IP=");
  Serial.println(WiFi.localIP());
}

void connectMqtt() {
  while (!mqttClient.connected()) {
    Serial.print("[MQTT] Connecting...");
    if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD)) {
      Serial.println("OK");
      mqttClient.subscribe(TOPIC_KTX_SERVO, 1);
      mqttClient.subscribe(TOPIC_BAIXE_SERVO_VAO, 1);
      mqttClient.subscribe(TOPIC_BAIXE_SERVO_RA, 1);
      Serial.println("[MQTT] Subscribed servo topics.");
      Serial.println("[MQTT] Servo test topics:");
      Serial.println("       saban/ktx/servo -> OPEN/CLOSE");
      Serial.println("       saban/baixe/servo_vao -> OPEN/CLOSE");
      Serial.println("       saban/baixe/servo_ra -> OPEN/CLOSE");
    } else {
      Serial.print("FAIL rc=");
      Serial.println(mqttClient.state());
      delay(3000);
    }
  }
}

// =========================
// SENSOR LOGIC
// =========================
bool shouldCloseBySensor(SensorChannel& sensor) {
  if (strcmp(sensor.topic, TOPIC_BAIXE_VAO_SENSOR2) == 0) {
    return baixeVaoGateOpen;
  }
  if (strcmp(sensor.topic, TOPIC_BAIXE_RA_SENSOR2) == 0) {
    return baixeRaGateOpen;
  }
  // KTX dung 2 sensor cheo. Khi cong dang mo, sensor bat ky co the gui PASSED de server dong theo state.
  if (strcmp(sensor.topic, TOPIC_KTX_SENSOR_VAO) == 0 || strcmp(sensor.topic, TOPIC_KTX_SENSOR_RA) == 0) {
    return ktxGateOpen;
  }
  return false;
}

void handleSensorActiveEdge(SensorChannel& sensor) {
  unsigned long now = millis();

  if (sensor.isAuthSensor) {
    // Neu cong KTX dang mo, sensor KTX kich hoat thi uu tien bao PASSED de dong cong.
    if (shouldCloseBySensor(sensor)) {
      publishSensor(sensor.topic, PAYLOAD_PASSED, sensor.name);
      return;
    }

    sensor.waitingOpen = true;
    sensor.sentCount = 1;
    sensor.lastPublishMs = now;
    publishSensor(sensor.topic, PAYLOAD_DETECTED, sensor.name);
    return;
  }

  // Sensor2 bai xe chi dung de dong cong.
  publishSensor(sensor.topic, PAYLOAD_PASSED, sensor.name);
}

void handleSensorHoldRetry(SensorChannel& sensor) {
  if (!sensor.isAuthSensor || !sensor.waitingOpen || !sensor.stableActive) {
    return;
  }

  unsigned long now = millis();
  if (sensor.sentCount >= AUTH_MAX_RETRY) {
    return;
  }

  if (now - sensor.lastPublishMs >= AUTH_RETRY_INTERVAL_MS) {
    sensor.sentCount++;
    sensor.lastPublishMs = now;
    publishSensor(sensor.topic, PAYLOAD_DETECTED, sensor.name);
  }
}

void updateSensors() {
  unsigned long now = millis();

  for (int i = 0; i < SENSOR_COUNT; i++) {
    SensorChannel& sensor = sensors[i];
    bool rawActive = readSensorActive(sensor.pin);

    if (rawActive != sensor.lastRawActive) {
      sensor.lastRawActive = rawActive;
      sensor.lastChangeMs = now;
    }

    if ((now - sensor.lastChangeMs) < SENSOR_DEBOUNCE_MS) {
      continue;
    }

    if (rawActive != sensor.stableActive) {
      sensor.stableActive = rawActive;
      if (sensor.stableActive) {
        handleSensorActiveEdge(sensor);
      } else {
        sensor.waitingOpen = false;
        sensor.sentCount = 0;
      }
    }

    handleSensorHoldRetry(sensor);
  }
}

// =========================
// ARDUINO SETUP/LOOP
// =========================
void setup() {
  Serial.begin(115200);
  delay(1000);

  for (int i = 0; i < SENSOR_COUNT; i++) {
    pinMode(sensors[i].pin, INPUT_PULLUP);
    sensors[i].lastRawActive = readSensorActive(sensors[i].pin);
    sensors[i].stableActive = sensors[i].lastRawActive;
    sensors[i].lastChangeMs = millis();
  }

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);

  servoKtx.setPeriodHertz(50);
  servoBaixeVao.setPeriodHertz(50);
  servoBaixeRa.setPeriodHertz(50);

  servoKtx.attach(PIN_SERVO_KTX, 500, 2400);
  servoBaixeVao.attach(PIN_SERVO_BAIXE_VAO, 500, 2400);
  servoBaixeRa.attach(PIN_SERVO_BAIXE_RA, 500, 2400);

  setServo(servoKtx, "KTX", false);
  setServo(servoBaixeVao, "BAIXE_VAO", false);
  setServo(servoBaixeRa, "BAIXE_RA", false);

  connectWiFi();

  wifiClient.setInsecure();
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (!mqttClient.connected()) {
    connectMqtt();
  }

  mqttClient.loop();
  updateSensors();
}
