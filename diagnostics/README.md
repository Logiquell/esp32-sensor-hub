# Diagnostics

Small MicroPython scripts used during bring-up and fault-finding. Each runs **once from RAM**
on the board (nothing is saved to flash) and prints its result over serial:

```bash
cd pc
python run_on_board.py ../diagnostics/i2c_scan.py
```

Running a diagnostic interrupts the firmware that is currently running. Press **EN** on the
board (or use `python watch.py --restart`) to start `main.py` again afterwards.

| Script | Checks | Expected result |
|---|---|---|
| `i2c_scan.py` | Devices on the I2C bus (GPIO21/22) | `['0x38', '0x3c', '0x53']` with all three I2C parts fitted |
| `oled_test.py` | SSD1306 OLED draws (needs `ssd1306.py` on the board) | Test pattern on the display |
| `adxl345_test.py` | ADXL345 address, `DEVID` register, 10 X/Y/Z samples | `DEVID 0xe5`; about +1 g on the vertical axis at rest |
| `aht20_test.py` | AHT20 calibration bit and 5 temperature/humidity samples | `calibrated=True`, plausible room values |
| `sonar_test.py` | HC-SR04: 20 trigger/echo cycles (Trig GPIO5, Echo GPIO19) | Stable distances in cm |
| `echo_diag.py` | Echo-line state: idle level, driven vs. floating (pull-down), pulse timing | Idle low; pulses after each trigger |
| `pin_pull_test.py` | GPIO19 with internal pull-down / pull-up / pull-down | Divider fitted: low in all three. Pin floating: follows the pull. Pin driven high: high in all three |
| `button_test.py` | MODE button on GPIO4 for 15 s (stops the servo PWM first) | `idle level 1`; one count per press |

`pin_pull_test.py` and `echo_diag.py` were written to tell apart *floating*, *pulled* and
*actively driven* lines when the ultrasonic sensor returned no readings. See
[`docs/development.md`](../docs/development.md) for the faults they found.
