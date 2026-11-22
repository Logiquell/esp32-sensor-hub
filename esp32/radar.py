# ESP32 radar: sweeps an HC-SR04 on a servo, prints "angle,distance_cm"
# over USB serial (115200) for the PC display, and draws a mini radar on
# a 128x64 SSD1306 OLED. distance -1 = no echo / out of range.
#
# Wiring
#   HC-SR04 VCC  -> 5V (HW-131)      HC-SR04 GND -> common GND
#   HC-SR04 Trig -> GPIO5
#   HC-SR04 Echo -> 1k -> GPIO19 -> 2.2k -> GND   (voltage divider)
#   Servo red    -> 5V (HW-131)      Servo brown -> common GND
#   Servo orange -> GPIO13 (signal)
#   OLED VCC     -> 3.3V (HW-131)    OLED GND    -> common GND
#   OLED SCL     -> GPIO22           OLED SDA    -> GPIO21
#   (avoid GPIO18 - it misbehaved after the earlier wiring fault)

import machine, time, math

TRIG_PIN = 5
ECHO_PIN = 19
SERVO_PIN = 13
SCL_PIN, SDA_PIN = 22, 21

ANGLE_MIN = 0
ANGLE_MAX = 180
STEP = 2            # degrees per step
SETTLE_MS = 15      # extra wait for the servo (OLED redraw adds ~25 ms)
MAX_CM = 400
OLED_RANGE_CM = 200 # distance at the outer ring of the OLED radar

trig = machine.Pin(TRIG_PIN, machine.Pin.OUT, value=0)
echo = machine.Pin(ECHO_PIN, machine.Pin.IN)
servo = machine.PWM(machine.Pin(SERVO_PIN), freq=50)

# SG90: ~0.5 ms = 0 deg, ~2.4 ms = 180 deg. Tweak if your servo hits its end stops.
PULSE_MIN_NS = 500_000
PULSE_MAX_NS = 2_400_000


def set_angle(a):
    ns = PULSE_MIN_NS + (PULSE_MAX_NS - PULSE_MIN_NS) * a // 180
    servo.duty_ns(ns)


def measure_cm():
    trig.value(0)
    time.sleep_us(4)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    t = machine.time_pulse_us(echo, 1, 25000)   # 25 ms ~ 4.3 m
    if t < 0:
        return -1
    d = t / 58.0
    return d if 2 <= d <= MAX_CM else -1


class OledRadar:
    CX, CY, R = 64, 63, 52          # centre at bottom middle, leave top rows for text

    def __init__(self):
        import ssd1306
        i2c = machine.I2C(0, scl=machine.Pin(SCL_PIN), sda=machine.Pin(SDA_PIN), freq=400000)
        self.o = ssd1306.SSD1306(128, 64, i2c)
        self.hits = {}                                  # angle -> distance
        self.cos = {a: math.cos(math.radians(a)) for a in range(0, 181)}
        self.sin = {a: math.sin(math.radians(a)) for a in range(0, 181)}

    def xy(self, a, k):
        return int(self.CX + k * self.cos[a]), int(self.CY - k * self.sin[a])

    def update(self, a, d):
        if d > 0:
            self.hits[a] = d
        else:
            self.hits.pop(a, None)
        o, cx, cy, r = self.o, self.CX, self.CY, self.R
        o.fill(0)
        for k in (r // 2, r):                           # range rings (top half)
            o.ellipse(cx, cy, k, k, 1, False, 0b0011)
        o.hline(cx - r, cy, 2 * r + 1, 1)
        x, y = self.xy(a, r)
        o.line(cx, cy, x, y, 1)                         # sweep line
        for ha, hd in self.hits.items():
            k = r * min(hd, OLED_RANGE_CM) / OLED_RANGE_CM
            hx, hy = self.xy(ha, k)
            o.fill_rect(hx - 1, hy - 1, 3, 3, 1)       # object
        o.text('%3d' % a, 0, 0)
        o.text(('%3dcm' % d) if d > 0 else '  ---', 88, 0)
        o.show()


def run():
    print('RADAR_START')
    try:
        oled = OledRadar()
    except Exception as e:                              # radar still works without the OLED
        print('OLED_OFF', e)
        oled = None
    a, direction = ANGLE_MIN, 1
    set_angle(a)
    time.sleep_ms(400)
    while True:
        set_angle(a)
        time.sleep_ms(SETTLE_MS)
        d = measure_cm()
        print('%d,%.1f' % (a, d))
        if oled:
            try:
                oled.update(a, d)
            except OSError:                             # loose I2C wire: keep sweeping
                pass
        a += STEP * direction
        if a >= ANGLE_MAX or a <= ANGLE_MIN:
            a = max(ANGLE_MIN, min(ANGLE_MAX, a))
            direction = -direction


try:
    run()
except KeyboardInterrupt:
    servo.deinit()
    print('RADAR_STOP')
