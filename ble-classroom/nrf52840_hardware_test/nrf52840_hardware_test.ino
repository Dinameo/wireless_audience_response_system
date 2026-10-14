
#include <bluefruit.h>
extern "C" {
#include <nrf_gpio.h>
}

#define CLIENT_ID "STUDENT_001"
#define DEVICE_NAME "BLE_QUIZ_CLIENT"
#define LED_CONNECT 11
#define LED_SENT 104
#define BUTTON_A 17
#define BUTTON_B 20
#define BUTTON_C 22
#define BUTTON_D 24
#define BUTTON_SUBMIT 100

// Preserve the pin numbers from the hardware table and translate only at the
// nrf_gpio API boundary (100 = P1.00, 104 = P1.04).
uint32_t nrfPin(uint32_t tablePin) {
  if (tablePin >= 100 && tablePin <= 115) return 32 + (tablePin - 100);
  return tablePin;
}

uint8_t QUIZ_SERVICE_UUID[] = {0x12,0x12,0x00,0x00,0x00,0x00,0x10,0x00,0x80,0x00,0x00,0x80,0x5F,0x9B,0x34,0xFB};
uint8_t QUIZ_CHARACTERISTIC_UUID[] = {0x12,0x12,0x00,0x01,0x00,0x00,0x10,0x00,0x80,0x00,0x00,0x80,0x5F,0x9B,0x34,0xFB};

// This Client is a connectable Peripheral/GATT Server. The quiz Server is Central/GATT Client.
BLEService quizService(QUIZ_SERVICE_UUID);
BLECharacteristic quizCharacteristic(QUIZ_CHARACTERISTIC_UUID);

volatile bool connected = false;
volatile bool authenticated = false;
volatile bool waitingAck = false;
volatile bool idSent = false;
volatile bool questionActive = false;
volatile bool answerSelected = false;
volatile char selectedAnswer = '\0';
uint16_t activeConnHandle = BLE_CONN_HANDLE_INVALID;
bool sentBlinkActive = false;
bool sentLedOn = false;
uint32_t sentBlinkToggled = 0;

void write_callback(uint16_t conn_hdl, BLECharacteristic* chr, uint8_t* data, uint16_t len);
void connect_callback(uint16_t conn_hdl);
void disconnect_callback(uint16_t conn_hdl, uint8_t reason);
void checkButtons();
void sendAnswer(char answer);
void processServerMessage(const char* message);
void waitButtonRelease(uint32_t pin);
void updateSentBlink();

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("BLE QUIZ CLIENT - Peripheral advertising");
  Serial.print("CLIENT ID: "); Serial.println(CLIENT_ID);

  nrf_gpio_cfg_output(LED_CONNECT);
  nrf_gpio_cfg_output(nrfPin(LED_SENT));
  // Wake the nRF from low-power idle when any active-low answer button is pressed.
  nrf_gpio_cfg_sense_input(BUTTON_A, NRF_GPIO_PIN_PULLUP, NRF_GPIO_PIN_SENSE_LOW);
  nrf_gpio_cfg_sense_input(BUTTON_B, NRF_GPIO_PIN_PULLUP, NRF_GPIO_PIN_SENSE_LOW);
  nrf_gpio_cfg_sense_input(BUTTON_C, NRF_GPIO_PIN_PULLUP, NRF_GPIO_PIN_SENSE_LOW);
  nrf_gpio_cfg_sense_input(BUTTON_D, NRF_GPIO_PIN_PULLUP, NRF_GPIO_PIN_SENSE_LOW);
  nrf_gpio_cfg_sense_input(nrfPin(BUTTON_SUBMIT), NRF_GPIO_PIN_PULLUP, NRF_GPIO_PIN_SENSE_LOW);
  nrf_gpio_pin_clear(LED_CONNECT);
  nrf_gpio_pin_clear(nrfPin(LED_SENT));

  Bluefruit.begin(1, 0); // one Peripheral, no Central role
  Bluefruit.setName(DEVICE_NAME);
  Bluefruit.setTxPower(4);

  quizService.begin();
  quizCharacteristic.setProperties(CHR_PROPS_WRITE | CHR_PROPS_NOTIFY);
  quizCharacteristic.setPermission(SECMODE_OPEN, SECMODE_OPEN);
  quizCharacteristic.setMaxLen(32);
  quizCharacteristic.setWriteCallback(write_callback);
  quizCharacteristic.begin();

  Bluefruit.Periph.setConnectCallback(connect_callback);
  Bluefruit.Periph.setDisconnectCallback(disconnect_callback);

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(quizService);
  // The 128-bit service UUID uses most of the advertising payload; put the full name
  // in the scan response so it is not silently omitted from the primary packet.
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  // Discoverable quickly at boot, then advertise at a low duty cycle (1 second).
  Bluefruit.Advertising.setInterval(160, 1600); // 100 ms fast, 1 s slow (0.625 ms units)
  Bluefruit.Advertising.setFastTimeout(10);
  Bluefruit.Advertising.start(0);
  Serial.print("Advertising name: "); Serial.println(DEVICE_NAME);
}

