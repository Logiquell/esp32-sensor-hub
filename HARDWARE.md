# ESP32 Sensor Hub — Hardware

> **Note:** the maintained version of this document is [`docs/hardware.md`](docs/hardware.md),
> which also marks unconfirmed details. This file is kept as the original build notes.

A multi-sensor board built on an ESP32-WROOM-32 dev board running MicroPython.
One MODE button cycles four screens on a two-colour OLED:
**RADAR → TILT → ACCEL → CLIMATE**.

---

## 1. Parts list

| Part | Model / marking | Function | Interface | Supply |
|---|---|---|---|---|
| Microcontroller | ESP32-WROOM-32 dev board (ESP32-D0WD-V3 rev 3.1, 4 MB flash, CP2102 USB-UART) | Runs everything | USB (COM3) | USB 5 V |
| Power module | HW-131 breadboard supply | 5 V and 3.3 V rails | — | Barrel jack 6.5–12 V or USB |
| Ultrasonic sensor | HC-SR04 | Distance 2–400 cm | GPIO (Trig/Echo) | **5 V** |
| Servo | SG90 (9 g hobby servo) | Sweeps the HC-SR04 0–180° | PWM 50 Hz | **5 V** |
| OLED display | GM009605 v4 — 0.96" 128×64 SSD1306, yellow/blue | Display | I2C `0x3C` | **3.3 V** |
| Accelerometer | DFRobot SEN0032 (ADXL345) | X/Y/Z acceleration, tilt | I2C `0x53` | **3.3 V** |
| Temp / humidity | AHT20 | Temperature, relative humidity | I2C `0x38` | **3.3 V** |
| Push button | 4-leg tactile switch | MODE select | GPIO (to GND) | — |
| Resistors | 1 kΩ + 2.2 kΩ | Echo voltage divider (5 V → 3.4 V) | — | — |

---

## 2. Power

```
              ┌──────────── HW-131 ────────────┐
 Battery / ──►│ 5V rail  (jumper = 5V)          │──► HC-SR04 VCC, Servo red
 adapter      │ 3.3V rail (jumper = 3.3V)       │──► OLED, ADXL345, AHT20 VCC, ADXL345 CS
              │ GND                             │──► common GND ◄── ESP32 GND
              └─────────────────────────────────┘
 PC USB ─────► ESP32 (powers the ESP32 only, + serial link)
```

**Rules**

- **One common ground.** HW-131 GND, ESP32 GND and every part's GND must be connected.
  A missing ground caused most of the faults during the build (Echo stuck high, no readings).
- **Never feed anything into the ESP32 3V3 pin.** It bypasses the regulator.
- **Don't connect HW-131 5V to ESP32 VIN while USB is plugged in** (risk of back-feeding the PC).
  For battery-only operation: unplug USB and feed HW-131 5V → ESP32 **VIN**.
- Each HW-131 side has its own jumper: one side **5V** (sensor + servo), the other **3.3V** (I2C devices).
- Servo current spikes up to ~500 mA. If the ESP32 resets when the servo moves,
  put a **470–1000 µF electrolytic** across the 5V rail near the servo (stripe = GND).

**Approximate current**

| Load | Current |
|---|---|
| ESP32 (Wi-Fi off) | 50–80 mA |
| OLED + ADXL345 + AHT20 | ~30 mA |
| HC-SR04 | ~15 mA |
| SG90 servo moving | 100–500 mA peaks |

---

## 3. Pin map

