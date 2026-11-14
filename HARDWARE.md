# Minimal hardware extension for त्रिNetra

The practical minimum for the proposed **dual-wavelength experiment** is a USB ESP32 board, an integrated photodiode/amplifier receiver board, and two switched IR emitters. Keep the laptop webcam. A complete receiver such as an OPT101 breakout reduces the separate analog parts compared with a bare BPW34, but does not eliminate LED current limiting, drivers, decoupling and optical shielding.

| Part / assembly | Why it is needed |
| --- | --- |
| ESP32 development board + USB cable | Sequences measurements, samples the receiver and sends readings to the laptop. No Raspberry Pi required. |
| OPT101 photodiode + amplifier breakout, or an equivalent characterized analog receiver | Combines light receiver and transimpedance amplifier. Check the actual board's supply/output range against the ESP32 ADC. |
| One 850 nm LED and one 940 nm LED, each with a suitable current-limited switching circuit | Produces two separate controlled illumination measurements. Use rated face-facing emitters and verify optical safety for the actual assembly. |
| Small opaque enclosure / receiver baffle | Reduces direct LED-to-receiver leakage and restricts the sampled area; mount beside the webcam. |

This is about three electronic assemblies if the emitters/drivers share one board, **not three individual components**. A generic digital obstacle/line sensor is unsuitable: it reports a thresholded proximity signal, not calibrated reflected intensity.

[TI specifies the OPT101](https://www.ti.com/product/OPT101) as a monolithic photodiode with an on-chip transimpedance amplifier and a 2.7–36 V supply range. Its sensitivity and the chosen LED spectra still need checking against the datasheet and board layout. Running a breakout at 5 V does not make its analog output automatically safe for a 3.3 V ESP32 ADC. The [BPW34 datasheet](https://www.vishay.com/docs/81521/bpw34.pdf) covers approximately 430–1100 nm, so it can receive 850/940 nm but not 1450 nm.

## Paper backing and limits

[Zhang, Yi, Lei and Li, “Face Liveness Detection by Learning Multispectral Reflectance Distributions”](https://nlpr.ia.ac.cn/2011papers/gjhy/gh65.pdf) motivates comparing spectral reflectance rather than using proximity alone. It studies a different optical setup and selected wavebands; it does not validate this cheaper 850/940 nm implementation. Replacing an imaging setup or a longer-wavelength channel with two nearby NIR LEDs and one photodiode discards evidence. [Monocular Facial Presentation–Attack–Detection: Classifying Near-Infrared Reflectance Patterns (2023)](https://doi.org/10.3390/app13031987) studies spatial NIR patterns; a single intensity receiver cannot reproduce spatial vessel/skin patterns.

The hypothesis to test is that synchronized, ambient-subtracted dual-band readings add discrimination against the actual paper, screens and masks used at this kiosk. Silicone, makeup, skin variation, angle, distance and ambient IR may cause overlap. Skin-like reflectance is not proof that a person is alive. There is no implemented or measured IR accuracy claim in this repository.

## Measurement and integration

1. Randomize the LED order; collect OFF → 850 → OFF → 940 → OFF samples and repeat. Use nearby OFF measurements to estimate ambient light for each channel. Reject saturation, weak signals, unstable position and insufficient samples.
2. Calibrate against a reference target separately for each wavelength. Subtract ambient, normalize by calibrated channel gain, then compute ratios with a denominator floor. A ratio is not inherently distance- or angle-independent.
3. Begin at a fixed 10–15 cm target distance for a bench experiment. Only test 20–50 cm after sufficient signal-to-noise is demonstrated. This sensor may become the range bottleneck even when RGB recognition works farther away.
4. Collect consented skin readings plus printed photos, phone stills, video replay and several mask materials across people, lighting, angles and distances. Use participant-disjoint splits, repeat sessions, and hold out at least one spoof material. Compare RGB baseline, IR baseline and fusion. Report attack acceptance, genuine rejection and median/p95 latency by condition, not a single overall accuracy number.
5. Connect ESP32 over USB serial to a small local service. Bind each measurement burst to a fresh server-issued nonce and the current camera session. Record sensor ID, measurement age and quality; align the sensor's sampled patch with the webcam face region. A nonce alone cannot secure an untrusted board or stop a nearby skin target being substituted for the mask.
6. Initially show IR only as experimental evidence in an operator/developer view. Missing, stale or low-quality readings lead to attended verification. Keep all automatic gate decisions on the trusted server path until fusion is calibrated and the acquisition chain is secured.

Do not add a browser-controlled relay that opens whenever the page displays Allow. A future gate controller should verify a short-lived, one-use server authorization tied to that gate and reject offline/replayed commands. Physical wiring, optical safety assessment and firmware remain separate work; no hardware is connected or simulated as trusted evidence by this update.

## Implemented prototype: ESP8266 + HW-201 + KY-016 (14 November 2026)

This is the low-cost kit actually on hand. It does **not** implement the dual-wavelength experiment above. The HW-201 is used as a **physical-presence check** (something real is in front of the kiosk), which counters injected or replayed camera video with nobody at the kiosk. Its optional analog value is logged as single-wavelength (~940 nm) reflectance for evaluation only.

| Wire | NodeMCU (ESP8266) | ESP32 DevKit |
| --- | --- | --- |
| HW-201 VCC / GND / OUT | 3V3 / GND / D5 | 3V3 / GND / GPIO27 |
| KY-016 R / G / B (220 Ω each if the module has none) | D6 / D7 / D2 | GPIO25 / GPIO26 / GPIO33 |
| KY-016 "–" | GND | GND |
| Optional HW-201 analog tap (LM393 input that varies with distance) | A0 | GPIO34 |

- Firmware: `hardware/trinetra_sensor/trinetra_sensor.ino` (115200 baud, JSON lines at ~20 Hz, LED commands `ALLOW|STEPUP|DENY|OFFLINE|SCAN|IDLE`, `N <nonce>`).
- Flash: `arduino-cli compile --fqbn esp8266:esp8266:nodemcuv2 hardware/trinetra_sensor` then `arduino-cli upload -p COMx --fqbn esp8266:esp8266:nodemcuv2 hardware/trinetra_sensor`. Close any Serial Monitor first.
- Kiosk: `ui/sensor.mjs` uses Web Serial (Chrome/Edge). Click **Connect** on the IR presence strip once; afterwards it reconnects automatically. Presence held for 400 ms starts a scan when the camera is ready.
- Backend (`policy.ir_evidence`): readings must be fresh (≤1.5 s old, ≥3 samples, matching the scan nonce). Presence ratio ρ ≥ 0.5 → `present`; ρ < 0.5 → **Deny** and liveness blocked for 10 minutes. Missing sensor → unchanged behaviour, unless `TRINETRA_REQUIRE_IR=1`, in which case the kiosk steps up and cloud liveness is refused until a fresh `present` scan. IR evidence never produces Allow.
- Limits: the browser relays sensor data, so this is not a trusted hardware attestation; a held-up phone or photo also reflects IR and will read `present`. Reflectance separation of skin vs silicone/3D masks is unmeasured.