void loop() {
  updateSentBlink();
  // Send the Client ID as soon as the Central has enabled notifications.
  if (connected && !idSent && activeConnHandle != BLE_CONN_HANDLE_INVALID &&
      quizCharacteristic.notifyEnabled(activeConnHandle)) {
    char idMessage[32];
    snprintf(idMessage, sizeof(idMessage), "ID:%s", CLIENT_ID);
    if (quizCharacteristic.notify(activeConnHandle, (uint8_t*)idMessage, strlen(idMessage))) {
      idSent = true;
      Serial.print("TX: "); Serial.println(idMessage);
    }
  }
  if (connected && authenticated && questionActive && !waitingAck) checkButtons();
  // Sleep until a BLE event, timer, or button GPIO sense event wakes the MCU.
  sd_app_evt_wait();
}

void connect_callback(uint16_t conn_hdl) {
  activeConnHandle = conn_hdl;
  connected = true;
  authenticated = false;
  waitingAck = false;
  idSent = false;
  questionActive = false;
  answerSelected = false;
  selectedAnswer = '\0';
  sentBlinkActive = false;
  nrf_gpio_pin_clear(LED_CONNECT);
  nrf_gpio_pin_clear(nrfPin(LED_SENT));
  Serial.println("Server connected; waiting for Client ID");
}

void disconnect_callback(uint16_t conn_hdl, uint8_t reason) {
  (void)conn_hdl;
  (void)reason;
  connected = false;
  authenticated = false;
  waitingAck = false;
  idSent = false;
  questionActive = false;
  answerSelected = false;
  selectedAnswer = '\0';
  sentBlinkActive = false;
  activeConnHandle = BLE_CONN_HANDLE_INVALID;
  nrf_gpio_pin_clear(LED_CONNECT);
  nrf_gpio_pin_clear(nrfPin(LED_SENT));
  Serial.println("Server disconnected; advertising resumes");
}

void write_callback(uint16_t conn_hdl, BLECharacteristic* chr, uint8_t* data, uint16_t len) {
  (void)chr;
  if (!len) return;
  char message[33];
  if (len > 32) len = 32;
  memcpy(message, data, len);
  message[len] = '\0';
  Serial.print("RX: "); Serial.println(message);

  if (conn_hdl == activeConnHandle) processServerMessage(message);
}

