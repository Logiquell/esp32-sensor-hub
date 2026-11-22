# Hardware

Breadboard prototype. Items marked ⚠️ **confirm** were assumed or not recorded during the build
and should be checked against the physical hardware.

## 1. Components

| Ref | Part | Function | Interface | Supply | Notes |
|---|---|---|---|---|---|
| U1 | ESP32-WROOM-32 dev board | MCU | USB (CP210x), COM3 | 5 V USB → on-board 3.3 V regulator | ESP32-D0WD-V3 rev 3.1, 40 MHz crystal, 4 MB flash (read by esptool). ⚠️ **confirm** board vendor/variant (pin count) and USB-UART part (Windows reports "CP210x") |
| U2 | HC-SR04 | Ultrasonic distance, 2–400 cm | GPIO (Trig/Echo) | 5 V | Echo output is 5 V logic |
| M1 | Hobby micro servo | Sweeps U2 through 0–180° | PWM 50 Hz | 5 V | ⚠️ **confirm** model (firmware pulse limits assume SG90: 0.5–2.4 ms) |
| U3 | GM009605 v4 OLED | 0.96" 128×64 SSD1306, two-colour | I2C `0x3C` | 3.3 V | Rows 0–15 yellow, rows 16–63 blue (fixed in the panel) |
| U4 | DFRobot SEN0032 | ADXL345 3-axis accelerometer | I2C `0x53` | 3.3 V | `DEVID` = `0xE5` verified |
| U5 | AHT20 module | Temperature and relative humidity | I2C `0x38` | 3.3 V | No BMP280 present (no device at `0x77`) |
| PS1 | HW-131 breadboard power module | 5 V and 3.3 V rails | — | ⚠️ **confirm** input source (USB or barrel-jack adapter, voltage) | Each side has its own 5 V / 3.3 V jumper |
| SW1 | Tactile push button | MODE select | GPIO4 → GND | — | Internal pull-up |
| SW2 | On-board BOOT button | Zero level (TILT) / reset peak (ACCEL) | GPIO0 | — | Strapping pin; see notes |
| R1 | 1 kΩ | Echo divider, top | — | — | |
| R2 | 2.2 kΩ | Echo divider, bottom | — | — | 2 kΩ was not available |

## 2. Pin assignment

| GPIO | Board label | Signal | Direction | Configuration | Notes |
|---|---|---|---|---|---|
| 0 | BOOT | SW2 | In | Pull-up | Strapping pin: holding BOOT during reset enters the ROM bootloader |
| 4 | D4 | SW1 (MODE) | In | Pull-up, active low | |
| 5 | D5 | HC-SR04 Trig | Out | Push-pull | 3.3 V drive accepted by the HC-SR04 |
| 13 | D13 | Servo signal | Out | PWM 50 Hz, 0.5–2.4 ms | Released (`deinit`) outside RADAR mode |
| 19 | D19 | HC-SR04 Echo via R1/R2 | In | No pull | Pulse width measured with `time_pulse_us` |
| 21 | D21 | I2C SDA | I/O | I2C0, 400 kHz | Shared by U3, U4, U5 |
| 22 | D22 | I2C SCL | Out | I2C0 | Shared by U3, U4, U5 |
| 18 | D18 | — | — | **Not used** | Read abnormally in pull-up/pull-down tests after a wiring fault; treated as suspect |

Unused pins available for extensions include GPIO23, 25, 26, 27, 32, 33 and input-only
GPIO34–36, 39. GPIO2, 12 and 15 are strapping pins and are best avoided for inputs that can
be held at reset.

## 3. Power

```
 HW-131 input ──► HW-131 ── 5 V side   ──► HC-SR04 VCC, servo +
                         ── 3.3 V side ──► OLED, ADXL345 (VCC + CS), AHT20
                         ── GND ─────────► common ground ◄── ESP32 GND
 PC USB ───────► ESP32 dev board (logic supply and serial link)
```

- **Common ground.** The HW-131 ground must be tied to the ESP32 ground. Missing ground
  connections caused several faults during the build (see `development.md`).
- **Nothing is fed into the ESP32 3V3 pin.** The ESP32 is powered from USB only.
- **I2C devices are on 3.3 V.** Module pull-ups then hold SDA/SCL at 3.3 V. At 5 V they
  could put 5 V on GPIO21/22.
- **HW-131 5 V is not connected to ESP32 VIN while USB is connected.** Whether the dev board
  isolates VIN from USB 5 V with a diode has not been checked.

Estimated current (typical datasheet and module values, **not measured**):

