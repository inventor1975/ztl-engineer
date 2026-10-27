"""The film's story frames: the AI pictures (video/img, made with Flux.1-dev in ComfyUI) at 1920x1080, a few with one
caption of a number and its source.

    python3 video/story.py      -> video/raw/story_<name>.png
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FRAMES = {
    "seller": None,
    "borehole": ("< 5 engineers per 10,000 people", "developing countries — UNESCO estimate"),
    "far": ("$40–150 an hour", "a freelance engineer; a written check can take a week"),
    "clinic": ("up to $20,000", "what engineering software can cost"),
    "empty": None,
    "phone": None,
    "water": None,
}


def main():
    for name, cap in FRAMES.items():
        im = Image.open(HERE / "img" / f"{name}.png").convert("RGB").resize((1920, 1097)).crop((0, 8, 1920, 1088))
        if cap:
            d = ImageDraw.Draw(im, "RGBA")
            big, small = ImageFont.truetype(BOLD, 72), ImageFont.truetype(REG, 34)
            w = max(d.textlength(cap[0], font=big), d.textlength(cap[1], font=small)) + 80
            d.rounded_rectangle((70, 820, 70 + w, 1010), radius=22, fill=(255, 255, 255, 226))
            d.text((110, 840), cap[0], font=big, fill=(59, 91, 219))
            d.text((110, 945), cap[1], font=small, fill=(60, 70, 85))
        im.save(HERE / "raw" / f"story_{name}.png")
        print(name)


if __name__ == "__main__":
    main()
