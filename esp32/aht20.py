# Minimal AHT20 temperature/humidity driver (I2C address 0x38).
# Blocking:      t, h = sensor.read()
# Non-blocking:  sensor.start(); ...>=80 ms later...; r = sensor.result()  (None if busy)
import time

ADDR = 0x38


class AHT20:
    def __init__(self, i2c, addr=ADDR):
        self.i2c, self.addr = i2c, addr
        time.sleep_ms(40)                                  # power-on delay
        if not self.i2c.readfrom(addr, 1)[0] & 0x08:       # not calibrated -> init
            self.i2c.writeto(addr, b'\xbe\x08\x00')
            time.sleep_ms(10)

    def start(self):
        self.i2c.writeto(self.addr, b'\xac\x33\x00')

    def result(self):
        d = self.i2c.readfrom(self.addr, 7)
        if d[0] & 0x80:                                    # still measuring
            return None
        hum = ((d[1] << 12) | (d[2] << 4) | (d[3] >> 4)) * 100 / 1048576
        temp = (((d[3] & 0x0F) << 16) | (d[4] << 8) | d[5]) * 200 / 1048576 - 50
        return temp, hum

    def read(self):
        self.start()
        time.sleep_ms(80)
        r = self.result()
        while r is None:
            time.sleep_ms(10)
            r = self.result()
        return r
