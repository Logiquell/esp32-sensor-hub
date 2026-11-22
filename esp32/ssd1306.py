# Minimal SSD1306 I2C OLED driver (128x64 / 128x32) built on framebuf.
# Usage:
#   import machine, ssd1306
#   i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
#   oled = ssd1306.SSD1306(128, 64, i2c)
#   oled.text('hello', 0, 0); oled.show()
import framebuf


class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, i2c, addr=0x3C):
        self.width, self.height = width, height
        self.i2c, self.addr = i2c, addr
        self.pages = height // 8
        self.buf = bytearray(self.pages * width)
        super().__init__(self.buf, width, height, framebuf.MONO_VLSB)
        self._cmd_buf = bytearray(2)
        self.init_display()

    def cmd(self, *cmds):
        for c in cmds:
            self._cmd_buf[0] = 0x80
            self._cmd_buf[1] = c
            self.i2c.writeto(self.addr, self._cmd_buf)

    def init_display(self):
        self.cmd(
            0xAE,                       # display off
            0x20, 0x00,                 # horizontal addressing
            0x40,                       # start line 0
            0xA1,                       # segment remap
            0xA8, self.height - 1,      # multiplex
            0xC8,                       # COM scan direction
            0xD3, 0x00,                 # display offset
            0xDA, 0x12 if self.height == 64 else 0x02,
            0xD5, 0x80,                 # clock
            0xD9, 0xF1,                 # pre-charge
            0xDB, 0x30,                 # VCOM detect
            0x81, 0xCF,                 # contrast
            0xA4,                       # follow RAM
            0xA6,                       # normal (not inverted)
            0x8D, 0x14,                 # charge pump on
            0xAF,                       # display on
        )
        self.fill(0)
        self.show()

    def contrast(self, value):
        self.cmd(0x81, value & 0xFF)

    def invert(self, on):
        self.cmd(0xA7 if on else 0xA6)

    def power(self, on):
        self.cmd(0xAF if on else 0xAE)

    def show(self):
        self.cmd(0x21, 0, self.width - 1, 0x22, 0, self.pages - 1)
        self.i2c.writevto(self.addr, (b'\x40', self.buf))
