"""Assemble the demo video: cards + recorded scenes, each with its narration; the waits for the model and the stand
are sped up (the logs from rec.py say when they were), and a scene shorter than its narration holds its last frame.

    ~/venvs/video/bin/python video/make.py        -> video/out/ztl-engineer-demo.mp4
"""
import json
import pathlib
import subprocess

import imageio_ffmpeg
import soundfile as sf

HERE = pathlib.Path(__file__).resolve().parent
RAW, AUD, OUT = HERE / "raw", HERE / "audio", HERE / "out"
FF = imageio_ffmpeg.get_ffmpeg_exe()
LEAD = 0.4            # narration starts this long after its scene
TAIL = 0.8            # and the scene runs this long after the narration ends

# the wait to compress in each scene: (from event, to event, how many seconds it should last on screen)
WAITS = {"pump": ("sent", "verdict", 4.0), "published": ("sent", "verdict", 3.0), "heavy": ("sent", "verdict", 4.0),
         "muhanna": ("sent", "verdict", 3.0), "borehole": ("sent", "verdict", 4.0), "borehole2": ("sent", "verdict", 3.0)}
# the montage scenes start when the example is already in the box (the task picking is shown once, in the main case)
START = {"published": "example in", "heavy": "example in", "muhanna": "example in"}
CARDS = ("title", "problem", "options", "end")
# montage scenes are cut from the front to their narration's length: the end (the result on screen) is what stays
FIT_TO_VOICE = ("published", "heavy", "muhanna")
ORDER = ["problem", "options", "borehole", "borehole2", "published", "heavy", "muhanna", "reproduce", "end"]


def run(args):
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def dur(path):
    out = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = out.split("Duration: ")[1].split(",")[0].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def scene_video(name):
    """the recorded scene with its wait compressed -> (path, duration)"""
    src = RAW / f"{name}.webm"
    ev = {e["what"]: e["t"] for e in json.loads((RAW / f"{name}.json").read_text())["events"]}
    dst = OUT / f"v_{name}.mp4"
    if name in WAITS:
        a, b, want = WAITS[name]
        t1, t2 = ev[a] + 0.6, ev[b] - 0.3
        k = max(1.0, (t2 - t1) / want)
        t0 = max(0.0, ev[START[name]] - 0.5) if name in START else 0
        f = (f"[0:v]trim={t0}:{t1},setpts=PTS-STARTPTS[a];[0:v]trim={t1}:{t2},setpts=(PTS-STARTPTS)/{k}[b];"
             f"[0:v]trim={t2},setpts=PTS-STARTPTS[c];[a][b][c]concat=n=3:v=1:a=0,fps=30[v]")
    else:
        f = "[0:v]fps=30[v]"
    run(["-i", str(src), "-filter_complex", f, "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
         str(dst)])
    return dst, dur(dst)


def card_video(name, seconds):
    dst = OUT / f"v_{name}.mp4"
    run(["-loop", "1", "-i", str(RAW / f"card_{name}.png"), "-t", f"{seconds}", "-vf", "fps=30,format=yuv420p",
         "-c:v", "libx264", "-crf", "18", str(dst)])
    return dst, seconds


def with_voice(name, vpath, vdur):
    """lay the narration over the scene; hold the last frame if the narration is longer; fade in and out"""
    apath = AUD / f"{name}.wav"
    adur = sf.info(str(apath)).duration
    total = max(vdur, LEAD + adur + TAIL)
    pad = total - vdur
    dst = OUT / f"s_{name}.mp4"
    vf = (f"tpad=stop_mode=clone:stop_duration={pad:.3f}," if pad > 0.01 else "") + \
         f"fade=t=in:st=0:d=0.35,fade=t=out:st={total - 0.35:.3f}:d=0.35"
    af = f"adelay={int(LEAD * 1000)}:all=1,apad=whole_dur={total:.3f},afade=t=out:st={total - 0.3:.3f}:d=0.3"
    run(["-i", str(vpath), "-i", str(apath), "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]", "-map", "[v]",
         "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "160k",
         "-ar", "48000", "-t", f"{total:.3f}", str(dst)])
    return dst, total


def main():
    OUT.mkdir(exist_ok=True)
    parts, timeline, t = [], [], 0.0
    for name in ORDER:
        if name not in CARDS and not (RAW / f"{name}.json").exists():
            print(f"(skipped: {name} not recorded yet)")
            continue
        if name in CARDS:
            v, d = card_video(name, 1.0)
        else:
            v, d = scene_video(name)
            need = LEAD + sf.info(str(AUD / f"{name}.wav")).duration + TAIL + 0.3
            if name in FIT_TO_VOICE and d > need:
                cut = OUT / f"v_{name}_fit.mp4"
                run(["-ss", f"{d - need:.3f}", "-i", str(v), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                     str(cut)])
                v, d = cut, dur(cut)
        s, total = with_voice(name, v, d)
        parts.append(s)
        timeline.append((name, round(t, 1), round(total, 1)))
        t += total
    lst = OUT / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    final = OUT / "ztl-engineer-demo.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final)])
    for name, start, length in timeline:
        print(f"{start:6.1f}s  {name:10s} {length:5.1f}s")
    print(f"total {t:.1f}s -> {final}")


if __name__ == "__main__":
    main()
