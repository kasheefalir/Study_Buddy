"""Original fixed-position professor sprite; excluded from the student catalog."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "app/ui/static/characters"


def frame(index):
    image = Image.new("RGBA", (32, 32))
    draw = ImageDraw.Draw(image)
    bob = -1 if index == 1 else 0

    def box(x, y, w, h, color):
        draw.rectangle((x, y + bob, x + w - 1, y + bob + h - 1), fill=color)

    draw.ellipse((6, 28, 26, 31), fill=(45, 49, 55, 40))
    # Shoes stay planted while the upper body breathes.
    draw.rectangle((10, 28, 14, 30), fill="#3e4355")
    draw.rectangle((19, 28, 23, 30), fill="#3e4355")
    box(9, 15, 15, 14, "#778591")
    box(10, 16, 13, 12, "#f4f4df")
    box(10, 23, 3, 5, "#d2dcd6")
    box(22, 20, 2, 8, "#b8cac8")
    box(15, 16, 4, 12, "#4b6471")
    box(16, 16, 2, 7, "#80a9a4")
    box(16, 18, 2, 2, "#bc7059")
    box(12, 16, 3, 3, "#ffffff")
    box(19, 16, 3, 3, "#ffffff")
    box(13, 19, 2, 2, "#c6d4cc")
    box(19, 19, 2, 2, "#c6d4cc")
    box(20, 22, 3, 2, "#a0b7b4")
    box(20, 20, 1, 3, "#bb6664")
    box(22, 20, 1, 3, "#5f8ca1")
    box(6, 17, 4, 8, "#d2dcd6")
    box(7, 17, 3, 6, "#f4f4df")
    box(7, 24, 3, 2, "#ddb18a")
    box(24, 17, 3, 6, "#f4f4df")
    box(24, 22, 3, 3, "#ddb18a")
    # Tiny green sample flask.
    box(26, 19, 2, 3, "#aec5c6")
    box(25, 22, 4, 3, "#537c7a")
    box(26, 22, 2, 2, "#9ad889")
    # Silver tufts surrounding a receding hairline.
    box(8, 4, 17, 11, "#9aafba")
    for x, y, w, h in [(4, 3, 5, 3), (6, 1, 3, 5), (3, 7, 7, 3),
                        (5, 11, 5, 3), (23, 2, 3, 5), (25, 4, 4, 3),
                        (24, 9, 6, 3), (23, 12, 4, 3)]:
        box(x, y, w, h, "#e8eee3")
    box(10, 4, 13, 10, "#dfb08a")
    box(12, 3, 9, 4, "#efc7a0")
    box(11, 11, 12, 4, "#efc7a0")
    box(13, 14, 8, 1, "#b3846c")
    # Goggles, asymmetric reflections, and eyebrows.
    box(8, 7, 8, 6, "#47596b")
    box(18, 7, 8, 6, "#47596b")
    box(16, 8, 2, 2, "#47596b")
    box(10, 8, 5, 3, "#a7d8d5")
    box(19, 8, 5, 3, "#a7d8d5")
    box(10, 8, 2, 1, "#f4fff1")
    box(19, 8, 2, 1, "#f4fff1")
    box(12, 9, 2, 1 if index == 3 else 2, "#354754")
    box(21, 9, 2, 1 if index == 3 else 2, "#354754")
    box(9, 5, 6, 1, "#f7f9e9")
    box(20, 5 if index != 2 else 4, 5, 1, "#f7f9e9")
    box(16, 11, 2, 2, "#c28c70")
    box(12, 13, 4, 2, "#f7f9e9")
    box(18, 13, 4, 2, "#f7f9e9")
    return image


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", (128, 32))
    frames = []
    for index in range(4):
        sprite = frame(index)
        sheet.alpha_composite(sprite, (index * 32, 0))
        preview = Image.new("RGBA", (48, 40), "#e8eeea")
        preview.alpha_composite(sprite, (8, 4))
        frames.append(preview.convert("RGB").resize((240, 200), Image.Resampling.NEAREST))
    sheet.save(OUT / "professor.png")
    frames[0].save(OUT / "professor-idle.gif", save_all=True, append_images=frames[1:],
                   duration=[1000, 350, 1300, 130], loop=0, disposal=2)
    print("Built Professor's four-frame idle sprite and preview.")
