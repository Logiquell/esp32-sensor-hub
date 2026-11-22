"""PC radar display for the ESP32 sweep firmware.

Reads "angle,distance_cm" lines from the board and draws a radar screen.
Needs only pyserial (pip install pyserial); the window uses tkinter,
which ships with Python.

    python radar.py                 # COM3, 200 cm range
    python radar.py --port COM5 --range 100
"""
import argparse, math, queue, threading, time, tkinter as tk

import serial

BG = '#03110a'
GRID = '#0f5a2e'
SWEEP = '#2bff88'
TEXT = '#5fdc95'
HIT = (255, 60, 60)       # newest hit colour, fades towards BG
FADE_S = 4.0              # how long a hit stays visible


def reader(port, q, stop):
    while not stop.is_set():
        try:
            s = serial.Serial()
            s.port, s.baudrate, s.timeout = port, 115200, 0.5
            s.dtr = s.rts = False            # don't reset the board
            s.open()
            q.put(('status', f'connected to {port}'))
            buf = b''
            while not stop.is_set():
                buf += s.read(256)
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    try:
                        a, d = line.decode().strip().split(',')
                        q.put(('data', int(a), float(d)))
                    except ValueError:
                        pass                 # banner / partial line
        except serial.SerialException as e:
            q.put(('status', f'{port}: {e.__class__.__name__}, retrying...'))
            time.sleep(1.5)


class Radar:
    def __init__(self, root, max_cm):
        self.max_cm = max_cm
        self.c = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.c.pack(fill='both', expand=True)
        self.c.bind('<Configure>', lambda e: self.layout())
        self.hits = {}                       # angle -> (dist, time)
        self.angle = 0
        self.dist = -1
        self.status = 'waiting for data...'

    def layout(self):
        w, h = self.c.winfo_width(), self.c.winfo_height()
        self.r = max(50, min(w / 2 - 30, h - 70))
        self.cx, self.cy = w / 2, h - 40

    def polar(self, angle, cm):
        rad = math.radians(angle)
        k = self.r * cm / self.max_cm
        return self.cx + k * math.cos(rad), self.cy - k * math.sin(rad)

    def draw(self):
        c, cx, cy, r = self.c, self.cx, self.cy, self.r
        c.delete('all')
        for i in range(1, 5):
            rr = r * i / 4
            c.create_arc(cx - rr, cy - rr, cx + rr, cy + rr, start=0, extent=180,
                         style='arc', outline=GRID)
            c.create_text(cx + rr + 4, cy + 12, text=f'{self.max_cm * i // 4} cm',
                          fill=TEXT, font=('Consolas', 9), anchor='w')
        for a in range(0, 181, 30):
            x, y = self.polar(a, self.max_cm)
            c.create_line(cx, cy, x, y, fill=GRID)
            lx, ly = self.polar(a, self.max_cm * 1.07)
            c.create_text(lx, ly, text=f'{a}°', fill=TEXT, font=('Consolas', 9))

        now = time.time()
        for a, (d, t) in list(self.hits.items()):
            age = now - t
            if age > FADE_S:
                del self.hits[a]
                continue
            f = 1 - age / FADE_S
            col = '#%02x%02x%02x' % tuple(int(b + (h - b) * f) for h, b in zip(HIT, (3, 17, 10)))
            x, y = self.polar(a, min(d, self.max_cm))
            ex, ey = self.polar(a, self.max_cm)
            c.create_line(x, y, ex, ey, fill=col, width=3)          # "shadow" behind object
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=col, outline='')

        x, y = self.polar(self.angle, self.max_cm)
        c.create_line(cx, cy, x, y, fill=SWEEP, width=2)

        d = f'{self.dist:.1f} cm' if self.dist > 0 else 'out of range'
        c.create_text(12, 12, anchor='nw', fill=TEXT, font=('Consolas', 12),
                      text=f'angle {self.angle:3d}°   distance {d}')
        c.create_text(12, 34, anchor='nw', fill=GRID, font=('Consolas', 9), text=self.status)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='COM3')
    ap.add_argument('--range', type=int, default=200, help='max distance shown, cm')
    args = ap.parse_args()

    root = tk.Tk()
    root.title('ESP32 Radar')
    root.geometry('900x560')
    root.configure(bg=BG)
    radar = Radar(root, args.range)

    q, stop = queue.Queue(), threading.Event()
    threading.Thread(target=reader, args=(args.port, q, stop), daemon=True).start()

    def tick():
        while not q.empty():
            msg = q.get_nowait()
            if msg[0] == 'status':
                radar.status = msg[1]
            else:
                _, a, d = msg
                radar.angle, radar.dist = a, d
                if 0 < d:
                    radar.hits[a] = (d, time.time())
                else:
                    radar.hits.pop(a, None)
        radar.draw()
        root.after(33, tick)

    root.after(100, lambda: (radar.layout(), tick()))
    root.protocol('WM_DELETE_WINDOW', lambda: (stop.set(), root.destroy()))
    root.mainloop()


if __name__ == '__main__':
    main()
