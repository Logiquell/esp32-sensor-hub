# Minimal ADXL345 I2C driver (DFRobot SEN0032).
# Wiring: VCC->3.3V, GND, SDA->GPIO21, SCL->GPIO22, CS->3.3V, SDO->GND (addr 0x53)
import struct, time

DEVID = 0x00
BW_RATE = 0x2C
POWER_CTL = 0x2D
DATA_FORMAT = 0x31
DATAX0 = 0x32

RANGES = {2: 0, 4: 1, 8: 2, 16: 3}
SCALE_G = 0.0039            # full-resolution mode: 3.9 mg/LSB at every range


class ADXL345:
    def __init__(self, i2c, addr=0x53, g_range=2):
        self.i2c, self.addr = i2c, addr
        devid = i2c.readfrom_mem(addr, DEVID, 1)[0]
        if devid != 0xE5:
            raise OSError('ADXL345 not found (DEVID 0x%02x)' % devid)
        i2c.writeto_mem(addr, DATA_FORMAT, bytes([0x08 | RANGES[g_range]]))  # full res
        i2c.writeto_mem(addr, BW_RATE, b'\x0a')                               # 100 Hz
        i2c.writeto_mem(addr, POWER_CTL, b'\x08')                             # measure
        time.sleep_ms(20)

    def read_raw(self):
        return struct.unpack('<hhh', self.i2c.readfrom_mem(self.addr, DATAX0, 6))

    def read_g(self):
        x, y, z = self.read_raw()
        return x * SCALE_G, y * SCALE_G, z * SCALE_G
