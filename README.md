# ESP32 Multi-Sensor Hub

An ESP32-WROOM-32 breadboard prototype in MicroPython. It combines four instruments on one
two-colour 128×64 OLED: a servo-swept ultrasonic **radar**, an accelerometer **tilt** level,
a raw **acceleration** readout and a **temperature/humidity** display. One push button cycles
between them. Every mode also streams its data as CSV over USB serial, and a Python
tool on the PC draws the radar sweep live.

The project covers sensor bring-up, mixed 5 V / 3.3 V interfacing, I2C bus sharing, PWM actuator
control and non-blocking sampling. It also records a hardware fault-finding process: a dead
MCU board, a damaged sensor, a suspect GPIO and several wiring faults, each isolated with
small diagnostic scripts.

---

## 1. Project Overview

| | |
|---|---|
| MCU | ESP32-D0WD-V3 (rev 3.1) on a WROOM-32 dev board, 4 MB flash |
| Firmware | MicroPython v1.29.0, application in Python |
| Sensors | HC-SR04 ultrasonic, ADXL345 accelerometer, AHT20 temperature/humidity |
| Actuator | Hobby servo (PWM, 50 Hz) sweeping the ultrasonic sensor 0–180° |
| Display | SSD1306 128×64 OLED (I2C), fixed yellow top band / blue lower area |
| Host link | USB-UART (CP210x), 115200 baud, CSV lines per mode |
| Power | USB for the ESP32; HW-131 breadboard module for 5 V and 3.3 V rails |

Modes, selected with the MODE button and remembered across resets:

| Mode | OLED | Serial output |
|---|---|---|
| RADAR | Half-circle sweep with detected objects, angle, distance | `angle,distance_cm` |
| TILT | Bubble level, pitch/roll; temperature and humidity at the sides | `pitch,roll,temp_c,humidity` |
| ACCEL | X/Y/Z in g with bar graphs, total and peak g | `x_g,y_g,z_g` |
| CLIMATE | Large temperature and humidity, min/max since power-up | `temp_c,humidity` |

---

## 2. Key Features

Implemented and exercised on the hardware:

- **Ultrasonic radar.** The servo steps 2° at a time, takes one HC-SR04 reading per step
  and draws the result on the OLED. Distance comes from the echo pulse width
  (`machine.time_pulse_us`, 25 ms timeout ≈ 4.3 m).
- **Voltage-divider level shifting** of the 5 V HC-SR04 Echo signal to the 3.3 V ESP32 input
  (1 kΩ / 2.2 kΩ, ≈ 3.4 V).
- **Shared I2C bus** at 400 kHz with three devices (OLED `0x3C`, ADXL345 `0x53`, AHT20 `0x38`),
  using minimal register-level drivers written for this project.
- **Tilt measurement.** Pitch and roll come from the gravity vector, with exponential smoothing,
  a zero offset set by button, and configurable axis directions.
- **Accelerometer readout** at ±4 g full-resolution, with magnitude and peak-hold.
- **Non-blocking AHT20 sampling.** A measurement is started and its result collected about
  80 ms later, so the display loop keeps running during the conversion.
- **Mode manager.** Every mode has `enter()`, `step()` and `exit()` functions. The button
  is debounced and switches on the edge. The servo PWM is released when leaving RADAR, and
  the selected mode is stored in flash.
- **Fault tolerance.** The firmware keeps running if the AHT20 or the OLED is missing
  at start-up, and a failed I2C transfer only skips that frame.
- **PC tools:** a live radar viewer (Tkinter), a file uploader over the MicroPython raw REPL,
  a one-shot script runner and a serial monitor.
- **Diagnostic scripts** for each sensor, the button and the I2C bus
  ([`diagnostics/`](diagnostics/README.md)).

---

## 3. Hardware Components

| Component | Part | Interface | Supply |
|---|---|---|---|
| MCU board | ESP32-WROOM-32 dev board, CP210x USB-UART | USB | 5 V USB |
| Ultrasonic sensor | HC-SR04 | GPIO5 Trig, GPIO19 Echo (via divider) | 5 V |
| Servo | Hobby micro servo ⚠️ *model to be confirmed (SG90 assumed)* | GPIO13 PWM | 5 V |
| OLED | GM009605 v4, 0.96" SSD1306 128×64, yellow/blue | I2C `0x3C` | 3.3 V |
| Accelerometer | DFRobot SEN0032 (Analog Devices ADXL345) | I2C `0x53` | 3.3 V |
| Temperature/humidity | AHT20 module | I2C `0x38` | 3.3 V |
| Power module | HW-131 breadboard supply (5 V and 3.3 V rails) | — | ⚠️ *input source to be confirmed* |
| Input | Tactile push button (MODE) and on-board BOOT button | GPIO4, GPIO0 | — |
| Passives | 1 kΩ, 2.2 kΩ (Echo divider) | — | — |

