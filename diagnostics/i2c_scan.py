import machine
i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
found = i2c.scan()
print('I2C devices:', [hex(a) for a in found])
