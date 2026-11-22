import machine, time
for pull, name in ((machine.Pin.PULL_DOWN, 'pulldown'), (machine.Pin.PULL_UP, 'pullup'), (machine.Pin.PULL_DOWN, 'pulldown again')):
    p = machine.Pin(19, machine.Pin.IN, pull)
    time.sleep_ms(200)
    s = sum(p.value() for _ in range(1000))
    print(name, 'high samples', s, '/ 1000')
print('PIN_DONE')
