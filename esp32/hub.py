# Multi-mode app: press the MODE button to cycle RADAR -> TILT -> ACCEL -> CLIMATE.
# The last mode is remembered across resets (mode.txt on the board).
#
# Wiring
#   MODE button  -> GPIO4 and GND (internal pull-up, no resistor)
#   BOOT button  -> zeroes the level in TILT mode, resets the peak in ACCEL mode
#   HC-SR04 Trig -> GPIO5, Echo -> 1k -> GPIO19 -> 2.2k -> GND, VCC 5V
#   Servo signal -> GPIO13, power 5V
#   OLED / ADXL345 / AHT20 on I2C: SDA GPIO21, SCL GPIO22, VCC 3.3V
#
# Serial output (115200) per mode:
#   RADAR   "angle,distance_cm"            (works with pc/radar.py)
#   TILT    "pitch,roll,temp_c,humidity"
#   ACCEL   "x_g,y_g,z_g"
#   CLIMATE "temp_c,humidity"
import machine, time, math, framebuf
import ssd1306, adxl345, aht20

SCL_PIN, SDA_PIN = 22, 21
MODE_PIN = 4
ZERO_PIN = 0
TRIG_PIN, ECHO_PIN, SERVO_PIN = 5, 19, 13
MODE_FILE = 'mode.txt'

i2c = machine.I2C(0, scl=machine.Pin(SCL_PIN), sda=machine.Pin(SDA_PIN), freq=400000)
oled = ssd1306.SSD1306(128, 64, i2c)
# Two-colour OLED: rows 0-15 yellow, rows 16-63 blue.


def big_text(s, x, y, scale=2):
    w = len(s) * 8
    fb = framebuf.FrameBuffer(bytearray(w), w, 8, framebuf.MONO_VLSB)
    fb.text(s, 0, 0, 1)
    for py in range(8):
        for px in range(w):
            if fb.pixel(px, py):
                oled.fill_rect(x + px * scale, y + py * scale, scale, scale, 1)


