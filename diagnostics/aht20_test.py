import machine, time
i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
found = i2c.scan()
print('I2C devices:', [hex(a) for a in found])
A = 0x38
if A not in found:
    print('AHT20 not found')
else:
    time.sleep_ms(40)
    status = i2c.readfrom(A, 1)[0]
    print('status 0x%02x calibrated=%s' % (status, bool(status & 0x08)))
    if not status & 0x08:
        i2c.writeto(A, b'\xbe\x08\x00'); time.sleep_ms(10)
    for i in range(5):
        i2c.writeto(A, b'\xac\x33\x00')
        time.sleep_ms(80)
        d = i2c.readfrom(A, 7)
        if d[0] & 0x80:
            print('busy'); continue
        hum = ((d[1] << 12) | (d[2] << 4) | (d[3] >> 4)) * 100 / 1048576
        tmp = (((d[3] & 0x0F) << 16) | (d[4] << 8) | d[5]) * 200 / 1048576 - 50
        print('temp %.2f C   humidity %.1f %%' % (tmp, hum))
        time.sleep_ms(1000)
