import machine, time
machine.PWM(machine.Pin(13)).deinit()
b = machine.Pin(4, machine.Pin.IN, machine.Pin.PULL_UP)
print('GPIO4 idle level', b.value(), '(1 = released, expected)')
presses, prev, low_samples, n = 0, b.value(), 0, 0
t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < 15000:
    v = b.value(); n += 1
    low_samples += (v == 0)
    if prev == 1 and v == 0:
        presses += 1
        print('press', presses, 'at %.1fs' % (time.ticks_diff(time.ticks_ms(), t0) / 1000))
    prev = v
    time.sleep_ms(10)
print('presses', presses, 'low ratio %.2f' % (low_samples / n))
