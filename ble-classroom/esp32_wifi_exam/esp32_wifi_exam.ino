// NEXUS Classroom — classic ESP32 DevKit (not ESP32-C3/S3).
// Wire five normally-open buttons between each GPIO and GND.
// Each separate LED needs its own 220–330 ohm series resistor to GND.
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include "secrets.h"  // Copy secrets.example.h; secrets.h is intentionally Git-ignored.

const int BUTTON_PINS[5] = {25, 26, 27, 32, 33};  // A, B, C, D, Submit.
const int LED_CONNECT = 18;  // On only after the server accepts this device token.
const int LED_NEXT = 19;     // Blink for a new question until answer ACK.
const char CHOICES[4] = {'A', 'B', 'C', 'D'};
const unsigned long POLL_MS = 1000;
const unsigned long HEARTBEAT_MS = 5000;
const unsigned long SERVER_CHECK_MS = 5000;
const unsigned long BLINK_MS = 250;
const unsigned long DEBOUNCE_MS = 35;

uint32_t currentQuestion = 0;
uint32_t sequenceNumber = 0;
char selectedChoice = '\0';
bool submitted = false;
bool answerAcked = false;
bool serverConnected = false;
bool nextLedOn = false;
bool lastReading[5] = {HIGH, HIGH, HIGH, HIGH, HIGH};
bool stableReading[5] = {HIGH, HIGH, HIGH, HIGH, HIGH};
unsigned long changedAt[5] = {0, 0, 0, 0, 0};
unsigned long lastPoll = 0;
unsigned long lastHeartbeat = 0;
unsigned long lastConnectAttempt = 0;
unsigned long lastServerCheck = 0;
unsigned long lastBlink = 0;

void setServerConnected(bool connected) {
  if (serverConnected == connected) return;
  serverConnected = connected;
  digitalWrite(LED_CONNECT, connected ? HIGH : LOW);
  Serial.println(connected ? "Server da nhan thiet bi." : "Mat ket noi server/thiet bi khong hop le.");
}

void setNextLed(bool on) {
  nextLedOn = on;
  digitalWrite(LED_NEXT, on ? HIGH : LOW);
  lastBlink = millis();
}

void blinkNextLed(unsigned long now) {
  if (currentQuestion == 0 || answerAcked) return;
  if (now - lastBlink >= BLINK_MS) setNextLed(!nextLedOn);
}

int httpRequest(const char *method, const String &path, const String &body, String &reply) {
  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, String(SERVER_URL) + path)) return -1;
  http.setTimeout(3000);
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  int code;
  if (String(method) == "POST") {
    http.addHeader("Content-Type", "application/json");
    code = http.POST(body);
  } else {
    code = http.GET();
  }
  reply = code > 0 ? http.getString() : "";
  http.end();
  return code;
}

uint32_t jsonQuestionId(const String &json) {
  int key = json.indexOf("\"question_id\"");
  if (key < 0) return 0;
  int colon = json.indexOf(':', key + 13);
  if (colon < 0) return 0;
  int i = colon + 1;
  while (i < json.length() && (json[i] == ' ' || json[i] == '\t')) ++i;
  int start = i;
  while (i < json.length() && json[i] >= '0' && json[i] <= '9') ++i;
  if (i == start) return 0;
  return static_cast<uint32_t>(json.substring(start, i).toInt());
}

void checkServer() {
  String reply;
  int code = httpRequest("GET", "/api/device/ping", "", reply);
  setServerConnected(code == 200);
  if (code == 401) Serial.println("Ma ESP32 sai/da thu hoi. Tao ma moi tren web va nap lai board.");
}

void pollQuestion() {
  String reply;
  int code = httpRequest("GET", "/api/device/current", "", reply);
  if (code == 200) {
    uint32_t next = jsonQuestionId(reply);
    if (next != 0 && next != currentQuestion) {
      currentQuestion = next;
      selectedChoice = '\0';
      submitted = false;
      answerAcked = false;
      lastHeartbeat = 0;
      setNextLed(true);  // A new question is the Wi-Fi equivalent of NEXT.
      Serial.printf("Cau moi #%lu — chon A/B/C/D roi bam Submit\n", (unsigned long)next);
    }
  } else if (code == 409 || code == 403) {
    if (currentQuestion != 0) Serial.println("Khong co cau hoi dang mo cho thiet bi nay.");
    currentQuestion = 0;
    selectedChoice = '\0';
    submitted = false;
    answerAcked = false;
    setNextLed(false);
  } else if (code == 401) {
    setServerConnected(false);
    Serial.println("Ma ESP32 sai/da thu hoi. Tao ma moi tren web va nap lai board.");
  } else {
    if (code < 0) setServerConnected(false);
    Serial.printf("Khong lay duoc cau hoi (HTTP %d). Kiem tra Wi-Fi/server.\n", code);
  }
}

