"""Copy a file onto the ESP32's MicroPython filesystem, then soft-reset
so main.py starts, and print the first few output lines.

    python upload.py ..\\esp32\\main.py            # COM3
    python upload.py ..\\esp32\\main.py --port COM5
"""
import argparse, os, sys, time

import serial


def raw_exec(s, code, wait=b'>'):
    s.write(code.encode() + b'\x04')
    out, end = b'', time.time() + 10
    while time.time() < end:
        out += s.read(256)
        if out.endswith(b'\x04>') or out.count(b'\x04') >= 2:
            break
    if b'Traceback' in out:
        raise RuntimeError(out.decode('utf-8', 'replace'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--port', default='COM3')
    ap.add_argument('--name', help='name on the board (default: same file name)')
    ap.add_argument('--show', type=float, default=4, help='seconds of output to show after reset')
    args = ap.parse_args()

    data = open(args.file, 'rb').read()
    name = args.name or os.path.basename(args.file)

    s = serial.Serial()
    s.port, s.baudrate, s.timeout = args.port, 115200, 0.2
    s.dtr = s.rts = False
    s.open()
    time.sleep(0.5)
    s.write(b'\r\x03\x03')                 # stop running program
    time.sleep(0.5); s.read(8192)
    s.write(b'\x01')                       # raw REPL
    time.sleep(0.3); s.read(8192)

    raw_exec(s, f"f=open({name!r},'wb')")
    for i in range(0, len(data), 256):
        raw_exec(s, f"f.write({data[i:i + 256]!r})")
    raw_exec(s, "f.close()")
    out = raw_exec(s, f"import os;print(os.stat({name!r})[6])")
    print(f'uploaded {name}: {len(data)} bytes, board reports', out.decode('utf-8', 'replace').strip('\x04>OK \r\n'))

    s.write(b'\x02')                       # normal REPL
    time.sleep(0.2); s.read(8192)
    s.write(b'\x04')                       # soft reset -> runs main.py
    out, end = b'', time.time() + args.show
    while time.time() < end:
        out += s.read(256)
    s.close()
    print('--- board output ---')
    print(out.decode('utf-8', 'replace')[-1500:])


if __name__ == '__main__':
    sys.exit(main())
