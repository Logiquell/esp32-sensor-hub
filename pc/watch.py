"""Watch the board's serial output without resetting it.
Prints mode changes / start banners, and a sample of data lines per mode.

    python watch.py [--port COM3] [--seconds 30]
"""
import argparse, time

import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM3')
ap.add_argument('--seconds', type=float, default=30)
ap.add_argument('--restart', action='store_true', help='soft-reset the board first (restarts main.py)')
args = ap.parse_args()

s = serial.Serial()
s.port, s.baudrate, s.timeout = args.port, 115200, 0.2
s.dtr = s.rts = False
s.open()
if args.restart:
    s.write(b'\r\x03\x03\x02')      # stop whatever runs, back to normal REPL
    time.sleep(0.3); s.read(8192)
    s.write(b'\x04')                # soft reset -> main.py

print(f'watching {args.port} for {args.seconds:.0f}s - press the MODE button now')
t0 = time.time()
buf, count, last = b'', 0, None
while time.time() - t0 < args.seconds:
    buf += s.read(512)
    while b'\n' in buf:
        line, buf = buf.split(b'\n', 1)
        text = line.decode('utf-8', 'replace').strip()
        if not text:
            continue
        stamp = f'{time.time() - t0:5.1f}s'
        if text[0].isalpha():                 # MODE / *_START / errors
            if last:
                print(f'        last data: {last}  ({count} lines)')
            print(f'{stamp}  {text}')
            count, last = 0, None
        else:
            count += 1
            if count in (1, 2):
                print(f'{stamp}    {text}')
            last = text
if last:
    print(f'        last data: {last}  ({count} lines)')
s.close()
