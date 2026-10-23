from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

SIZE = 1024
BG = "#121315"
BORDER = "#3B3C40"
BRASS = "#C2A878"
FONT = Path(r"C:\Windows\Fonts\seguisb.ttf")


def build_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = 24
    radius = 214
    draw.rounded_rectangle(
        (inset, inset, SIZE - inset, SIZE - inset),
        radius=radius,
        fill=BG,
        outline=BORDER,
        width=12,
    )
    draw.rounded_rectangle(
        (inset + 20, inset + 20, SIZE - inset - 20, SIZE - inset - 20),
        radius=radius - 20,
        outline="#242529",
        width=3,
    )

    font = ImageFont.truetype(str(FONT), 590)
    left, top, right, bottom = draw.textbbox((0, 0), "P", font=font)
    x = (SIZE - (right - left)) / 2 - left
    y = (SIZE - (bottom - top)) / 2 - top - 18
    draw.text((x, y), "P", font=font, fill=BRASS)
    return image


def main() -> None:
    icon = build_icon()
    icon.save(ASSETS / "parsy.png")
    icon.save(
        ASSETS / "parsy.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Wrote {ASSETS / 'parsy.png'}")
    print(f"Wrote {ASSETS / 'parsy.ico'}")


if __name__ == "__main__":
    main()
