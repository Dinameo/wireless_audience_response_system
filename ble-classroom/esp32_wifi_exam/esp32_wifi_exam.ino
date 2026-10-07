// NEXUS Classroom — classic ESP32 DevKit (not ESP32-C3/S3).
// Wire five normally-open buttons between each GPIO and GND.
// Each separate LED needs its own 220–330 ohm series resistor to GND.
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include <cstring>

// Edit these four values before uploading. Never commit real Wi-Fi credentials
// or a device token to a public GitHub repository.
const char *WIFI_SSID = "thanh tung";
const char *WIFI_PASSWORD = "viet123nam";
const char *SERVER_URL = "http://192.168.2.7:8000";  // Laptop LAN IP; never localhost.
const char *DEVICE_TOKEN = "0RptOuVG99-Zew-rVnW1rVhM2bHh6dyw4PIrLm2d09c";

const int BUTTON_PINS[5] = {25, 26, 27, 32, 33};  // A, B, C, D, Submit.
const int LED_CONNECT = 18;  // On only after the server accepts this device token.
const int LED_NEXT = 19;     // Blink for a new question until answer ACK.
const char CHOICES[4] = {'A', 'B', 'C', 'D'};
const unsigned long POLL_MS = 1000;
const unsigned long HEARTBEAT_MS = 5000;
const unsigned long SERVER_CHECK_MS = 5000;
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 20000;
const unsigned long WIFI_RETRY_MS = 5000;
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
unsigned long lastServerCheck = 0;
unsigned long lastBlink = 0;
unsigned long wifiAttemptStarted = 0;
unsigned long wifiRetryStarted = 0;
unsigned long lastServerErrorLog = 0;
bool configReady = false;
bool wifiAttemptActive = false;
bool wifiWasConnected = false;
int lastServerCode = 0;

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

void clearQuestion() {
  currentQuestion = 0;
  selectedChoice = '\0';
  submitted = false;
  answerAcked = false;
  setNextLed(false);
}

bool validateConfig() {
  if (!WIFI_SSID[0] || std::strcmp(WIFI_SSID, "YOUR_WIFI_SSID") == 0 ||
      std::strcmp(WIFI_PASSWORD, "YOUR_WIFI_PASSWORD") == 0 ||
      !DEVICE_TOKEN[0] || std::strcmp(DEVICE_TOKEN, "PASTE_ONE_TIME_ESP32_TOKEN") == 0 ||
      std::strstr(SERVER_URL, "YOUR_SERVER_IP") != nullptr) {
    Serial.println("Chua dien Wi-Fi/IP server/token o dau file .ino. Khong in mat khau hay token ra Serial.");
    return false;
  }
  if (std::strncmp(SERVER_URL, "http://", 7) != 0) {
    Serial.println("SERVER_URL phai bat dau bang http:// va dung IP LAN cua may web.");
    return false;
  }
  return true;
}

// Begin only once. After a timeout, explicitly stop the attempt and wait before
// WiFi.reconnect(); calling WiFi.begin() every five seconds while STA is still
// connecting causes "wifi:sta is connecting, cannot set config".
void startWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  wifiAttemptActive = true;
  wifiAttemptStarted = millis();
  Serial.println("ESP32 dang ket noi Wi-Fi...");
}

bool maintainWifi(unsigned long now) {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      wifiAttemptActive = false;
      lastServerCheck = 0;  // Authenticate with the web immediately.
      lastPoll = 0;
      Serial.print("Wi-Fi da ket noi. IP cua ESP32: ");
      Serial.println(WiFi.localIP());
    }
    return true;
  }

  if (wifiWasConnected) {
    wifiWasConnected = false;
    setServerConnected(false);
    clearQuestion();
    WiFi.disconnect(false, false);
    wifiAttemptActive = false;
    wifiRetryStarted = now;
    Serial.println("Mat Wi-Fi; se thu lai sau 5 giay.");
  }
  if (wifiAttemptActive && now - wifiAttemptStarted >= WIFI_CONNECT_TIMEOUT_MS) {
    Serial.printf("Wi-Fi chua ket noi sau 20 giay (status=%d). Kiem tra SSID/mat khau/song Wi-Fi.\n",
                  static_cast<int>(WiFi.status()));
    WiFi.disconnect(false, false);
    wifiAttemptActive = false;
    wifiRetryStarted = now;
  }
  if (!wifiAttemptActive && now - wifiRetryStarted >= WIFI_RETRY_MS) {
    wifiRetryStarted = now;
    wifiAttemptActive = WiFi.reconnect();
    if (wifiAttemptActive) {
      wifiAttemptStarted = now;
      Serial.println("Dang thu ket noi lai Wi-Fi...");
    } else {
      Serial.println("Chua bat dau duoc ket noi Wi-Fi; se thu lai sau 5 giay.");
    }
  }
  return false;
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
  if (std::strcmp(method, "POST") == 0) {
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
  if (code == 200) {
    if (!serverConnected) lastPoll = 0;
    setServerConnected(true);
  } else {
    setServerConnected(false);
    clearQuestion();
    const unsigned long now = millis();
    if (code != lastServerCode || now - lastServerErrorLog >= 30000) {
      if (code == 401) {
        Serial.println("Token ESP32 sai/da thu hoi. Cap lai token tren web roi nap lai bo.");
      } else {
        Serial.printf("Web chua nhan ESP32 (HTTP %d). Kiem tra SERVER_URL va mang LAN.\n", code);
      }
      lastServerErrorLog = now;
    }
  }
  lastServerCode = code;
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
    clearQuestion();
  } else if (code == 401) {
    setServerConnected(false);
    clearQuestion();
    Serial.println("Token ESP32 sai/da thu hoi. Cap lai token tren web roi nap lai bo.");
  } else {
    if (code < 0) {
      setServerConnected(false);
      clearQuestion();
    }
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
  if (code != 202) {
    Serial.printf("Heartbeat chua duoc nhan (HTTP %d).\n", code);
    if (code == 401) {
      setServerConnected(false);
      clearQuestion();
    }
  }
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
    if (code < 0 || code == 401) {
      setServerConnected(false);
      clearQuestion();
      Serial.printf("Chua nop duoc (HTTP %d). Cho web ket noi lai roi chon dap an moi.\n", code);
    } else {
      Serial.printf("Chua nop duoc (HTTP %d). Bam Submit de thu lai.\n", code);
    }
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
  configReady = validateConfig();
  if (configReady) startWifi();
}

void loop() {
  if (!configReady) {
    delay(1000);
    return;
  }
  if (!maintainWifi(millis())) {
    scanButtons();  // Track releases while offline; never submit without a question.
    delay(10);
    return;
  }
  unsigned long now = millis();
  if (lastServerCheck == 0 || now - lastServerCheck >= SERVER_CHECK_MS) {
    lastServerCheck = now;
    checkServer();
  }
  if (!serverConnected) {
    scanButtons();
    delay(10);
    return;
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
