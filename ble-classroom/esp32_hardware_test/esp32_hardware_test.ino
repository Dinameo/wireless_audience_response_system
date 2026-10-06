#include <Arduino.h>

// Hardware-only test for a classic ESP32 DevKit / ESP-WROOM-32.
// ESP32-C3/S3 boards have different pinouts: do not use this mapping on them.
#if !defined(CONFIG_IDF_TARGET_ESP32)
#error "This pin map is only for classic ESP32 DevKit / ESP-WROOM-32."
#endif

// Connect each normally-open button between its GPIO and GND.
// Connect each separate LED from its GPIO through a 220-330 ohm resistor
// to LED anode; connect LED cathode to GND.
constexpr uint8_t BUTTON_PINS[5] = {25, 26, 27, 32, 33}; // A B C D SUBMIT
constexpr uint8_t LED_CONNECT = 18;
constexpr uint8_t LED_NEXT = 19;
constexpr char CHOICES[] = "ABCD";

bool lastRaw[5] = {};
bool stablePressed[5] = {};
unsigned long changedAt[5] = {};
bool nextBlinking = true;
bool nextLedOn = true;
unsigned long lastBlinkAt = 0;
unsigned long lastReportAt = 0;
char selected = 0;

void setNextLed(bool on) {
  nextLedOn = on;
  digitalWrite(LED_NEXT, on ? HIGH : LOW);
}

void onButtonPressed(uint8_t index) {
  if (index < 4) {
    selected = CHOICES[index];
    nextBlinking = true; // Simulate NEXT for wiring test.
    setNextLed(true);
    lastBlinkAt = millis();
    Serial.print("BUTTON: ");
    Serial.println(selected);
  } else {
    Serial.print("SUBMIT: ");
    Serial.println(selected ? selected : '-');
    nextBlinking = false; // Simulate ACK for wiring test.
    setNextLed(false);
    selected = 0;
  }
}

void setup() {
  Serial.begin(115200);
  for (uint8_t pin : BUTTON_PINS) pinMode(pin, INPUT_PULLUP);
  pinMode(LED_CONNECT, OUTPUT);
  pinMode(LED_NEXT, OUTPUT);
  digitalWrite(LED_CONNECT, HIGH); // Test only: sketch running, NOT Wi-Fi connected.
  setNextLed(true);
  lastBlinkAt = millis();
  Serial.println("ESP32 HARDWARE TEST: 25=A 26=B 27=C 32=D 33=SUBMIT");
  Serial.println("CONNECT LED steady = sketch running, not Wi-Fi connected.");
  Serial.println("NEXT LED blinks; press A/B/C/D, then SUBMIT to turn it off.");
}

void loop() {
  const unsigned long now = millis();
  for (uint8_t i = 0; i < 5; ++i) {
    const bool raw = digitalRead(BUTTON_PINS[i]) == LOW;
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
  if (now - lastReportAt >= 2000) {
    lastReportAt = now;
    Serial.print("ALIVE pins A/B/C/D/SUBMIT = ");
    for (uint8_t i = 0; i < 5; ++i) {
      if (i) Serial.print('/');
      Serial.print(digitalRead(BUTTON_PINS[i]));
    }
    Serial.println("  (1=released, 0=pressed)");
  }
  delay(5);
}
