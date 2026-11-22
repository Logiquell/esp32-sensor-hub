# Firmware Architecture

## 1. Files

### Board side (`esp32/`, copied to the board's filesystem root)

| File | Role |
|---|---|
| `main.py` | Runs at boot. Imports the module named in `APP` (`'hub'`; `'radar'` and `'tilt'` are the older single-purpose apps) |
| `hub.py` | Four-mode application: mode manager, the four mode classes, shared sensors |
| `ssd1306.py` | SSD1306 I2C driver: init sequence, framebuffer (`framebuf.MONO_VLSB`), `show()` as one bulk write |
| `adxl345.py` | ADXL345 driver: `DEVID` check, full-resolution mode, range 2/4/8/16 g, 100 Hz data rate, `read_g()` |
| `aht20.py` | AHT20 driver: calibration check, blocking `read()` and non-blocking `start()` / `result()` |
| `radar.py` | Standalone radar app (servo + HC-SR04 + OLED + serial) |
| `tilt.py` | Standalone bubble-level app (ADXL345 + AHT20 + OLED) |
| `mode.txt` | Created at run time; index of the last selected mode. Not part of the repository |

### PC side (`pc/`)

| File | Role |
|---|---|
| `upload.py` | Writes a file to the board through the MicroPython raw REPL in 256-byte chunks, checks the size with `os.stat`, then soft-resets |
| `run_on_board.py` | Runs a script once from RAM through the raw REPL and prints stdout/stderr |
| `watch.py` | Opens the port without toggling DTR/RTS (no reset) and summarises mode changes and data lines. `--restart` soft-resets first |
| `radar.py` | Tkinter radar display. A reader thread parses `angle,distance` lines into a queue, and the GUI redraws at ~30 fps with fading hits |

## 2. Runtime structure (`hub.py`)

```
boot ─► main.py ─► import hub
                     │
                     ├─ I2C0 @ 400 kHz (GPIO21/22)
                     ├─ SSD1306 (0x3C)
                     ├─ Climate  ── AHT20 (0x38), shared, optional
                     ├─ ADXL345 (0x53, ±4 g), shared
                     └─ modes = [Radar, Tilt, Accel, ClimateView]
                                       │
   main loop ◄─────────────────────────┘
     ├─ climate.poll()            non-blocking AHT20 state machine
     ├─ MODE button edge?         debounce 30 ms → exit() old, save index, splash, enter() new
     └─ mode.step()               one unit of work; OSError (I2C) caught → retry next loop
```

Each mode class implements the same interface:

| Method | Radar | Tilt | Accel | ClimateView |
|---|---|---|---|---|
| `enter()` | Create PWM, home servo to 0°, clear hits | Seed the smoothed angles | — | — |
| `step()` | Move 2°, settle 15 ms, measure, print, redraw | Read accel, smooth, zero check, print, redraw, 30 ms | Read accel, magnitude/peak, print, redraw, 40 ms | Redraw, print once per second, 100 ms |
| `exit()` | `PWM.deinit()` (servo released) | — | — | — |

Scheduling is cooperative and single-threaded: no interrupts, timers or threads are used on
the board. Loop timing comes from each `step()`'s sleep, its I/O, and the 25 ms worst-case echo
timeout in RADAR.

## 3. Data flow and processing

### RADAR
1. Servo duty = 0.5 ms + (1.9 ms × angle / 180).
2. 10 µs Trig pulse. `time_pulse_us(echo, 1, 25000)` measures the Echo high time.
3. distance = t / 58 (cm). Values outside 2–400 cm, or timeouts, become `-1`.
4. `hits[angle] = distance`, or removed if there is no echo. These are drawn as 3×3 dots,
   scaled to a 200 cm outer ring.
5. Serial: `angle,distance` (one decimal place).

### TILT
1. `read_g()` returns raw 16-bit counts × 3.9 mg/LSB (full-resolution mode).
2. roll = atan2(y, z); pitch = atan2(−x, √(y² + z²)).
3. Exponential smoothing: `value += 0.25 × (new − value)`.
4. Pressing BOOT stores the current angles as the zero offset.
5. Bubble offset = angle / 30° × ring radius, clamped inside the ring, and signed by
   `PITCH_DIR` / `ROLL_DIR`.
6. Serial: `pitch,roll[,temp,humidity]`.

The tilt is derived from gravity only. It is valid while the board is static or moving slowly;
linear acceleration is read as tilt. There is no gyroscope fusion.

### ACCEL
X/Y/Z in g, magnitude √(x² + y² + z²), and a peak-hold that BOOT resets. The bars span ±2 g
on a ±4 g sensor range. Serial: `x,y,z` (three decimal places).

### CLIMATE
`Climate.poll()` runs every loop: it starts a conversion every 2 s and reads the result once
80 ms have passed, retrying while the busy bit is set. It tracks the current value and
min/max since boot. The same values are shown in TILT.

Conversion, per the AHT20 data format: RH = raw / 2²⁰ × 100 %;
T = raw / 2²⁰ × 200 − 50 °C.

## 4. Serial protocol

- 115200 baud, one record per line, comma-separated, no header.
- Lines starting with a letter are events: `RADAR_START`, `TILT_START`, `ACCEL_START`,
  `CLIMATE_START`, `MODE <NAME>`, plus MicroPython tracebacks.
- `pc/radar.py` accepts only lines that parse as `int,float`, so output from other modes is
  ignored.

## 5. Design decisions

| Decision | Reason | Trade-off |
|---|---|---|
| MicroPython instead of C/C++ (Arduino or ESP-IDF) | Interactive REPL for bring-up, fast iteration, no toolchain install | Slower execution and less deterministic timing; `time_pulse_us` resolution is enough for cm-level ranging |
| Own minimal drivers | No network or package manager needed on the board; each driver is short and readable | Fewer features than micropython-lib (no AHT20 CRC, no ADXL345 interrupts) |
| One cooperative loop with `enter/step/exit` modes | Simple, no concurrency bugs, easy to add modes | A blocking step (echo timeout, zero-button hold) delays the other loop work |
| Non-blocking AHT20 | The 80 ms conversion would otherwise stall the display | Small extra state machine |
| Mode index saved to flash on every change | Board restarts in the last mode | One small flash write per button press |
| Servo PWM released outside RADAR | No holding current or buzz | Servo position not held |
| Polled button with 30 ms debounce | Adequate at the observed loop rates (≈ 11 Hz in RADAR, ≈ 13 Hz in ACCEL) | A press shorter than one loop iteration could be missed; no interrupt |

## 6. Known limitations

- No CRC check on AHT20 data.
- No ADXL345 offset or gain calibration (≈ 0.91 g magnitude observed at rest).
- Speed of sound fixed (no temperature compensation), one sample per angle, no filtering.
- The HC-SR04 beam width (typically ~15°) limits angular resolution, whatever the 2° step.
- In TILT, holding BOOT blocks the main loop until it is released.
- No automated tests. Verification is by the diagnostic scripts and by observation.
- `radar.py` and `tilt.py` duplicate code that now lives in `hub.py`.
