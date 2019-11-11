import argparse
from fitparse import FitFile
import moviepy.editor as mpy
import numpy as np
import pandas as pd
import math
import gizeh as gz
import os


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


def add_alpha_channel(path):
    from moviepy.tools import subprocess_call
    from moviepy.config import get_setting

    work = os.path.join(os.path.dirname(path), ".{}".format(os.path.basename(path)))
    cmd = [
        get_setting("FFMPEG_BINARY"),
        "-y", "-i", path, "-loop", "1",
        "-i", "base-clip.png",
        "-filter_complex", "[1:v]alphaextract[alf];[0:v][alf]alphamerge",
        "-c:v", "qtrle", "-an",
        work]
    try:
        subprocess_call(cmd)
    except IOError as e:
        print(e)
    finally:
        if os.path.exists(work):
            os.rename(work, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Input .FIT file")
    parser.add_argument("--output", type=str, default="out.mov", help="Output video clip file")

    args = parser.parse_args()

    fit = FitFile(args.input)
    df = FitDataFrame(fit).as_df()

    def make_frame(t):
        s = math.floor(t)
        surface = gz.Surface(1280, 720, bg_color=(0, 0, 0, 0))
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

    bg_mask = mpy.ImageClip("base-clip.png", duration=duration, ismask=True)
    background = mpy.ImageClip("base-clip.png", duration=duration)
    mask = mpy.VideoClip(lambda t: make_frame(t)[:, :, 3] / 255.0, duration=duration, ismask=True)
    hr_power = mpy.VideoClip(lambda t: make_frame(t)[:, :, :3], duration=duration).set_mask(mask)
    clip = mpy.CompositeVideoClip(clips=[background, hr_power],
                                  size=(1280, 720)).set_mask(mask).set_duration(duration)
    clip.write_videofile(args.output, codec="prores_ks", fps=1)
    # TODO: alpha channelを保持して出力できないので、ffmpegでalpha channelを追加する
    # https://github.com/Zulko/moviepy/pull/679
    add_alpha_channel(args.output)


if __name__ == "__main__":
    main()