| Load | Estimate |
|---|---|
| ESP32, Wi-Fi off | 50–80 mA |
| OLED + ADXL345 + AHT20 | ≈ 30 mA |
| HC-SR04 | ≈ 15 mA |
| Micro servo while moving | 100–500 mA peaks |

Not implemented or tested: battery operation, and bulk decoupling on the servo rail
(470–1000 µF suggested if the ESP32 resets when the servo moves).

## 4. Interfaces

### 4.1 HC-SR04 and Echo level shifting

```
HC-SR04 Echo ──[ R1 1k ]──┬── GPIO19
                          │
                      [ R2 2.2k ]
                          │
                         GND
```

V(GPIO19) = 5 V × 2.2 / (1 + 2.2) ≈ **3.44 V**, slightly above the 3.3 V I/O supply.
It has worked in practice, but the margin is small. ⚠️ **Confirm** against the
absolute-maximum input rating in the ESP32 datasheet. A 1 kΩ / 2 kΩ pair (3.33 V) or a
dedicated level shifter would give more margin.

Breadboard layout used:

| Row | Contents |
|---|---|
| A | Echo wire, R1 |
| B | R1, R2, wire to GPIO19 |
| C | R2, GND |

- Swapping R1 and R2 gives ≈ 1.6 V at the pin, which reads as logic low: no echoes are seen.
- Keep the Trig wire out of rows A–C.
- Distance = pulse width / 58 µs per cm. This assumes c ≈ 343 m/s, about 20 °C, with no
  temperature compensation. The echo timeout is 25 ms, ≈ 4.3 m.

### 4.2 Servo

| Servo wire | Connection |
|---|---|
| Brown / black | GND |
| Red | HW-131 5 V |
| Orange / yellow | GPIO13 |

Duty is set with `PWM.duty_ns()`: 0.5 ms = 0°, 2.4 ms = 180°, linear in between.
The firmware steps 2° and waits 15 ms before each reading.

### 4.3 I2C bus

| Device | Address | Extra pins |
|---|---|---|
| SSD1306 OLED | `0x3C` | — |
| ADXL345 | `0x53` | **CS → 3.3 V** (selects I2C mode), **SDO → GND** (selects 0x53), INT1/INT2 not connected. ⚠️ **confirm** CS/SDO wiring as built |
| AHT20 | `0x38` | — |

- No external pull-ups. The bus works with the pull-ups already on the modules: the scan
  finds all three devices at 400 kHz.
- Check the OLED pin order on the module (GND/VCC order differs between batches).

### 4.4 Buttons

SW1 connects GPIO4 to GND. The legs of a 4-pin tactile switch are joined in two internal
pairs, so use **diagonally opposite** legs, with the switch across the breadboard's centre gap.

## 5. Wiring summary

| From | To |
|---|---|
| HW-131 5 V | HC-SR04 VCC, servo + |
| HW-131 3.3 V | OLED VCC, ADXL345 VCC and CS, AHT20 VCC |
| HW-131 GND | ESP32 GND, all module GNDs, ADXL345 SDO, R2, SW1 |
| ESP32 GPIO5 | HC-SR04 Trig |
| HC-SR04 Echo | R1 → GPIO19 |
| ESP32 GPIO13 | Servo signal |
| ESP32 GPIO21 / GPIO22 | SDA / SCL of OLED, ADXL345, AHT20 |
| ESP32 GPIO4 | SW1 |

A schematic has not been drawn yet. This table and the pin assignment above are the
reference for the breadboard wiring.

## 6. Troubleshooting reference

| Symptom | Likely cause | Check |
|---|---|---|
| esptool: "No serial data received" | Board not in bootloader, or faulty | Hold BOOT, tap EN; try another board |
| Repeated panic/reboot on the console | Over-voltage on a 3.3 V pin, or a short | Disconnect power; check what reaches 3V3 and the GPIOs |
| HC-SR04: every reading times out | No 5 V at the sensor, Trig/Echo swapped, divider not on GPIO19 | Rail jumper; pin order; `pin_pull_test.py` |
| Echo stuck high | Missing ground at the sensor or at R2 | `echo_diag.py`; ground continuity |
| Readings below 2 cm | Trigger crosstalk or an unpowered sensor | Wire placement; 5 V at the sensor |
| I2C device missing from scan | Wrong pins, no common ground, ADXL345 CS low | `i2c_scan.py` |
| MODE button never detected | Not connecting GPIO4 to GND | `button_test.py`; diagonal legs |
| Temperature reads high | Self-heating from nearby electronics | Move the AHT20 away from the ESP32 |