def centred_big(s, y, scale=2):
    big_text(s, (128 - len(s) * 8 * scale) // 2, y, scale)


# ---------------------------------------------------------------- climate
class Climate:
    """Shared AHT20 sampler; measures every EVERY_MS without blocking."""
    EVERY_MS = 2000

    def __init__(self):
        self.temp = self.hum = None
        self.tmin = self.tmax = None
        try:
            self.dev = aht20.AHT20(i2c)
            self._store(*self.dev.read())
        except OSError:
            self.dev = None
        self.measuring, self.last = False, time.ticks_ms()

    def _store(self, t, h):
        self.temp, self.hum = t, h
        self.tmin = t if self.tmin is None else min(self.tmin, t)
        self.tmax = t if self.tmax is None else max(self.tmax, t)

    def poll(self):
        if not self.dev:
            return
        try:
            now = time.ticks_ms()
            if not self.measuring and time.ticks_diff(now, self.last) >= self.EVERY_MS:
                self.dev.start()
                self.measuring, self.last = True, now
            elif self.measuring and time.ticks_diff(now, self.last) >= 80:
                r = self.dev.result()
                if r:
                    self._store(*r)
                    self.measuring = False
        except OSError:
            self.measuring = False


# ---------------------------------------------------------------- radar
class Radar:
    name = 'RADAR'
    STEP = 2
    SETTLE_MS = 15
    RANGE_CM = 200
    CX, CY, R = 64, 63, 46          # semicircle stays inside the blue area
    PULSE_MIN_NS, PULSE_MAX_NS = 500_000, 2_400_000

    def __init__(self):
        self.trig = machine.Pin(TRIG_PIN, machine.Pin.OUT, value=0)
        self.echo = machine.Pin(ECHO_PIN, machine.Pin.IN)
        self.servo = None
        self.cos = [math.cos(math.radians(a)) for a in range(181)]
        self.sin = [math.sin(math.radians(a)) for a in range(181)]

    def enter(self):
        self.servo = machine.PWM(machine.Pin(SERVO_PIN), freq=50)
        self.a, self.dir, self.hits = 0, 1, {}
        self.set_angle(0)
        time.sleep_ms(300)
        print('RADAR_START')

    def exit(self):
        if self.servo:
            self.servo.deinit()                         # servo goes limp and quiet
            self.servo = None

    def set_angle(self, a):
        self.servo.duty_ns(self.PULSE_MIN_NS + (self.PULSE_MAX_NS - self.PULSE_MIN_NS) * a // 180)

    def measure(self):
        t = self.trig
        t.value(0); time.sleep_us(4); t.value(1); time.sleep_us(10); t.value(0)
        us = machine.time_pulse_us(self.echo, 1, 25000)
        if us < 0:
            return -1
        d = us / 58.0
        return d if 2 <= d <= 400 else -1

    def xy(self, a, k):
        return int(self.CX + k * self.cos[a]), int(self.CY - k * self.sin[a])

    def step(self):
        a = self.a
        self.set_angle(a)
        time.sleep_ms(self.SETTLE_MS)
        d = self.measure()
        print('%d,%.1f' % (a, d))
        if d > 0:
            self.hits[a] = d
        else:
            self.hits.pop(a, None)

        o, r = oled, self.R
        o.fill(0)
        o.text('RADAR', 0, 0)
        o.text('%dcm' % self.RANGE_CM, 88, 0)
        o.text('%3d deg' % a, 0, 8)
        o.text(('%4dcm' % d) if d > 0 else '   ---', 80, 8)
        for k in (r // 2, r):
            o.ellipse(self.CX, self.CY, k, k, 1, False, 0b0011)
        o.hline(self.CX - r, self.CY, 2 * r + 1, 1)
        x, y = self.xy(a, r)
        o.line(self.CX, self.CY, x, y, 1)
        for ha, hd in self.hits.items():
            hx, hy = self.xy(ha, r * min(hd, self.RANGE_CM) / self.RANGE_CM)
            o.fill_rect(hx - 1, hy - 1, 3, 3, 1)
        o.show()

        self.a += self.STEP * self.dir
        if self.a >= 180 or self.a <= 0:
            self.a = max(0, min(180, self.a))
            self.dir = -self.dir


# ---------------------------------------------------------------- tilt
class Tilt:
    name = 'TILT'
    FULL_SCALE_DEG = 30
    SMOOTH = 0.25
    PITCH_DIR = 1                   # flip (1/-1) if the bubble moves the wrong way left/right
    ROLL_DIR = 1                    # flip (1/-1) if the bubble moves the wrong way up/down
    CX, CY, R = 64, 40, 22

    def __init__(self, climate, acc):
        self.climate = climate
        self.acc = acc
        self.zero_btn = machine.Pin(ZERO_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
        self.zero_p = self.zero_r = 0.0

    @staticmethod
    def angles(x, y, z):
        roll = math.degrees(math.atan2(y, z))
        pitch = math.degrees(math.atan2(-x, math.sqrt(y * y + z * z)))
        return pitch, roll

    def enter(self):
        self.pitch, self.roll = self.angles(*self.acc.read_g())
        print('TILT_START')

    def exit(self):
        pass

    def step(self):
        p, r = self.angles(*self.acc.read_g())
        self.pitch += self.SMOOTH * (p - self.pitch)
        self.roll += self.SMOOTH * (r - self.roll)

        if self.zero_btn.value() == 0:
            self.zero_p, self.zero_r = self.pitch, self.roll
            oled.fill(0); oled.text('ZEROED', 40, 4); oled.show()
            while self.zero_btn.value() == 0:
                time.sleep_ms(20)

        dp, dr = self.pitch - self.zero_p, self.roll - self.zero_r
        c = self.climate
        if c.temp is None:
            print('%.1f,%.1f' % (dp, dr))
        else:
            print('%.1f,%.1f,%.1f,%.1f' % (dp, dr, c.temp, c.hum))

        R = self.R
        bx = self.PITCH_DIR * dp / self.FULL_SCALE_DEG * R
        by = self.ROLL_DIR * dr / self.FULL_SCALE_DEG * R
        dist = math.sqrt(bx * bx + by * by)
        if dist > R - 4:
            bx, by = bx * (R - 4) / dist, by * (R - 4) / dist

        o = oled
        o.fill(0)
        o.text('PITCH', 4, 0)
        o.text('ROLL', 84, 0)
        o.text('%+6.1f' % dp, 0, 8)
        o.text('%+6.1f' % dr, 72, 8)
        o.ellipse(self.CX, self.CY, R, R, 1)
        o.ellipse(self.CX, self.CY, 6, 6, 1)
        o.hline(self.CX - R, self.CY, 2 * R + 1, 1)
        o.vline(self.CX, self.CY - R, 2 * R + 1, 1)
        o.ellipse(self.CX + int(bx), self.CY + int(by), 4, 4, 1, True)
        if c.temp is not None:
            o.text('TEMP', 4, 20)
            o.text('%4.1fC' % c.temp, 0, 30)
            o.text('HUM', 96, 20)
            o.text('%3.0f%%' % c.hum, 96, 30)
        if abs(dp) < 1 and abs(dr) < 1:
            o.text('LEVEL', 0, 56)
        o.show()
        time.sleep_ms(30)


# ---------------------------------------------------------------- accelerometer
class Accel:
    name = 'ACCEL'
    BAR_G = 2.0                     # bar reaches the end at +-2 g
    BAR_X, BAR_W = 56, 72           # bar area on the right, centre at BAR_X + BAR_W/2

    def __init__(self, acc):
        self.acc = acc
        self.reset_btn = machine.Pin(ZERO_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
        self.peak = 0.0

    def enter(self):
        print('ACCEL_START')

    def exit(self):
        pass

    def step(self):
        x, y, z = self.acc.read_g()
        mag = math.sqrt(x * x + y * y + z * z)
        self.peak = max(self.peak, mag)
        if self.reset_btn.value() == 0:             # BOOT: reset peak
            self.peak = mag
        print('%.3f,%.3f,%.3f' % (x, y, z))

        o = oled
        o.fill(0)
        o.text('ACCEL', 0, 0)
        o.text('%5.2fg' % mag, 80, 0)
        o.text('peak', 0, 8)
        o.text('%5.2fg' % self.peak, 80, 8)
        cx = self.BAR_X + self.BAR_W // 2
        half = self.BAR_W // 2
        for i, (label, v) in enumerate((('X', x), ('Y', y), ('Z', z))):
            row = 20 + i * 15
            o.text('%s%+5.2f' % (label, v), 0, row)
            o.rect(self.BAR_X, row, self.BAR_W, 8, 1)
            o.vline(cx, row - 2, 12, 1)                 # zero mark
            n = int(min(abs(v), self.BAR_G) / self.BAR_G * (half - 1))
            if v >= 0:
                o.fill_rect(cx, row + 2, n, 4, 1)
            else:
                o.fill_rect(cx - n, row + 2, n, 4, 1)
        o.show()
        time.sleep_ms(40)


# ---------------------------------------------------------------- climate view
class ClimateView:
    name = 'CLIMATE'

    def __init__(self, climate):
        self.climate = climate
        self.last_print = 0

    def enter(self):
        print('CLIMATE_START')

    def exit(self):
        pass

    def step(self):
        c, o = self.climate, oled
        o.fill(0)
        if c.temp is None:
            o.text('CLIMATE', 36, 0)
            o.text('AHT20 not found', 4, 36)
        else:
            o.text('CLIMATE', 36, 0)
            o.text('min%5.1f max%5.1f' % (c.tmin, c.tmax), 0, 8)
            centred_big('%.1fC' % c.temp, 20)
            centred_big('%.1f%%' % c.hum, 44)
            now = time.ticks_ms()
            if time.ticks_diff(now, self.last_print) >= 1000:
                print('%.1f,%.1f' % (c.temp, c.hum))
                self.last_print = now
        o.show()
        time.sleep_ms(100)


# ---------------------------------------------------------------- main loop
def load_mode(n):
    try:
        with open(MODE_FILE) as f:
            return int(f.read()) % n
    except (OSError, ValueError):
        return 0


def save_mode(i):
    try:
        with open(MODE_FILE, 'w') as f:
            f.write(str(i))
    except OSError:
        pass


def splash(name):
    oled.fill(0)
    oled.text('MODE', 48, 4)
    centred_big(name, 30)
    oled.show()


def run():
    climate = Climate()
    acc = adxl345.ADXL345(i2c, g_range=4)          # +-4 g so shakes don't clip
    modes = [Radar(), Tilt(climate, acc), Accel(acc), ClimateView(climate)]
    button = machine.Pin(MODE_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

    idx = load_mode(len(modes))
    mode = modes[idx]
    splash(mode.name)
    time.sleep_ms(600)
    mode.enter()
    was_up = True

    while True:
        climate.poll()
        up = button.value() == 1
        if was_up and not up:                       # button pressed
            time.sleep_ms(30)                       # debounce
            if button.value() == 0:
                mode.exit()
                idx = (idx + 1) % len(modes)
                save_mode(idx)
                mode = modes[idx]
                splash(mode.name)
                print('MODE', mode.name)
                while button.value() == 0:          # wait for release
                    time.sleep_ms(20)
                time.sleep_ms(400)
                mode.enter()
                up = True
        was_up = up
        try:
            mode.step()
        except OSError:                             # I2C hiccup: keep going
            time.sleep_ms(50)


try:
    run()
except KeyboardInterrupt:
    machine.PWM(machine.Pin(SERVO_PIN)).deinit()    # stop the servo if it was sweeping
    print('HUB_STOP')
