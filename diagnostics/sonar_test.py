import machine, time
trig = machine.Pin(5, machine.Pin.OUT, value=0)
echo = machine.Pin(19, machine.Pin.IN)
print('echo idle level', echo.value())
for i in range(20):
    trig.value(0); time.sleep_us(5)
    trig.value(1); time.sleep_us(10); trig.value(0)
    t = machine.time_pulse_us(echo, 1, 30000)
    if t < 0:
        print(i, 'no echo' if t == -1 else 'timeout', t)
    else:
        print(i, '%.1f cm' % (t / 58.0))
    time.sleep_ms(300)
print('SONAR_DONE')
