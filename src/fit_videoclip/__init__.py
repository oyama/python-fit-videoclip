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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Input .FIT file")
    parser.add_argument("--output", type=str, default="out.mov", help="Output video clip file")

    args = parser.parse_args()

    fit = FitFile(args.input)
    df = FitDataFrame(fit).as_df()
    df = df.fillna(0)
    df['power'] = df['power'].astype(np.int)
    df['heart_rate'] = df['heart_rate'].astype(np.int)
    def make_frame(t):
        s = math.floor(t)
        surface = gz.Surface(1280, 720)
        xy = [158, 54]
        for c in reversed(list(str(df.iloc[s]['power']))):
            power = gz.text(c, "Helvetica Neue", 83, fontweight="bold",
                            xy=xy, fill=(1, 1, 1), v_align="center", h_align="center")
            power.draw(surface)
            xy[0] -= 45
        xy = [170, 115]
        for c in reversed(list(str(df.iloc[s]['heart_rate']))):
            hr = gz.text(c, "Helvetica Neue", 38, fontweight="bold",
                         xy=xy, fill=(0, 0, 0), v_align="center", h_align="center")
            hr.draw(surface)
            xy[0] -= 22
        return surface.get_npimage(transparent=True)

    duration = len(df.index)
    bg_mask = mpy.ImageClip("base-clip.png", duration=duration, ismask=True, fromalpha=True)
    background = mpy.ImageClip("base-clip.png", duration=duration)
    background.set_mask(bg_mask)

    data_mask = mpy.VideoClip(lambda t: make_frame(t)[:, :, 3] / 255.0, duration=duration, ismask=True)
    data = mpy.VideoClip(lambda t: make_frame(t)[:, :, :3], duration=duration)
    data = data.set_mask(data_mask)

    clip_mask = bg_mask.fx(vfx.mask_or, data_mask)
    clip = mpy.CompositeVideoClip(clips=[background, data],
                                  size=(1280, 720)).set_mask(clip_mask).set_duration(duration)
    clip.write_videofile(args.output, codec="prores_ks", fps=1, withmask=True)


if __name__ == "__main__":
    main()

