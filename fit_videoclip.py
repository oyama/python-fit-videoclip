import argparse
from fitparse import FitFile
import moviepy.editor as mpy
import numpy as np
import pandas as pd
import math
import gizeh as gz
import os
import moviepy.video.fx.all as vfx


class FitDataFrame:
    # TODO: extend DataFrame object
    def __init__(self, fit):
        self.fit = fit
        self._record = list(self.fit.get_messages('record'))
        self._columns = None

    def as_df(self):
        rows = []
        last_timestamp = None

        for m in self._record:
            t = m.get('timestamp').value
            if last_timestamp is not None:
                delta = int((t - last_timestamp).total_seconds())
                # add blank row
                for b in range(delta - 1):
                    blank = []
                    for name in self.columns:
                        blank.append(None)
                    rows.append(blank)
            row = []
            for name in self.columns:
                field = m.get(name)
                row.append(field.value if field is not None else None)
            rows.append(row)
            last_timestamp = t

        return pd.DataFrame(data=rows, columns=self.columns)

    @property
    def columns(self) -> list:
        if self._columns is None:
            f = {}
            for r in self._record:
                f.update(r.get_values())
            self._columns = sorted(list(f.keys()))
        return self._columns

class WattPrime:
    def __init__(self, critical_power: int, watt_prime: int, integral: bool = False):
        self.critical_power = critical_power
        self.watt_prime = watt_prime
        self.watt_prime_balance = self.watt_prime
        self.total = 0
        self.count = 0
        self.I = 0
        self.elapsed_time = 0
        self.integral = integral

    def update(self, watts: int):
        if self.integral:
            return self._update_integral(watts)
        else:
            return self._update_differencial(watts)

    def _update_differencial(self, watts: int):
        if watts < self.critical_power:
            self.watt_prime_balance += (self.critical_power - watts) * (self.watt_prime - self.watt_prime_balance) / self.watt_prime
        else:
            self.watt_prime_balance += self.critical_power - watts
        return self.watt_prime_balance

    def _update_integral(self, watts: int):
        self.elapsed_time += 1
        p = 0
        e = 2.71828183
        if watts > self.critical_power:
            p = watts - self.critical_power
        elif watts < self.critical_power:
            self.total += watts
            self.count += 1
        TAU = 0.0
        if self.count > 0:
                TAU = 546.00 * math.pow(math.e, -0.01 * (self.critical_power - (self.total / self.count))
            ) + 316.0
        else:
            TAU = 546.00 * math.pow(math.e, -0.01 * self.critical_power
            ) + 316.0
        TAU = TAU
        self.I += math.pow(math.e, self.elapsed_time / TAU) * p
        self.watt_prime_balance = int(self.watt_prime - math.pow(math.e, -self.elapsed_time / TAU) * self.I)
        return self.watt_prime_balance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Input .FIT file")
    parser.add_argument("--output", type=str, default="out.mov", help="Output video clip file")
    parser.add_argument("--duration", type=int, default=None, help="video clip duration")
    parser.add_argument("--cp", type=int, default=None, help="set your Critical Power")
    parser.add_argument("--wprime", type=int, default=None, help="set your Watt Prime")
    args = parser.parse_args()

    fit = FitFile(args.input)
    df = FitDataFrame(fit).as_df()
    df = df.fillna(0)
    df['power'] = df['power'].astype(np.int)
    df['heart_rate'] = df['heart_rate'].astype(np.int)

    wp = WattPrime(critical_power=args.cp, watt_prime=args.wprime)
    df['wPrimeBal'] = df.power.rolling(window=1, min_periods=1).mean().map(lambda x: wp.update(x))
    df['w_bal'] = np.around(df['wPrimeBal'] / 1000, 1)
    def make_frame(t):
        s = math.floor(t)
        surface = gz.Surface(1280, 720)
        xy = [158, 54]
        for c in reversed(list(str(df.iloc[s]['power']))):
            power = gz.text(c, "Helvetica Neue", 83, fontweight="bold",
                            xy=xy, fill=(1, 1, 1), v_align="center", h_align="center")
            power.draw(surface)
            xy[0] -= 45

        xy = [75, 127]
        digit = 1
        for c in reversed(list(str(df.iloc[s]['w_bal']))):
            hr = gz.text(c, "Helvetica Neue", 38, fontweight="bold",
                         xy=xy, fill=(0, 0, 0), v_align="top", h_align="center")
            hr.draw(surface)
            if digit >= 0:
                xy[0] -= 15
            else:
                xy[0] -= 22
            digit -= 1

        xy = [170, 113]
        for c in reversed(list(str(df.iloc[s]['heart_rate']))):
            hr = gz.text(c, "Helvetica Neue", 38, fontweight="bold",
                         xy=xy, fill=(0, 0, 0), v_align="center", h_align="center")
            hr.draw(surface)
            xy[0] -= 22

        return surface.get_npimage(transparent=True)

    duration = len(df.index)
    if args.duration is not None:
        duration = args.duration

    background = mpy.ImageClip("base-clip.png", duration=duration)
    bg_mask = mpy.ImageClip("base-clip.png", duration=duration, ismask=True, fromalpha=True)

    data = mpy.VideoClip(lambda t: make_frame(t)[:, :, :3], duration=duration)
    data_mask = mpy.VideoClip(lambda t: make_frame(t)[:, :, 3] / 255.0, duration=duration, ismask=True)
    data = data.set_mask(data_mask)

    clip = mpy.CompositeVideoClip(clips=[background, data], size=(1280, 720), use_bgclip=True)
    clip = clip.set_mask(bg_mask)
    clip = clip.set_duration(duration)
    clip.write_videofile(args.output, codec="prores_ks", fps=1, withmask=True)


if __name__ == "__main__":
    main()