void sendHeartbeat() {
  if (currentQuestion == 0) return;
  String body = "{\"question_id\":" + String(currentQuestion) +
                ",\"connected\":true,\"rssi\":" + String(WiFi.RSSI()) +
                ",\"gateway_id\":\"esp32:" + WiFi.macAddress() + "\"}";
  String reply;
  int code = httpRequest("POST", "/api/device/presence", body, reply);
  if (code != 202) Serial.printf("Heartbeat chua duoc nhan (HTTP %d).\n", code);
}

void submitChoice() {
  if (currentQuestion == 0 || selectedChoice == '\0' || submitted) return;
  ++sequenceNumber;
  String body = "{\"question_id\":" + String(currentQuestion) +
                ",\"choice\":\"" + String(selectedChoice) +
                "\",\"sequence\":" + String(sequenceNumber) + "}";
  String reply;
  int code = httpRequest("POST", "/api/device/answers", body, reply);
  if (code == 201 && reply.indexOf("\"ACK\"") >= 0) {
    submitted = true;
    answerAcked = true;
    setNextLed(false);  // Explicit ACK from the server.
    Serial.printf("Da nop dap an %c cho cau #%lu. Khong the chon lai.\n",
                  selectedChoice, (unsigned long)currentQuestion);
  } else if (code == 409) {
    submitted = true;  // Duplicate/expired: wait for the next question, do not retry blindly.
    Serial.println("Cau da het gio hoac da nop. Cho cau tiep theo.");
  } else {
    if (code < 0 || code == 401) setServerConnected(false);
    Serial.printf("Chua nop duoc (HTTP %d). Bam Submit de thu lai.\n", code);
  }
}

void scanButtons() {
  unsigned long now = millis();
  for (int i = 0; i < 5; ++i) {
    bool reading = digitalRead(BUTTON_PINS[i]);
    if (reading != lastReading[i]) changedAt[i] = now;
    lastReading[i] = reading;
    if (now - changedAt[i] < DEBOUNCE_MS || reading == stableReading[i]) continue;
    stableReading[i] = reading;
    if (reading != LOW || currentQuestion == 0 || submitted) continue;
    if (i < 4) {
      selectedChoice = CHOICES[i];
      Serial.printf("Da chon %c. Bam Submit de nop.\n", selectedChoice);
    } else {
      submitChoice();
    }
  }
}

void setup() {
  Serial.begin(115200);
  for (int pin : BUTTON_PINS) pinMode(pin, INPUT_PULLUP);
  pinMode(LED_CONNECT, OUTPUT);
  pinMode(LED_NEXT, OUTPUT);
  digitalWrite(LED_CONNECT, LOW);
  digitalWrite(LED_NEXT, LOW);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastConnectAttempt = millis();
  Serial.println("ESP32 Wi-Fi dang ket noi...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setServerConnected(false);
    setNextLed(false);
    currentQuestion = 0;
    selectedChoice = '\0';
    answerAcked = false;
    if (millis() - lastConnectAttempt >= 5000) {
      lastConnectAttempt = millis();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      Serial.println("Dang ket noi lai Wi-Fi...");
    }
    delay(20);
    return;
  }
  unsigned long now = millis();
  if (lastServerCheck == 0 || now - lastServerCheck >= SERVER_CHECK_MS) {
    lastServerCheck = now;
    checkServer();
  }
  if (now - lastPoll >= POLL_MS) {
    lastPoll = now;
    pollQuestion();
  }
  if (currentQuestion != 0 && (lastHeartbeat == 0 || now - lastHeartbeat >= HEARTBEAT_MS)) {
    lastHeartbeat = now;
    sendHeartbeat();
  }
  scanButtons();
  blinkNextLed(millis());
  delay(10);
}