| ESP32 pin | Label | Connected to | Direction | Notes |
|---|---|---|---|---|
| GPIO0 | BOOT | On-board BOOT button | In (pull-up) | Zero level (TILT), reset peak (ACCEL) |
| GPIO4 | D4 | MODE button → GND | In (pull-up) | Cycles modes |
| GPIO5 | D5 | HC-SR04 Trig | Out | 3.3 V is enough to trigger |
| GPIO13 | D13 | Servo signal (orange) | PWM out | 50 Hz, 0.5–2.4 ms |
| GPIO19 | D19 | HC-SR04 Echo **via divider** | In | Never connect Echo directly |
| GPIO21 | D21 | I2C SDA (OLED, ADXL345, AHT20) | I2C | 400 kHz |
| GPIO22 | D22 | I2C SCL (OLED, ADXL345, AHT20) | I2C | |
| GPIO18 | D18 | — **do not use** | — | Behaved erratically after an earlier 5 V wiring fault |
| GND | GND | Common ground | — | |

Free for future use: GPIO2 (on-board blue LED), 15, 23, 25, 26, 27, 32, 33, and input-only 34, 35, 36 (VP), 39 (VN).

---

## 4. Wiring per part

### 4.1 HC-SR04 ultrasonic sensor

| HC-SR04 | Connects to |
|---|---|
| VCC | HW-131 **5V** |
| GND | Common GND |
| Trig | ESP32 **GPIO5** (direct) |
| Echo | **1 kΩ** → GPIO19 → **2.2 kΩ** → GND |

**Echo voltage divider** — the sensor outputs a 5 V pulse; ESP32 pins are 3.3 V.

```
HC-SR04 Echo ──[ 1k ]──┬── ESP32 GPIO19
                       │
                    [ 2.2k ]
                       │
                      GND
```

`V(GPIO19) = 5 V × 2.2k / (1k + 2.2k) ≈ 3.4 V`

Breadboard layout (three rows):

| Row | Contents |
|---|---|
| A | Echo wire + 1k leg |
| B | 1k other leg + 2.2k leg + wire to **GPIO19** |
| C | 2.2k other leg + **GND** |

- 1k on the **Echo** side, 2.2k on the **GND** side. Swapped → only ~1.6 V reaches the pin → no readings.
- Keep the Trig wire out of rows A–C (crosstalk gives fake ~0.5 cm readings).
- Alternative values: any pair with bottom ≈ 2× top (e.g. 10k / 20k).

### 4.2 SG90 servo

| Wire | Connects to |
|---|---|
| Brown | Common GND |
| Red | HW-131 **5V** (not ESP32 3V3) |
| Orange | ESP32 **GPIO13** |

The HC-SR04 is mounted on the servo horn, facing straight out.
If the servo buzzes at the end stops, adjust `PULSE_MIN_NS` / `PULSE_MAX_NS` in `hub.py`.

### 4.3 I2C bus (OLED + ADXL345 + AHT20)

All three share SDA (GPIO21) and SCL (GPIO22).

| Device | Address | VCC | Extra pins |
|---|---|---|---|
| OLED GM009605 v4 (SSD1306) | `0x3C` | 3.3V | — |
| ADXL345 (SEN0032) | `0x53` | 3.3V | **CS → 3.3V** (selects I2C), **SDO → GND** (address 0x53), INT1/INT2 unused |
| AHT20 | `0x38` | 3.3V | — |

- **No extra pull-up resistors** — the OLED module already has them; one set serves the whole bus.
- Never put resistors *in series* with SDA/SCL, and never capacitors on them.
- Add 4.7 kΩ pull-ups to **3.3V** only if the scan misses devices or wires are > 30 cm.
- Power I2C devices from **3.3V**: on 5V, module pull-ups would put 5 V on GPIO21/22.
- Check OLED pin order on the module (usually GND, VCC, SCL, SDA — some batches swap VCC/GND).

**OLED colour zones** (two-colour panel, fixed in hardware):

| Rows | Colour | Used for |
|---|---|---|
| 0–15 | Yellow | Titles and numbers |
| 16–63 | Blue | Graphics (radar, bubble, bars, big digits) |

### 4.4 MODE button

| Button leg | Connects to |
|---|---|
| One leg | ESP32 **GPIO4** |
| Diagonally opposite leg | **GND** |

