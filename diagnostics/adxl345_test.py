import machine, time, struct
i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
found = i2c.scan()
print('I2C devices:', [hex(a) for a in found])
addr = 0x53 if 0x53 in found else (0x1D if 0x1D in found else None)
if addr is None:
    print('ADXL345 not found')
else:
    devid = i2c.readfrom_mem(addr, 0x00, 1)[0]
    print('addr', hex(addr), 'DEVID', hex(devid), '(0xe5 = ADXL345)' if devid == 0xE5 else '(unexpected)')
    i2c.writeto_mem(addr, 0x31, b'\x08')   # DATA_FORMAT: full resolution, +-2g
    i2c.writeto_mem(addr, 0x2C, b'\x0a')   # BW_RATE: 100 Hz
    i2c.writeto_mem(addr, 0x2D, b'\x08')   # POWER_CTL: measure
    time.sleep_ms(50)
    for i in range(10):
        x, y, z = struct.unpack('<hhh', i2c.readfrom_mem(addr, 0x32, 6))
        g = 0.0039                          # 3.9 mg/LSB in full-res mode
        print('x %+.2f g  y %+.2f g  z %+.2f g' % (x * g, y * g, z * g))
        time.sleep_ms(300)
