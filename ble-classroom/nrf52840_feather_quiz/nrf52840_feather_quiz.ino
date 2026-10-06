#include <Arduino.h>
#include <bluefruit.h>

// Adafruit Feather nRF52840 Express. Edit to match "Mã thiết bị" on the web.
// This is a DEVICE ID, not necessarily the student's MSSV.
constexpr char DEVICE_ID[] = "STUDENT_001";

// Feather header labels. The raw Nordic pins 17/20/22/100/104 in the supplied
// PDF cannot all be wired on this board (QSPI/SWO/not bonded out).
constexpr uint8_t BUTTON_PINS[] = {5, 6, 9, 10, 11}; // A, B, C, D, SUBMIT
constexpr uint8_t LED_CONNECT = 12;
constexpr uint8_t LED_SENT = 13;
constexpr char CHOICES[] = "ABCD";

constexpr char SERVICE_UUID[] = "6a2f7ad9-2c64-4f13-8a7e-5b5a0a660d6e";
constexpr char TX_UUID[] = "d1484dd8-6d20-4d49-a6f1-4638f9d44c25"; // notify -> gateway
constexpr char RX_UUID[] = "b0f9c817-2d2b-4f28-9ae5-5dd6ca5f5d48"; // write <- gateway

BLEService quizService(SERVICE_UUID);
BLECharacteristic txChar(TX_UUID);
BLECharacteristic rxChar(RX_UUID);

enum class State { DISCONNECTED, WAIT_ACCEPT, READY, ANSWERING, WAIT_ACK };
State state = State::DISCONNECTED;
uint16_t connectionHandle = BLE_CONN_HANDLE_INVALID;
char selected = 0;
bool sentLedOn = false;
uint32_t lastBlinkMs = 0;
uint32_t lastIdMs = 0;
bool stablePressed[5] = {};
bool lastRawPressed[5] = {};
uint32_t lastChangeMs[5] = {};

void resetSession(State newState) {
  state = newState;
  selected = 0;
  sentLedOn = false;
  digitalWrite(LED_CONNECT, LOW);
  digitalWrite(LED_SENT, LOW);
}

void onConnect(uint16_t connHandle) {
  connectionHandle = connHandle;
  resetSession(State::WAIT_ACCEPT);
  lastIdMs = 0;
  Serial.println("BLE connected; waiting for notify subscription");
}

void onDisconnect(uint16_t connHandle, uint8_t reason) {
  (void) connHandle;
  (void) reason;
  connectionHandle = BLE_CONN_HANDLE_INVALID;
  resetSession(State::DISCONNECTED);
  Serial.println("BLE disconnected; advertising again");
}

void onWrite(uint16_t connHandle, BLECharacteristic *characteristic,
             uint8_t *data, uint16_t len) {
  (void) characteristic;
  if (connHandle != connectionHandle || len == 0 || len > 16) return;
  char cmd[17] = {};
  memcpy(cmd, data, len);
  Serial.print("RX: "); Serial.println(cmd);

  if (strcmp(cmd, "ACCEPT") == 0 && state == State::WAIT_ACCEPT) {
    state = State::READY;
    digitalWrite(LED_CONNECT, HIGH);
  } else if (strcmp(cmd, "REJECT") == 0) {
    resetSession(State::WAIT_ACCEPT);
  } else if (strcmp(cmd, "NEXT") == 0 &&
             (state == State::READY || state == State::WAIT_ACK || state == State::ANSWERING)) {
    // A new NEXT opens exactly one new answer slot. A/B/C/D alone never transmits.
    state = State::ANSWERING;
    selected = 0;
    sentLedOn = true;
    digitalWrite(LED_SENT, HIGH);
    lastBlinkMs = millis();
  } else if (strcmp(cmd, "ACK") == 0 && state == State::WAIT_ACK) {
    state = State::READY;
    selected = 0;
    sentLedOn = false;
    digitalWrite(LED_SENT, LOW);
  } else if (strcmp(cmd, "DISCONNECT") == 0) {
    Bluefruit.disconnect(connHandle);
  }
}

void press(uint8_t index) {
  if (state != State::ANSWERING) return;
  if (index < 4) {
    selected = CHOICES[index];
    Serial.print("Selected: "); Serial.println(selected);
  } else if (selected != 0 && connectionHandle != BLE_CONN_HANDLE_INVALID &&
             txChar.notifyEnabled(connectionHandle)) {
    char message[] = "ANS:X";
    message[4] = selected;
    if (txChar.notify(connectionHandle, message)) {
      state = State::WAIT_ACK; // no second submission before ACK/NEXT
      Serial.print("TX: "); Serial.println(message);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_CONNECT, OUTPUT);
  pinMode(LED_SENT, OUTPUT);
  resetSession(State::DISCONNECTED);
  for (uint8_t i = 0; i < 5; ++i) pinMode(BUTTON_PINS[i], INPUT_PULLUP);

  Bluefruit.begin(1, 0);
  Bluefruit.autoConnLed(false);
  Bluefruit.setName("BLE_QUIZ_CLIENT");
  Bluefruit.Periph.setConnectCallback(onConnect);
  Bluefruit.Periph.setDisconnectCallback(onDisconnect);

  quizService.begin();
  txChar.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
  txChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  txChar.setMaxLen(40);
  txChar.begin();
  rxChar.setProperties(CHR_PROPS_WRITE);
  rxChar.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN);
  rxChar.setMaxLen(16);
  rxChar.setWriteCallback(onWrite);
  rxChar.begin();

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addService(quizService);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setIntervalMS(100, 1000);
  Bluefruit.Advertising.setFastTimeout(10);
  Bluefruit.Advertising.start(0);
  Serial.println("Advertising BLE_QUIZ_CLIENT");
}

void loop() {
  const uint32_t now = millis();
  // Send ID only after the gateway has enabled notifications. Retry until ACCEPT.
  if (state == State::WAIT_ACCEPT && connectionHandle != BLE_CONN_HANDLE_INVALID &&
      txChar.notifyEnabled(connectionHandle) && (lastIdMs == 0 || now - lastIdMs >= 1000)) {
    char message[44];
    snprintf(message, sizeof(message), "ID:%s", DEVICE_ID);
    if (txChar.notify(connectionHandle, message)) {
      lastIdMs = now;
      Serial.print("TX: "); Serial.println(message);
    }
  }

  for (uint8_t i = 0; i < 5; ++i) {
    const bool raw = digitalRead(BUTTON_PINS[i]) == LOW;
    if (raw != lastRawPressed[i]) {
      lastRawPressed[i] = raw;
      lastChangeMs[i] = now;
    }
    if (raw != stablePressed[i] && now - lastChangeMs[i] >= 30) {
      stablePressed[i] = raw;
      if (raw) press(i);
    }
  }

  if ((state == State::ANSWERING || state == State::WAIT_ACK) && now - lastBlinkMs >= 250) {
    lastBlinkMs = now;
    sentLedOn = !sentLedOn;
    digitalWrite(LED_SENT, sentLedOn ? HIGH : LOW);
  }
  delay(5);
}