- No resistor — internal pull-up is used. Pressed = low.
- Place the button **across the breadboard centre gap** and use **diagonal legs**:
  legs on the same side are internally connected in pairs, so the wrong pair reads "always pressed".

---

## 5. Full connection summary

```
                         ESP32-WROOM-32
                    ┌──────────────────────┐
   MODE btn ── GND  │ GPIO4                │
   HC-SR04 Trig ────│ GPIO5                │
   Servo signal ────│ GPIO13               │
   Echo divider ────│ GPIO19               │
   I2C SDA ─────────│ GPIO21               │
   I2C SCL ─────────│ GPIO22               │
   Common GND ──────│ GND                  │
                    │ GPIO18  (unused!)    │
   PC ══ USB ═══════│ USB (COM3)           │
                    └──────────────────────┘

   HW-131 5V   ──► HC-SR04 VCC, Servo red
   HW-131 3.3V ──► OLED VCC, ADXL345 VCC + CS, AHT20 VCC
   HW-131 GND  ──► everything's GND (incl. ESP32 GND, ADXL345 SDO)
```

---

## 6. Firmware on the board

| File | Purpose |
|---|---|
| `main.py` | Selects the startup app (`APP = 'hub'`) |
| `hub.py` | Four-mode app (RADAR / TILT / ACCEL / CLIMATE) |
| `radar.py`, `tilt.py` | Older standalone apps |
| `ssd1306.py`, `adxl345.py`, `aht20.py` | Drivers |
| `mode.txt` | Last selected mode (created automatically) |

MicroPython v1.29.0 (`ESP32_GENERIC`) flashed at `0x1000`.
Serial: COM3, 115200 baud. Upload with `pc/upload.py`, watch with `pc/watch.py`,
PC radar view with `pc/radar.py` (close it before uploading — both use COM3).

| Mode | Screen | Serial output |
|---|---|---|
| RADAR | Sweep + objects, angle, distance | `angle,distance_cm` |
| TILT | Bubble level, pitch/roll, temp/humidity | `pitch,roll,temp_c,humidity` |
| ACCEL | X/Y/Z bars, total and peak g | `x_g,y_g,z_g` |
| CLIMATE | Large temp + humidity, min/max | `temp_c,humidity` |

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `esptool`: "No serial data received" | Board faulty / not in bootloader | Hold BOOT, tap EN; try another board (first board was dead) |
| ESP32 panic/reboot loop | 5 V on a 3.3 V pin, or short | Unplug at once; check nothing 5 V reaches 3V3 or GPIOs |
| HC-SR04: all "timeout" | No 5 V at sensor, Trig/Echo swapped, divider not on GPIO19 | Check rail jumper, pin order, divider rows |
| HC-SR04: Echo stuck high | GND missing (sensor or divider bottom) | Restore common GND |
| HC-SR04: ~0.5 cm readings | Trig crosstalk into Echo rows | Separate Trig from divider rows |
| I2C scan empty / missing device | Wrong pins, no common GND, no pull-ups | Check SDA=21/SCL=22, GND; add 4.7k to 3.3V |
| ADXL345 not found | CS not tied high (stuck in SPI mode) | CS → 3.3V |
| Button always "pressed" | Wired to an internally connected leg pair | Rotate 90° or use diagonal legs |
| Button never pressed | Not between GPIO4 and GND | Check rows, button across centre gap |
| ESP32 resets when servo moves | Servo current spikes | 470–1000 µF on the 5V rail |
| Temperature 1–2 °C high | Heat from ESP32 | Move AHT20 a few cm away |

---

## 8. Lessons from the build

- The **first ESP32 board was dead** (no serial output at all); the second worked first time.
- A wiring fault put 5 V where it didn't belong: it **killed the first HC-SR04** and left
  **GPIO18 unreliable** — Echo was moved to GPIO19.
- Almost every later fault was a **missing common ground**.
