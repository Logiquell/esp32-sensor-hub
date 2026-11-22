# Development Log

Development notes, test evidence, decisions and known limitations.

**About the evidence.** Results below were taken from the serial console during development
sessions (15–16 November 2026). The raw logs were not saved to the repository; the values
are quoted as they were printed. Statements based on visual observation are marked
*(visual)*.

## 1. Timeline

| Stage | Work | Outcome |
|---|---|---|
| 1. MCU bring-up | Detected the USB-UART (CP210x, COM3), installed esptool, tried to connect | **Board 1 unresponsive**, see §3.1 |
| 2. Second board | `esptool flash-id` | ESP32-D0WD-V3 rev 3.1, 4 MB flash, MAC read. Connected without manual BOOT |
| 3. Firmware | Erased flash, wrote MicroPython v1.29.0 at `0x1000` | "Hash of data verified." Ran code from the REPL: 160 MHz, 4 194 304 B flash, ≈ 162 kB free heap |
| 4. GPIO | Toggled GPIO2 (on-board LED) | LED blinked *(visual)* |
| 5. HC-SR04 | Trig GPIO5, Echo GPIO18 via divider | Several faults, see §3.2–3.5. Echo moved to GPIO19; sensor replaced |
| 6. Radar | Servo on GPIO13, sweep firmware, PC viewer `pc/radar.py` | Sweep data streamed; viewer working *(visual)* |
| 7. OLED | I2C scan → `0x3C`, own SSD1306 driver, mini radar view | Working *(visual)* |
| 8. ADXL345 | I2C `0x53`, `DEVID 0xE5`, tilt/bubble-level app | Axis mapping set through tests (§3.8) |
| 9. AHT20 | I2C `0x38`, non-blocking driver, readings added to the tilt screen | Status `0x18` (calibrated) |
| 10. Hub | `hub.py`: four modes, MODE button on GPIO4, mode stored in flash | Mode switching verified (§2) |
| 11. Rewire | Breadboard rebuilt; HC-SR04 re-verified | Two wiring faults found and fixed (§3.6) |

## 2. Verification results

| Test | Method | Result |
|---|---|---|
| Chip identity | `esptool flash-id` | ESP32-D0WD-V3 rev v3.1, 40 MHz crystal, flash 4 MB (manufacturer `0x5e`, device `0x4016`) |
| Firmware integrity | `esptool write-flash` verification | Hash verified (1 790 544 B image) |
| I2C bus | `diagnostics/i2c_scan.py` | `['0x38', '0x3c', '0x53']` |
| ADXL345 identity | `diagnostics/adxl345_test.py` | `DEVID 0xe5` |
| ADXL345 at rest | 10 samples, ±2 g | x +0.00…+0.01 g, y −0.28…−0.27 g, z +0.87…+0.88 g. Noise about ±0.01 g. Magnitude ≈ 0.91 g, so uncalibrated |
| AHT20 | `diagnostics/aht20_test.py`, 5 samples at 1 s | 26.45–26.54 °C, 24.8–25.0 % RH (no reference instrument) |
| HC-SR04, replacement sensor | 20 cycles, target not controlled | 20/20 echoes, 23.4–56.7 cm |
| HC-SR04 after rewiring | `diagnostics/sonar_test.py`, stationary target (distance not measured independently) | 20/20 echoes: 16.1 cm (18 readings), 17.0 and 17.1 cm (1 each) |
| Mode button | `pc/watch.py`, 30 s capture | 11 presses → 11 single-step transitions RADAR→TILT→CLIMATE→… (before ACCEL was added); no double or missed switches |
| ACCEL mode | `pc/watch.py`, 20 s capture | 265 `x,y,z` records (≈ 13 Hz); z ≈ +0.9–1.0 g at rest |
| RADAR loop rate | `pc/watch.py`, 30 s capture | 322 records (≈ 10.7 Hz) |
| Displays | Visual | RADAR, TILT, ACCEL and CLIMATE screens confirmed; PC radar viewer confirmed |

**Not yet tested:** distance accuracy against a tape measure, temperature and humidity against
a reference, ADXL345 calibration, current consumption, battery operation, long-duration
stability.

## 3. Faults and how they were isolated

### 3.1 Unresponsive first ESP32 board
- The CP210x enumerated as COM3, so the USB side was working.
- `esptool flash-id` failed with "No serial data received". This held with auto-reset, with
  `--before no-reset` at 115200, and with the BOOT/EN sequence done by hand.
- A passive listen on COM3 with DTR/RTS held inactive, across 10 s and 30 s windows with EN
  presses, received 0 bytes. A working ESP32 prints ROM boot messages at reset.
- Power LED on. **Conclusion:** the ESP32 itself was not running, or its UART path was broken.
  A second board of the same type worked immediately. Board 1 was set aside; the root cause
  was not determined.

