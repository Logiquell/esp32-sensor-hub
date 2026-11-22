# Bubble level on the OLED using the ADXL345, plus temperature/humidity
# from the AHT20 on the sides of the bubble.
# Prints "pitch,roll,temp_c,humidity" over USB serial too.
# Press the BOOT button (GPIO0) to zero the level at the current position.
import machine, time, math
import ssd1306, adxl345, aht20

CLIMATE_EVERY_MS = 2000  # how often to measure temperature/humidity

SCL_PIN, SDA_PIN = 22, 21
BUTTON_PIN = 0          # BOOT button on the dev board
FULL_SCALE_DEG = 30     # tilt at which the bubble hits the edge
SMOOTH = 0.25           # 0..1, lower = smoother but slower
PITCH_DIR = 1           # flip (1/-1) if the bubble moves the wrong way left/right
ROLL_DIR = 1            # flip (1/-1) if the bubble moves the wrong way up/down
# Two-colour OLED: rows 0-15 are yellow (text), rows 16-63 are blue (bubble).
CX, CY, R = 64, 40, 22  # bubble circle centred in the blue area


def angles(x, y, z):
    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y * y + z * z)))
    return pitch, roll


def run():
    i2c = machine.I2C(0, scl=machine.Pin(SCL_PIN), sda=machine.Pin(SDA_PIN), freq=400000)
    oled = ssd1306.SSD1306(128, 64, i2c)
    acc = adxl345.ADXL345(i2c)
    button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    try:
        climate = aht20.AHT20(i2c)
        temp, hum = climate.read()
    except OSError:                             # AHT20 missing: level still works
        climate, temp, hum = None, None, None
    measuring, last_climate = False, time.ticks_ms()

    pitch, roll = angles(*acc.read_g())
    zero_p = zero_r = 0.0
    print('TILT_START')

    while True:
        # temperature/humidity without blocking the bubble:
        # start a measurement, pick up the result on a later loop (>=80 ms)
        if climate:
            try:
                now = time.ticks_ms()
                if not measuring and time.ticks_diff(now, last_climate) >= CLIMATE_EVERY_MS:
                    climate.start()
                    measuring, last_climate = True, now
                elif measuring and time.ticks_diff(now, last_climate) >= 80:
                    r = climate.result()
                    if r:
                        temp, hum = r
                        measuring = False
            except OSError:
                measuring = False

        p, r = angles(*acc.read_g())
        pitch += SMOOTH * (p - pitch)
        roll += SMOOTH * (r - roll)

        if button.value() == 0:                 # BOOT pressed -> set zero
            zero_p, zero_r = pitch, roll
            oled.fill(0); oled.text('ZEROED', 40, 4); oled.show()
            while button.value() == 0:
                time.sleep_ms(20)

        dp, dr = pitch - zero_p, roll - zero_r
        if temp is None:
            print('%.1f,%.1f' % (dp, dr))
        else:
            print('%.1f,%.1f,%.1f,%.1f' % (dp, dr, temp, hum))

        # bubble moves "uphill" like a real spirit level
        bx = PITCH_DIR * dp / FULL_SCALE_DEG * R    # pitch -> left/right on screen
        by = ROLL_DIR * dr / FULL_SCALE_DEG * R     # roll  -> up/down on screen
        dist = math.sqrt(bx * bx + by * by)
        if dist > R - 4:                        # keep the bubble inside the ring
            bx, by = bx * (R - 4) / dist, by * (R - 4) / dist

        oled.fill(0)
        # yellow band: labels + values
        oled.text('PITCH', 4, 0)
        oled.text('ROLL', 84, 0)
        oled.text('%+6.1f' % dp, 0, 8)
        oled.text('%+6.1f' % dr, 72, 8)
        # blue area: bubble level
        oled.ellipse(CX, CY, R, R, 1)           # outer ring
        oled.ellipse(CX, CY, 6, 6, 1)           # centre target
        oled.hline(CX - R, CY, 2 * R + 1, 1)
        oled.vline(CX, CY - R, 2 * R + 1, 1)
        oled.ellipse(CX + int(bx), CY + int(by), 4, 4, 1, True)   # bubble
        # blue area sides: temperature (left), humidity (right)
        if temp is not None:
            oled.text('TEMP', 4, 20)
            oled.text('%4.1fC' % temp, 0, 30)
            oled.text('HUM', 96, 20)
            oled.text('%3.0f%%' % hum, 96, 30)
        if abs(dp) < 1 and abs(dr) < 1:
            oled.text('LEVEL', 0, 56)
        oled.show()
        time.sleep_ms(30)


try:
    run()
except KeyboardInterrupt:
    print('TILT_STOP')