Pin assignments, wiring and power notes: [`docs/hardware.md`](docs/hardware.md).

---

## 4. Software and Development Tools

| Tool | Version | Use |
|---|---|---|
| MicroPython (`ESP32_GENERIC`) | v1.29.0 | Firmware runtime |
| esptool | 5.6.0 | Chip identification, flash erase/write |
| Python (PC) | 3.13 | Host tools |
| pyserial | 3.5 | Serial communication from the PC |
| Tkinter | Python standard library | Radar viewer GUI |
| Claude Code | — | Development assistant (see [AI-assisted development](#ai-assisted-development)) |

No external MicroPython libraries are used. The SSD1306, ADXL345 and AHT20 drivers are small
modules in [`esp32/`](esp32/), written against the device registers and command sets.

---

## 5. System Architecture

```
                 ┌──────────────────────── ESP32 (MicroPython) ────────────────────────┐
 MODE btn ──GPIO4┤                                                                      │
 BOOT btn ──GPIO0┤  main.py ─► hub.py   main loop: poll button → climate.poll() → step() │
                 │              │                                                       │
 HC-SR04 ◄─GPIO5─┤   Radar ─────┤  Trig/Echo timing, servo PWM (GPIO13)                 │
         ─GPIO19►┤   Tilt  ─────┤  adxl345.py ─┐                                        │
 Servo  ◄─GPIO13─┤   Accel ─────┤              ├─ I2C0 (GPIO21 SDA / GPIO22 SCL) ───────┼─► OLED, ADXL345, AHT20
                 │   Climate ───┤  aht20.py ───┘          ssd1306.py (framebuffer)      │
                 │              └─ print() CSV ──► USB-UART ──────────────────────────────┼─► PC: watch.py / radar.py
                 └──────────────────────────────────────────────────────────────────────┘
```

- `main.py` only selects the application (`hub`, or the older standalone `radar` / `tilt`).
- `hub.py` creates the shared I2C bus, the OLED, the ADXL345 and a shared `Climate` sampler,
  then runs a single cooperative loop. Each mode's `step()` does one unit of work: one radar
  angle, or one display frame.
- Drivers are independent modules with no dependencies beyond `machine` and `framebuf`.

Details: [`docs/architecture.md`](docs/architecture.md).

---

## 6. Technical Challenges and Solutions

| Problem | How it was diagnosed | Resolution |
|---|---|---|
| First ESP32 board never responded to esptool | USB bridge enumerated (COM3), but esptool got no bytes, with and without the BOOT/EN sequence. A passive serial listen across an EN reset also got no bytes | Board judged faulty; a second board of the same type connected first time |
| 5 V Echo output vs. 3.3 V GPIO | Datasheet levels | 1 kΩ / 2.2 kΩ divider (2 kΩ not available) → ≈ 3.4 V |
| Panic/reboot loop after rewiring the sensor supply from 3.3 V to 5 V | Serial console showed repeated panic-handler resets | Wiring fault corrected. Afterwards the first HC-SR04 gave no echo and GPIO18 read abnormally, so Echo was moved to GPIO19 and the sensor replaced ⚠️ *cause of damage inferred, not proven* |
| Echo line stuck high | `echo_diag.py` / `pin_pull_test.py`: the line stayed high even with the internal pull-down, so it was actively driven, not floating | Missing ground connection found and restored |
| Divider not reaching the GPIO | Pull-up test: GPIO19 followed the internal pull-up, so the 2.2 kΩ to GND was not connected | Breadboard wiring corrected; the pin then read low under pull-up |
| Implausible 0.4–0.9 cm readings (below the 2 cm sensor minimum) | Pulse widths ~25–50 µs, consistent with trigger crosstalk or an unpowered sensor | Wiring rechecked; normal readings resumed ⚠️ *exact fault not recorded* |
| Mode button not detected | `button_test.py`: GPIO4 idle high and never pulled low during presses | Button wiring to GPIO4/GND rechecked; retest detected presses. Tactile-switch leg pairing (diagonal legs across the centre gap) documented |
| AHT20 needs ~80 ms per conversion | Would stall the 30–40 ms display loop | Split into `start()` / `result()` and polled from the main loop |
| Two-colour OLED (fixed yellow rows 0–15) | Visual check | Layouts keep text in the yellow band and graphics in rows 16–63 |
| Accelerometer axes vs. mounting orientation | Interactive tilt tests | Pitch/roll formulas assigned to the mounting, with `PITCH_DIR` / `ROLL_DIR` sign constants |
| `main.py` failed with `NameError` on the board | Traceback pointed to an invisible first character | PowerShell 5 `Set-Content -Encoding utf8` writes a UTF-8 BOM, which MicroPython does not accept; files are now written without a BOM |

More detail and the decisions behind them: [`docs/development.md`](docs/development.md).

---

## 7. Current Development Status

**Working on the hardware.** These were observed in serial output during development,
and the OLED screens were checked by eye. Raw logs are not stored in the repository.

- Chip identification via esptool: ESP32-D0WD-V3 rev 3.1, 40 MHz crystal, 4 MB flash.
  MicroPython image written and hash-verified.
- I2C scan finds `0x38`, `0x3C` and `0x53`. ADXL345 `DEVID` reads `0xE5`. AHT20 reports
  calibrated (status `0x18`).
- HC-SR04 returned 20 of 20 echoes against a stationary object: 18 × 16.1 cm, 1 × 17.0 cm,
  1 × 17.1 cm.
- Mode switching: 11 button presses in a 30 s capture gave 11 single-step transitions,
  with no double or missed switches.
- RADAR streams to the PC viewer, and every mode's OLED screen was confirmed visually.

**Not validated.**

- Distance accuracy against a reference measurement.
- Temperature and humidity accuracy against a reference instrument.
- Accelerometer calibration. At rest the magnitude read ≈ 0.91 g instead of 1.00 g, so
  offset and gain are uncalibrated.
- Long-duration operation, battery operation, and servo supply decoupling.

---

## 8. Planned Improvements

These are proposals; none of them is implemented yet.

- Temperature-compensated speed of sound for the radar, using the on-board AHT20
  (currently fixed at 58 µs/cm, ≈ 343 m/s).
- Median-of-N distance filtering, and a reading quality flag.
- ADXL345 offset/gain calibration, using the six-position method and its offset registers.
- AHT20 CRC check (the 7th byte is read but not verified).
- Distance and climate accuracy tests against reference instruments, with logged results.
- CSV logging tool on the PC, and a schematic (KiCad) to replace the breadboard notes.
- Battery supply with servo decoupling, then porting the display from breadboard to perfboard.

---

## 9. Building and Flashing

Requirements: Python 3, an ESP32-WROOM-32 board on a known COM port (examples use `COM3`).

```bash
pip install -r pc/requirements.txt
```

**1. Flash MicroPython.** Download `ESP32_GENERIC` v1.29.0 from
[micropython.org/download/ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/).
The image is not stored in this repository.

```bash
python -m esptool --port COM3 erase-flash
python -m esptool --port COM3 --baud 460800 write-flash 0x1000 ESP32_GENERIC-20260824-v1.29.0.bin
```

If esptool cannot connect, hold **BOOT**, tap **EN**, then retry.

**2. Upload the application.** Upload the drivers first and `main.py` last. Each upload
soft-resets the board, so `main.py` should only start once everything it imports is there.

```bash
cd pc
python upload.py ../esp32/ssd1306.py
python upload.py ../esp32/adxl345.py
python upload.py ../esp32/aht20.py
python upload.py ../esp32/hub.py
python upload.py ../esp32/main.py
```

**3. Run and monitor.**

```bash
python watch.py              # mode changes and sample data, without resetting the board
python radar.py --range 200  # live radar view (board in RADAR mode)
```

Only one program can hold the serial port at a time: close `radar.py` before running
`upload.py`, `watch.py` or `run_on_board.py`.

---

## Repository Structure

```
esp32/        Firmware copied to the board (application + drivers)
pc/           Host tools: uploader, script runner, serial monitor, radar viewer
diagnostics/  One-shot test scripts used for bring-up and fault-finding
docs/         Hardware, architecture and development notes
HARDWARE.md   Original wiring notes (superseded by docs/hardware.md)
```

## AI-assisted development

This project was developed with Claude Code as an assistant. It suggested and drafted much of
the code, the diagnostic scripts and the documentation. The hardware was assembled, wired and
debugged by me, and every result above comes from tests run on the physical hardware. I have
reviewed the code and documentation, and I am responsible for the design decisions in this
repository.