### 3.2 Echo level shifting
The HC-SR04 Echo output is 5 V; ESP32 inputs are 3.3 V. A 1 kΩ / 2.2 kΩ divider was used,
giving ≈ 3.44 V (2 kΩ was not available). See `hardware.md` §4.1 for the margin note.

### 3.3 No echo at 3.3 V supply
All readings timed out with the sensor on the 3.3 V rail; the standard HC-SR04 needs 5 V.
The supply was moved to 5 V.

### 3.4 Panic/reboot loop after the supply change
After moving the sensor to 5 V, the console showed repeated
"Panic handler entered multiple times… Rebooting". Power was removed and the wiring fault
was found and corrected ⚠️ *the specific fault was not recorded*. Afterwards:

- The original HC-SR04 never produced an echo pulse.
- GPIO18 behaved inconsistently in pull-up / pull-down tests (it read high after switching
  from pull-up back to pull-down).

Echo was moved to **GPIO19**, which passed the same pull test, and the sensor was replaced.
The replacement worked first time. ⚠️ *Damage to the sensor and GPIO18 is inferred from
behaviour, not proven.*

### 3.5 Echo stuck high / divider open
A diagnostic sequence (`echo_diag.py`, `pin_pull_test.py`) was used to classify the Echo
line:

| Observation | Interpretation |
|---|---|
| High even with the internal pull-down | Actively driven high: the Echo output was latched, or the divider's ground was missing |
| Low with pull-down but high with pull-up | Floating: nothing connected to the pin |
| Low under both pulls | Divider connected (2.2 kΩ to GND overrides the weak internal pull-up) |

Faults found this way: a **missing ground connection** (the line was driven high) and the
**divider not connected to GPIO19** (the line floated). Both were fixed by rewiring.

### 3.6 Faults after rebuilding the breadboard
- Readings of 0.4–0.9 cm, below the 2 cm sensor minimum. These were ~25–50 µs pulses,
  consistent with trigger crosstalk or an unpowered sensor. Fixed by rechecking the wiring
  ⚠️ *exact cause not recorded*.
- Echo held high under pull-down again → a missing ground, as in §3.5. After the fix:
  16.1 cm, 20/20.

### 3.7 MODE button
The first `button_test.py` run showed GPIO4 idle high with no presses detected. The wiring
was rechecked, and the second run detected presses. The tactile-switch leg pairing
(use diagonal legs) was documented.

### 3.8 Axis mapping and display layout
- The OLED's top 16 rows are always yellow, so layouts were reworked: numbers in the yellow
  band, graphics in the blue area.
- Pitch/roll labels and bubble directions were corrected over three iterations of physical
  tilt tests. `PITCH_DIR` / `ROLL_DIR` constants were added, so mounting changes need no
  maths changes.

### 3.9 Tooling issue: UTF-8 BOM
A `main.py` generated with PowerShell 5 (`Set-Content -Encoding utf8`) started with a
UTF-8 BOM. MicroPython failed with `NameError: name '﻿' isn't defined`. Files are now
written without a BOM.

## 4. Technical decisions

See `architecture.md` §5 for the firmware trade-offs. Hardware-side decisions:

| Decision | Reason |
|---|---|
| I2C devices on 3.3 V, sensor and servo on 5 V | Keeps I2C pull-ups at the ESP32's logic level; the HC-SR04 and servo need 5 V |
| Resistive divider rather than a level-shifter IC | Parts at hand; one unidirectional signal |
| No external I2C pull-ups | Module pull-ups proved sufficient for three devices on short wires |
| ±4 g accelerometer range in the hub | Avoids clipping during shake tests; full-resolution mode keeps 3.9 mg/LSB |
| GPIO18 retired | Suspect after the over-voltage event; GPIO19 used instead |

## 5. Known limitations

- Breadboard construction; no schematic, PCB or enclosure.
- Distance, temperature and humidity accuracy not validated against references.
- ADXL345 uncalibrated; tilt valid only when static (no gyro fusion).
- No speed-of-sound temperature compensation; one ultrasonic sample per angle.
- Echo divider output ≈ 3.44 V, above the 3.3 V I/O supply.
- No automated tests; verification is manual, with the diagnostic scripts.
- Raw test logs are not stored in the repository.

## 6. Items requiring confirmation

| Item | Current assumption |
|---|---|
| Servo model | SG90 (pulse limits 0.5–2.4 ms) |
| ESP32 dev board vendor / variant, USB-UART part | WROOM-32 dev board, "CP210x" per Windows |
| HW-131 input supply | Not recorded |
| ADXL345 CS and SDO wiring as built | CS → 3.3 V, SDO → GND (address 0x53 confirms SDO low) |
| Wiring fault behind the panic loop (§3.4) | Not recorded |
| Cause of the sub-2 cm readings (§3.6) | Not recorded |

## 7. AI-assisted development

Claude Code was used as a development assistant: it drafted code, diagnostic scripts and
documentation, and suggested debugging steps. Hardware assembly, wiring, physical tests and
observations were done by the author. Outputs quoted here come from runs on the physical
hardware.
