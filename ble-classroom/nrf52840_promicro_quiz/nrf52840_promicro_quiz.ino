#include <Arduino.h>
#include <Adafruit_TinyUSB.h> // Enables USB Serial in the Adafruit nRF52 core.
#include <bluefruit.h>
#include <nrf_gpio.h>

// nRF52840 Pro Micro / nice!nano-style board with RAW NORDIC pin labels.
// The nRF52840 factory device ID is different on every chip. Flash the SAME
// sketch to every board, then copy its printed ID into "Mã thiết bị" on the web.
// This is an identifier, not a secret or exam authentication credential.
char deviceId[21] = {};

// Printed board label 017 means P0.17, 100 means P1.00, etc.
// These follow the supplied PDF exactly. Do not use Arduino D numbers here.
constexpr uint32_t BUTTON_PINS[] = {
  NRF_GPIO_PIN_MAP(0, 17), // A: 017
  NRF_GPIO_PIN_MAP(0, 20), // B: 020
  NRF_GPIO_PIN_MAP(0, 22), // C: 022
  NRF_GPIO_PIN_MAP(0, 24), // D: 024
  NRF_GPIO_PIN_MAP(1, 0),  // SUBMIT: 100
};
// Two active-high LEDs: connect on 011, NEXT/ACK on 104.
// A common-cathode RGB module may still use its B and G channels instead.
constexpr uint32_t LED_CONNECT = NRF_GPIO_PIN_MAP(0, 11); // 011
constexpr uint32_t LED_NEXT = NRF_GPIO_PIN_MAP(1, 4);    // 104
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
bool nextLedOn = false;
uint32_t lastBlinkMs = 0;
uint32_t lastIdMs = 0;
bool stablePressed[5] = {};
bool lastRawPressed[5] = {};
uint32_t lastChangeMs[5] = {};

void setConnect(bool on) { nrf_gpio_pin_write(LED_CONNECT, on ? 1 : 0); }
void setNext(bool on) { nrf_gpio_pin_write(LED_NEXT, on ? 1 : 0); }

void resetSession(State newState) {
  state = newState;
  selected = 0;
  nextLedOn = false;
  setConnect(connectionHandle != BLE_CONN_HANDLE_INVALID);
  setNext(false);
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
  } else if (strcmp(cmd, "REJECT") == 0) {
    resetSession(State::WAIT_ACCEPT);
  } else if (strcmp(cmd, "NEXT") == 0 &&
             (state == State::READY || state == State::WAIT_ACK || state == State::ANSWERING)) {
    state = State::ANSWERING;
    selected = 0;
    nextLedOn = true;
    setNext(true);
    lastBlinkMs = millis();
  } else if (strcmp(cmd, "ACK") == 0 && state == State::WAIT_ACK) {
    state = State::READY;
    selected = 0;
    nextLedOn = false;
    setNext(false);
  } else if (strcmp(cmd, "DISCONNECT") == 0) {
    Bluefruit.disconnect(connHandle);
  }
}

void press(uint8_t index) {
  if (index == 4) {
    Serial.print("SUBMIT debounced; state=");
    Serial.print(static_cast<int>(state));
    Serial.print(" selected=");
    Serial.println(selected ? selected : '-');
  }
  if (state != State::ANSWERING) return;
  if (index < 4) {
    selected = CHOICES[index];
    Serial.print("Selected: "); Serial.println(selected);
  } else {
    if (selected == 0) {
      Serial.println("SUBMIT ignored: no choice selected");
      return;
    }
    if (connectionHandle == BLE_CONN_HANDLE_INVALID || !txChar.notifyEnabled(connectionHandle)) {
      Serial.println("SUBMIT ignored: BLE notify unavailable");
      return;
    }
    char message[] = "ANS:X";
    message[4] = selected;
    if (txChar.notify(connectionHandle, message)) {
      state = State::WAIT_ACK;
      Serial.print("TX: "); Serial.println(message);
    } else {
      Serial.println("SUBMIT failed: BLE notify returned false");
    }
  }
}

void setup() {
  Serial.begin(115200);
  snprintf(deviceId, sizeof(deviceId), "NRF-%08lX%08lX",
           static_cast<unsigned long>(NRF_FICR->DEVICEID[1]),
           static_cast<unsigned long>(NRF_FICR->DEVICEID[0]));
  Serial.print("Device ID: "); Serial.println(deviceId);
  nrf_gpio_cfg_output(LED_CONNECT);
  nrf_gpio_cfg_output(LED_NEXT);
  resetSession(State::DISCONNECTED);
  for (uint8_t i = 0; i < 5; ++i) {
    nrf_gpio_cfg_input(BUTTON_PINS[i], NRF_GPIO_PIN_PULLUP);
  }

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
  if (state == State::WAIT_ACCEPT && connectionHandle != BLE_CONN_HANDLE_INVALID &&
      txChar.notifyEnabled(connectionHandle) && (lastIdMs == 0 || now - lastIdMs >= 1000)) {
    char message[44];
    snprintf(message, sizeof(message), "ID:%s", deviceId);
    if (txChar.notify(connectionHandle, message)) {
      lastIdMs = now;
      Serial.print("TX: "); Serial.println(message);
    }
  }

  for (uint8_t i = 0; i < 5; ++i) {
    const bool raw = nrf_gpio_pin_read(BUTTON_PINS[i]) == 0;
    if (raw != lastRawPressed[i]) {
      lastRawPressed[i] = raw;
      lastChangeMs[i] = now;
      if (i == 4) Serial.println(raw ? "SUBMIT pin LOW" : "SUBMIT pin HIGH");
    }
    if (raw != stablePressed[i] && now - lastChangeMs[i] >= 30) {
      stablePressed[i] = raw;
      if (raw) press(i);
    }
  }

  if ((state == State::ANSWERING || state == State::WAIT_ACK) && now - lastBlinkMs >= 250) {
    lastBlinkMs = now;
    nextLedOn = !nextLedOn;
    setNext(nextLedOn);
  }
  delay(5);
}
