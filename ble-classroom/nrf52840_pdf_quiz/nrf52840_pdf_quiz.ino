#include <Arduino.h>
#include <Adafruit_TinyUSB.h>
#include <bluefruit.h>
#include <nrf_gpio.h>

// BLE Client flow in BLE_Client_luong_hoat_dong_va_phan_cung.pdf.
// This nRF52840 board is a BLE peripheral/GATT server. The laptop gateway is
// the BLE central/GATT client. Give EACH physical board a different ID.
constexpr char CLIENT_ID[] = "STUDENT_001";
static_assert(sizeof(CLIENT_ID) - 1 + 3 <= 20,
              "ID: plus CLIENT_ID must fit one default BLE notification");

// Raw labels printed on the nRF52840 Pro Micro / nice!nano-style board.
// Each button connects its GPIO to GND; internal pull-ups are enabled.
constexpr uint32_t LED_CONNECT = 11;  // 011 = P0.11; lights only after ACCEPT.
constexpr uint32_t LED_SENT = 104;    // 104 = P1.04; blinks NEXT through ACK.
constexpr uint32_t BUTTON_PINS[5] = {17, 20, 22, 24, 100}; // A B C D SUBMIT.
constexpr char CHOICES[] = "ABCD";

uint32_t nrfPin(uint32_t label) {
  return label >= 100 && label <= 115 ? NRF_GPIO_PIN_MAP(1, label - 100)
                                      : NRF_GPIO_PIN_MAP(0, label);
}

// Bluefruit's byte-array UUID constructor expects on-air little-endian order.
// Gateway sees service fb349b5f-8000-0080-0010-000000001212 and one
// Notify+Write characteristic fb349b5f-8000-0080-0010-000001001212.
uint8_t QUIZ_SERVICE_UUID[] = {
  0x12, 0x12, 0x00, 0x00, 0x00, 0x00, 0x10, 0x00,
  0x80, 0x00, 0x00, 0x80, 0x5F, 0x9B, 0x34, 0xFB
};
uint8_t QUIZ_CHARACTERISTIC_UUID[] = {
  0x12, 0x12, 0x00, 0x01, 0x00, 0x00, 0x10, 0x00,
  0x80, 0x00, 0x00, 0x80, 0x5F, 0x9B, 0x34, 0xFB
};
BLEService quizService(QUIZ_SERVICE_UUID);
BLECharacteristic quizCharacteristic(QUIZ_CHARACTERISTIC_UUID);

enum class State { DISCONNECTED, WAIT_ACCEPT, READY, ANSWERING, WAIT_ACK };
State state = State::DISCONNECTED;
uint16_t connectionHandle = BLE_CONN_HANDLE_INVALID;
uint32_t lastIdMs = 0;
uint32_t lastBlinkMs = 0;
uint32_t lastChangeMs[5] = {};
bool lastRawPressed[5] = {};
bool stablePressed[5] = {};
bool sentLedOn = false;
char selected = 0;
bool disconnectRequested = false;
uint32_t disconnectRequestedAt = 0;

void setConnect(bool on) { nrf_gpio_pin_write(nrfPin(LED_CONNECT), on ? 1 : 0); }
void setSent(bool on) {
  sentLedOn = on;
  nrf_gpio_pin_write(nrfPin(LED_SENT), on ? 1 : 0);
}

void resetSession() {
  selected = 0;
  lastIdMs = 0;
  setConnect(false);
  setSent(false);
}

void onConnect(uint16_t handle) {
  connectionHandle = handle;
  state = State::WAIT_ACCEPT;
  resetSession();
  Serial.println("BLE linked; waiting for notify and ACCEPT");
}

void onDisconnect(uint16_t handle, uint8_t reason) {
  (void)handle;
  (void)reason;
  connectionHandle = BLE_CONN_HANDLE_INVALID;
  disconnectRequested = false;
  state = State::DISCONNECTED;
  resetSession();
  Serial.println("BLE disconnected; advertising again");
}

void onWrite(uint16_t handle, BLECharacteristic *characteristic,
             uint8_t *data, uint16_t len) {
  (void)characteristic;
  if (handle != connectionHandle || len == 0 || len > 16) return;
  char command[17] = {};
  memcpy(command, data, len);
  Serial.print("RX: "); Serial.println(command);

  if (strcmp(command, "ACCEPT") == 0 && state == State::WAIT_ACCEPT) {
    state = State::READY;
    setConnect(true);
  } else if (strcmp(command, "REJECT") == 0) {
    state = State::WAIT_ACCEPT;
    resetSession();
  } else if (strcmp(command, "NEXT") == 0 &&
             (state == State::READY || state == State::ANSWERING ||
              state == State::WAIT_ACK)) {
    state = State::ANSWERING;
    selected = 0;
    setSent(true);
    lastBlinkMs = millis();
  } else if (strcmp(command, "ACK") == 0 && state == State::WAIT_ACK) {
    state = State::READY;
    selected = 0;
    setSent(false);
  } else if (strcmp(command, "DISCONNECT") == 0) {
    // Let the GATT Write response leave the board before ending the link.
    disconnectRequested = true;
    disconnectRequestedAt = millis();
  }
}

