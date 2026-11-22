"""Run a MicroPython script on the ESP32 once (without saving it) and print its output.

    python run_on_board.py some_test.py [--port COM3] [--timeout 15]
"""
import argparse, time

import serial

ap = argparse.ArgumentParser()
ap.add_argument('file')
ap.add_argument('--port', default='COM3')
ap.add_argument('--timeout', type=float, default=15)
args = ap.parse_args()

code = open(args.file, 'rb').read()
s = serial.Serial()
s.port, s.baudrate, s.timeout = args.port, 115200, 0.2
s.dtr = s.rts = False
s.open()
time.sleep(0.5)
s.write(b'\r\x03\x03'); time.sleep(0.5); s.read(8192)
s.write(b'\x01'); time.sleep(0.3); s.read(8192)
s.write(code + b'\x04')
out, end = b'', time.time() + args.timeout
while time.time() < end:
    out += s.read(512)
    if out.count(b'\x04') >= 2:       # raw REPL: OK <stdout> \x04 <stderr> \x04
        break
s.write(b'\x02')
s.close()
text = out.decode('utf-8', 'replace')
if text.startswith('OK'):
    text = text[2:]
stdout, _, rest = text.partition('\x04')
err = rest.partition('\x04')[0]
print(stdout.rstrip())
if err.strip():
    print('--- error ---')
    print(err.rstrip())