void processServerMessage(const char* message) {
  if (strcmp(message, "ACCEPT") == 0) {
    authenticated = true;
    questionActive = false; // Wait for NEXT before accepting an answer.
    answerSelected = false;
    sentBlinkActive = false;
    sentLedOn = false;
    nrf_gpio_pin_clear(nrfPin(LED_SENT));
    nrf_gpio_pin_set(LED_CONNECT);
    Serial.println("AUTHENTICATION ACCEPTED");
  } else if (strcmp(message, "REJECT") == 0) {
    authenticated = false;
    questionActive = false;
    answerSelected = false;
    sentBlinkActive = false;
    sentLedOn = false;
    nrf_gpio_pin_clear(LED_CONNECT);
    nrf_gpio_pin_clear(nrfPin(LED_SENT));
    Serial.println("AUTHENTICATION REJECTED");
  } else if (strcmp(message, "ACK") == 0) {
    if (waitingAck) {
      waitingAck = false;
      questionActive = false;
      sentBlinkActive = false;
      sentLedOn = false;
      nrf_gpio_pin_clear(nrfPin(LED_SENT));
      Serial.println("ANSWER ACKNOWLEDGED; LED_SENT OFF");
    } else {
      Serial.println("Unexpected ACK ignored");
    }
  } else if (strcmp(message, "NEXT") == 0) {
    waitingAck = false;
    questionActive = authenticated;
    answerSelected = false;
    selectedAnswer = '\0';
    sentBlinkActive = true;
    sentBlinkToggled = millis();
    sentLedOn = true;
    nrf_gpio_pin_set(nrfPin(LED_SENT));
    Serial.println("NEXT QUESTION; LED_SENT blinks continuously, 0.5 s per cycle");
  } else if (strcmp(message, "DISCONNECT") == 0) {
    authenticated = false;
    waitingAck = false;
    questionActive = false;
    answerSelected = false;
    sentBlinkActive = false;
    sentLedOn = false;
    nrf_gpio_pin_clear(LED_CONNECT);
    nrf_gpio_pin_clear(nrfPin(LED_SENT));
    Serial.println("Server requested disconnect");
    delay(100);
    if (activeConnHandle != BLE_CONN_HANDLE_INVALID) Bluefruit.disconnect(activeConnHandle);
  }
}

void checkButtons() {
  if (nrf_gpio_pin_read(BUTTON_A) == 0) { selectedAnswer = 'A'; answerSelected = true; Serial.println("Selected A; press SUBMIT to send"); waitButtonRelease(BUTTON_A); }
  else if (nrf_gpio_pin_read(BUTTON_B) == 0) { selectedAnswer = 'B'; answerSelected = true; Serial.println("Selected B; press SUBMIT to send"); waitButtonRelease(BUTTON_B); }
  else if (nrf_gpio_pin_read(BUTTON_C) == 0) { selectedAnswer = 'C'; answerSelected = true; Serial.println("Selected C; press SUBMIT to send"); waitButtonRelease(BUTTON_C); }
  else if (nrf_gpio_pin_read(BUTTON_D) == 0) { selectedAnswer = 'D'; answerSelected = true; Serial.println("Selected D; press SUBMIT to send"); waitButtonRelease(BUTTON_D); }
  else if (nrf_gpio_pin_read(nrfPin(BUTTON_SUBMIT)) == 0) {
    if (answerSelected) sendAnswer(selectedAnswer);
    else Serial.println("Choose A/B/C/D before SUBMIT");
    waitButtonRelease(nrfPin(BUTTON_SUBMIT));
  }
}

void sendAnswer(char answer) {
  if (!authenticated || !questionActive || waitingAck || !answerSelected ||
      activeConnHandle == BLE_CONN_HANDLE_INVALID) return;
  char message[8];
  snprintf(message, sizeof(message), "ANS:%c", answer);
  if (quizCharacteristic.notify(activeConnHandle, (uint8_t*)message, strlen(message))) {
    waitingAck = true;
    questionActive = false;
    answerSelected = false;
    Serial.print("TX: "); Serial.println(message);
  } else {
    Serial.println("Send failed; press SUBMIT to retry");
  }
}

void updateSentBlink() {
  if (!sentBlinkActive) return;
  uint32_t now = millis();
  // 250 ms ON + 250 ms OFF = a repeating 0.5-second blink cycle.
  if ((uint32_t)(now - sentBlinkToggled) >= 250) {
    sentBlinkToggled = now;
    sentLedOn = !sentLedOn;
    if (sentLedOn) nrf_gpio_pin_set(nrfPin(LED_SENT));
    else nrf_gpio_pin_clear(nrfPin(LED_SENT));
  }
}

void waitButtonRelease(uint32_t pin) {
  delay(30);
  while (nrf_gpio_pin_read(pin) == 0) delay(5);
  delay(30);
}