void onButtonPressed(uint8_t index) {
  // No answer may be selected or submitted before NEXT.
  if (state != State::ANSWERING) return;
  if (index < 4) {
    selected = CHOICES[index];
    Serial.print("Selected: "); Serial.println(selected);
    return;
  }
  if (!selected || connectionHandle == BLE_CONN_HANDLE_INVALID ||
      !quizCharacteristic.notifyEnabled(connectionHandle)) {
    Serial.println("SUBMIT ignored: select A/B/C/D after NEXT");
    return;
  }
  char message[] = "ANS:X";
  message[4] = selected;
  if (quizCharacteristic.notify(connectionHandle,
                                reinterpret_cast<uint8_t *>(message), 5)) {
    state = State::WAIT_ACK;
    Serial.print("TX: "); Serial.println(message);
  } else {
    Serial.println("Notify failed; press SUBMIT again");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.print("CLIENT ID: "); Serial.println(CLIENT_ID);
  nrf_gpio_cfg_output(nrfPin(LED_CONNECT));
  nrf_gpio_cfg_output(nrfPin(LED_SENT));
  resetSession();
  for (uint8_t i = 0; i < 5; ++i)
    nrf_gpio_cfg_input(nrfPin(BUTTON_PINS[i]), NRF_GPIO_PIN_PULLUP);

  Bluefruit.begin(1, 0);
  Bluefruit.autoConnLed(false);
  Bluefruit.setName("BLE_QUIZ_CLIENT");
  Bluefruit.setTxPower(4);
  Bluefruit.Periph.setConnectCallback(onConnect);
  Bluefruit.Periph.setDisconnectCallback(onDisconnect);

  quizService.begin();
  quizCharacteristic.setProperties(CHR_PROPS_WRITE | CHR_PROPS_NOTIFY);
  quizCharacteristic.setPermission(SECMODE_OPEN, SECMODE_OPEN);
  quizCharacteristic.setMaxLen(32);
  quizCharacteristic.setWriteCallback(onWrite);
  quizCharacteristic.begin();

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(quizService);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(160, 1600); // 100 ms, then 1 s.
  Bluefruit.Advertising.setFastTimeout(10);
  Bluefruit.Advertising.start(0);
  Serial.println("Advertising BLE_QUIZ_CLIENT (PDF GATT profile)");
}

void loop() {
  const uint32_t now = millis();
  if (disconnectRequested && now - disconnectRequestedAt >= 50) {
    disconnectRequested = false;
    if (connectionHandle != BLE_CONN_HANDLE_INVALID)
      Bluefruit.disconnect(connectionHandle);
  }
  if (state == State::WAIT_ACCEPT && connectionHandle != BLE_CONN_HANDLE_INVALID &&
      quizCharacteristic.notifyEnabled(connectionHandle) &&
      (lastIdMs == 0 || now - lastIdMs >= 1000)) {
    char message[21];
    snprintf(message, sizeof(message), "ID:%s", CLIENT_ID);
    if (quizCharacteristic.notify(connectionHandle,
                                  reinterpret_cast<uint8_t *>(message), strlen(message))) {
      lastIdMs = now;
      Serial.print("TX: "); Serial.println(message);
    }
  }

  for (uint8_t i = 0; i < 5; ++i) {
    const bool raw = nrf_gpio_pin_read(nrfPin(BUTTON_PINS[i])) == 0;
    if (raw != lastRawPressed[i]) {
      lastRawPressed[i] = raw;
      lastChangeMs[i] = now;
    }
    if (raw != stablePressed[i] && now - lastChangeMs[i] >= 30) {
      stablePressed[i] = raw;
      if (raw) onButtonPressed(i);
    }
  }

  // Non-blocking loop keeps the 250 ms on/off blink alive while a button is held.
  if ((state == State::ANSWERING || state == State::WAIT_ACK) &&
      now - lastBlinkMs >= 250) {
    lastBlinkMs = now;
    setSent(!sentLedOn);
  }
  delay(5);
}
