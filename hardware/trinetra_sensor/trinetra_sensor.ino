// त्रिNetra kiosk sensor: ESP8266 NodeMCU or ESP32 + HW-201 IR obstacle sensor + KY-016 RGB LED.
// Board: "NodeMCU 1.0 (ESP-12E Module)" or "ESP32 Dev Module". Serial 115200 baud, newline-delimited.
//
// Device -> kiosk, every 50 ms:
//   {"t":"ir","present":1,"raw":612,"ms":123456,"n":"a1b2c3d4"}
//     present  1 when HW-201 OUT is LOW (something in front of the sensor)
//     raw      averaged A0 value (0-1023). Only meaningful if the optional analog tap is wired.
//     ms       device uptime, lets the kiosk detect a frozen stream
//     n        last nonce the kiosk sent (binds readings to the current scan)
// Device -> kiosk, on boot or HELLO:
//   {"t":"hello","id":"trinetra-esp8266","fw":1}
// Kiosk -> device:
//   ALLOW | STEPUP | DENY | OFFLINE | SCAN | IDLE   set the status LED
//   N <hex nonce, up to 16 chars>                    set the nonce echoed in readings
//   HELLO                                            re-send identification
//
// Wiring (see HARDWARE.md):
//   HW-201  VCC->3V3  GND->GND  OUT->D5
//   KY-016  R->D6  G->D7  B->D2  (220 ohm in series if the module has no resistors)  "-"->GND
//   Optional: HW-201 receiver node (LM393 input that changes smoothly with distance) -> A0

// Works on both boards. Select the board in Arduino IDE and the right pins are used:
//   ESP8266 NodeMCU:  IR OUT D5, LED R D6 / G D7 / B D2, analog A0
//   ESP32 DevKit:     IR OUT GPIO27, LED R GPIO25 / G GPIO26 / B GPIO33, analog GPIO34
#if defined(ESP32)
  #include <WiFi.h>
  const uint8_t IR_OUT = 27;
  const uint8_t LED_R = 25, LED_G = 26, LED_B = 33;
  const uint8_t IR_ANALOG = 34;
  int readRaw() { return analogRead(IR_ANALOG) >> 2; }  // 12-bit -> 0..1023
#else
  #include <ESP8266WiFi.h>
  const uint8_t IR_OUT = D5;
  const uint8_t LED_R = D6, LED_G = D7, LED_B = D2;
  int readRaw() { return analogRead(A0); }
#endif
const unsigned long PERIOD_MS = 50;
const unsigned long LED_TIMEOUT_MS = 15000;  // decision colours fade back to idle

String line;
char nonce[17] = "";
unsigned long lastSample = 0, ledSetAt = 0;
bool ledHolds = false;   // OFFLINE and IDLE stay on; decisions time out
bool scanning = false;

// No series resistors on hand: cap the PWM duty so average current per pin stays low.
// If you add 220 ohm resistors (or your KY-016 has them on board), set this to 255.
const uint8_t LED_MAX = 50;

void color(uint8_t r, uint8_t g, uint8_t b) {
  analogWrite(LED_R, (uint16_t)r * LED_MAX / 255);
  analogWrite(LED_G, (uint16_t)g * LED_MAX / 255);
  analogWrite(LED_B, (uint16_t)b * LED_MAX / 255);
}

void hello() {
  Serial.println(F("{\"t\":\"hello\",\"id\":\"trinetra-esp8266\",\"fw\":1}"));
}

void setLed(const String& cmd) {
  scanning = false;
  ledHolds = false;
  ledSetAt = millis();
  if (cmd == "ALLOW") color(0, 255, 0);
  else if (cmd == "DENY") color(255, 0, 0);
  else if (cmd == "STEPUP") color(255, 110, 0);
  else if (cmd == "OFFLINE") { color(0, 0, 255); ledHolds = true; }
  else if (cmd == "SCAN") { scanning = true; ledHolds = true; }
  else { color(0, 0, 0); ledHolds = true; }
}

void handle(String cmd) {
  cmd.trim();
  if (cmd.startsWith("N ")) {
    String n = cmd.substring(2);
    n.trim();
    size_t len = 0;
    for (size_t i = 0; i < n.length() && len < 16; i++) {
      char c = n[i];
      if (isxdigit(c)) nonce[len++] = c;
    }
    nonce[len] = '\0';
  } else if (cmd == "HELLO") {
    hello();
  } else if (cmd.length()) {
    setLed(cmd);
  }
}

void setup() {
  WiFi.mode(WIFI_OFF);  // not needed, and it adds noise to the ADC
  Serial.begin(115200);
  pinMode(IR_OUT, INPUT);
  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);
#if !defined(ESP32)
  WiFi.forceSleepBegin();
  analogWriteRange(255);
#endif
  // Power-on self test: R, G, B
  color(80, 0, 0); delay(150);
  color(0, 80, 0); delay(150);
  color(0, 0, 80); delay(150);
  color(0, 0, 0);
  hello();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { handle(line); line = ""; }
    else if (c != '\r' && line.length() < 40) line += c;
  }

  unsigned long now = millis();
  if (scanning) {  // soft white pulse while the kiosk is scanning
    uint8_t v = 40 + (uint8_t)(100 * (0.5 + 0.5 * sin(now / 120.0)));
    color(v, v, v);
  }
  if (!ledHolds && now - ledSetAt > LED_TIMEOUT_MS) { color(0, 0, 0); ledHolds = true; }

  if (now - lastSample >= PERIOD_MS) {
    lastSample = now;
    long sum = 0;
    for (int i = 0; i < 8; i++) sum += readRaw();
    int present = digitalRead(IR_OUT) == LOW ? 1 : 0;
    Serial.printf("{\"t\":\"ir\",\"present\":%d,\"raw\":%ld,\"ms\":%lu,\"n\":\"%s\"}\n",
                  present, sum / 8, now, nonce);
  }
}
