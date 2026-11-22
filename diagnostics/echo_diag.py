import machine, time
trig = machine.Pin(5, machine.Pin.OUT, value=0)
echo = machine.Pin(19, machine.Pin.IN)
# 1) idle: sample echo for 2 s with no trigger
hi = 0; n = 0; t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < 2000:
    hi += echo.value(); n += 1
print('idle high ratio', hi / n)
# 2) with pull-down: does it still read high? (driven vs floating)
echo2 = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_DOWN)
time.sleep_ms(10)
print('with pulldown', echo2.value())
echo = machine.Pin(19, machine.Pin.IN)
# 3) triggered with long timeouts
for i in range(5):
    trig.value(1); time.sleep_us(10); trig.value(0)
    low = machine.time_pulse_us(echo, 0, 300000)
    t = machine.time_pulse_us(echo, 1, 300000)
    print(i, 'low_us', low, 'high_us', t)
    time.sleep_ms(200)
print('DIAG_DONE')
