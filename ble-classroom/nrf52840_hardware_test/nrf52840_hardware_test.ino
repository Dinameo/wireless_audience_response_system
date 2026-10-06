#include <Arduino.h>
#include <Adafruit_TinyUSB.h> // Enables USB Serial in the Adafruit nRF52 core.
#include <nrf_gpio.h>

// nRF52840 Pro Micro / nice!nano-style with raw Nordic pin labels.
// Each button goes from its GPIO to GND (internal pull-up enabled).
// Separate LEDs need a 220-330 ohm series resistor and their cathodes to GND.
constexpr uint32_t BUTTON_PINS[5] = {
  NRF_GPIO_PIN_MAP(0, 17), // A: 017
  NRF_GPIO_PIN_MAP(0, 20), // B: 020
  NRF_GPIO_PIN_MAP(0, 22), // C: 022
  NRF_GPIO_PIN_MAP(0, 24), // D: 024
  NRF_GPIO_PIN_MAP(1, 0),  // SUBMIT: 100
};
constexpr uint32_t LED_CONNECT = NRF_GPIO_PIN_MAP(0, 11); // 011
constexpr uint32_t LED_NEXT = NRF_GPIO_PIN_MAP(1, 4);    // 104
constexpr char CHOICES[] = "ABCD";

bool lastRaw[5] = {};
bool stablePressed[5] = {};
uint32_t changedAt[5] = {};
bool nextBlinking = true;
bool nextLedOn = true;
uint32_t lastBlinkAt = 0;
uint32_t lastReportAt = 0;
char selected = 0;
bool serialAnnounced = false;

void setNextLed(bool on) {
  nextLedOn = on;
  nrf_gpio_pin_write(LED_NEXT, on ? 1 : 0);
}

void onButtonPressed(uint8_t index) {
  if (index < 4) {
    selected = CHOICES[index];
    nextBlinking = true; // Simulate a NEXT notification for LED testing.
    setNextLed(true);
    lastBlinkAt = millis();
    Serial.print("BUTTON: ");
    Serial.println(selected);
  } else {
    Serial.print("SUBMIT: ");
    Serial.println(selected ? selected : '-');
    nextBlinking = false; // Simulate an ACK for LED testing.
    setNextLed(false);
    selected = 0;
  }
}

void setup() {
  Serial.begin(115200);
  nrf_gpio_cfg_output(LED_CONNECT);
  nrf_gpio_cfg_output(LED_NEXT);
  nrf_gpio_pin_write(LED_CONNECT, 0);
  setNextLed(false);

  for (uint8_t i = 0; i < 5; ++i) {
    nrf_gpio_cfg_input(BUTTON_PINS[i], NRF_GPIO_PIN_PULLUP);
  }

  delay(300);
  nrf_gpio_pin_write(LED_CONNECT, 1); // Test only: means the sketch is running, NOT a real BLE connection.
  nextBlinking = true;
  setNextLed(true);
  lastBlinkAt = millis();
}

void loop() {
  const uint32_t now = millis();

  if (Serial && !serialAnnounced) {
    Serial.println("NRF HARDWARE TEST: 017=A 020=B 022=C 024=D 100=SUBMIT");
    Serial.println("CONNECT LED steady = sketch running (not BLE connected).");
    Serial.println("NEXT LED blinks; press A/B/C/D, then SUBMIT to turn it off.");
    serialAnnounced = true;
  }

  for (uint8_t i = 0; i < 5; ++i) {
    const bool raw = nrf_gpio_pin_read(BUTTON_PINS[i]) == 0;
    if (raw != lastRaw[i]) {
      lastRaw[i] = raw;
      changedAt[i] = now;
    }
    if (raw != stablePressed[i] && now - changedAt[i] >= 30) {
      stablePressed[i] = raw;
      if (raw) onButtonPressed(i);
    }
  }

  if (nextBlinking && now - lastBlinkAt >= 250) {
    lastBlinkAt = now;
    setNextLed(!nextLedOn);
  }
  if (Serial && now - lastReportAt >= 2000) {
    lastReportAt = now;
    Serial.print("ALIVE pins A/B/C/D/SUBMIT = ");
    for (uint8_t i = 0; i < 5; ++i) {
      if (i) Serial.print('/');
      Serial.print(nrf_gpio_pin_read(BUTTON_PINS[i]) ? 1 : 0);
    }
    Serial.println("  (1=released, 0=pressed)");
  }
  delay(5);
}
