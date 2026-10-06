"""Build the original college student pixel sprite and animation metadata."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parents[1] / "app/ui/static/characters"
COLORS = {
    "outline": "#343947", "hair": "#433e48", "hair_light": "#67515a",
    "skin": "#cf946d", "skin_light": "#edb68a", "skin_shadow": "#ad715c",
    "green": "#49796a", "green_light": "#6a9980", "green_dark": "#34584f",
    "cream": "#e5dbb9", "cream_shadow": "#b8b59b",
    "jeans": "#4e5874", "jeans_dark": "#394158",
    "shoe": "#eae4cc", "sole": "#969c9b",
    "bag": "#b16d5b", "bag_light": "#d19171", "bag_dark": "#7f4c48",
}


CHARACTERS = [
    {"id": "rowan", "name": "Rowan", "file": "college-student", "style": "tousled", "colors": {}},
    {"id": "amara", "name": "Amara", "file": "amara", "style": "curls", "colors": {
        "skin": "#89563f", "skin_light": "#ac7451", "skin_shadow": "#694031",
        "hair": "#302c37", "hair_light": "#55404a",
        "green": "#a95c61", "green_light": "#cf8180", "green_dark": "#784448",
        "bag": "#648b83", "bag_light": "#8fb1a0", "bag_dark": "#425d5c"}},
    {"id": "mei", "name": "Mei", "file": "mei", "style": "bob", "colors": {
        "skin": "#d6a57c", "skin_light": "#f1cba0", "skin_shadow": "#b68267",
        "hair": "#292e3b", "hair_light": "#495264",
        "green": "#557eaa", "green_light": "#7fa5c3", "green_dark": "#3e587c",
        "bag": "#b78a50", "bag_light": "#dbc080", "bag_dark": "#866640"}},
    {"id": "arjun", "name": "Arjun", "file": "arjun", "style": "waves", "colors": {
        "skin": "#b37a50", "skin_light": "#cc9867", "skin_shadow": "#8c5b43",
        "hair": "#302e38", "hair_light": "#54424a",
        "green": "#b08a4f", "green_light": "#d3af69", "green_dark": "#826539",
        "bag": "#646c97", "bag_light": "#969ec0", "bag_dark": "#484c70"}},
]


def frame(direction, index, character=None):
    character = character or CHARACTERS[0]
    colors = {**COLORS, **character["colors"]}
    image = Image.new("RGBA", (32, 32))
    draw = ImageDraw.Draw(image)
    walking = index >= 4
    step = (0, 1, 0, -1)[index - 4] if walking else 0
    bob = -1 if (walking and step == 0) or (not walking and index == 1) else 0
    blink = not walking and index == 3

    def box(x, y, w, h, color):
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=colors.get(color, color))

    def hairstyle(side=False):
        style = character["style"]
        if style == "curls":
            for x, y in [(10, 3), (13, 1), (17, 1), (20, 3), (9, 6)]:
                box(x, y + bob, 4, 4, "hair")
                box(x + 1, y + bob, 2, 1, "hair_light")
            if not side:
                box(21, 7 + bob, 3, 3, "hair")
        elif style == "bob":
            box(9, 5 + bob, 3, 9, "hair")
            box(10, 12 + bob, 3, 3, "hair")
            if not side:
                box(21, 5 + bob, 3, 10, "hair")
                box(19, 13 + bob, 3, 2, "hair")
            box(11, 3 + bob, 10, 4, "hair")
            box(12, 3 + bob, 7, 1, "hair_light")
            box(10, 8 + bob, 1, 4, "hair_light")
        elif style == "waves":
            box(11, 2 + bob, 11, 4, "hair")
            box(13, 1 + bob, 7, 3, "hair")
            box(11, 3 + bob, 5, 1, "hair_light")
            box(16, 2 + bob, 4, 1, "hair_light")
            box(18, 5 + bob, 4, 3, "hair")

    # Fixed floor contact keeps the idle and walk cycles free of anchor drift.
    draw.ellipse((8, 28, 24, 30), fill=(44, 49, 54, 35))
    if direction in ("down", "up"):
        for x, stride in ((11, step), (18, -step)):
            box(x, 22, 4, 6 + stride, "outline")
            box(x + 1, 22, 2, 4 + stride, "jeans")
            box(x - 1, 27 + stride, 5, 2, "shoe")
            box(x - 1, 29 + stride, 5, 1, "sole")
        # Backpack straps are visible from the front; full bag faces the camera from behind.
        box(10, 13 + bob, 13, 10, "outline")
        box(11, 14 + bob, 11, 8, "green")
        box(12, 14 + bob, 3, 7, "green_light")
        box(11, 22 + bob, 11, 1, "cream_shadow")
        for x, swing in ((7, -step), (23, step)):
            box(x, 15 + bob + swing, 3, 7, "outline")
            box(x, 16 + bob + swing, 3, 4, "cream")
            box(x, 20 + bob + swing, 3, 2, "skin_light")
        if direction == "down":
            box(15, 14 + bob, 3, 8, "cream")
            box(16, 15 + bob, 1, 7, "green_dark")
            box(11, 14 + bob, 1, 7, "bag_dark")
            box(21, 14 + bob, 1, 7, "bag_dark")
            box(19, 16 + bob, 2, 2, "cream")
        else:
            box(11, 14 + bob, 11, 10, "bag_dark")
            box(12, 15 + bob, 9, 8, "bag")
            box(13, 15 + bob, 7, 2, "bag_light")
            box(13, 20 + bob, 7, 3, "bag_dark")
            box(14, 20 + bob, 5, 2, "bag_light")
            box(15, 14 + bob, 3, 1, "cream_shadow")
        # Face and tousled hair.
        box(11, 4 + bob, 11, 10, "outline")
        box(10, 7 + bob, 13, 5, "skin")
        box(12, 6 + bob, 9, 7, "skin_light")
        box(13, 13 + bob, 7, 1, "skin_shadow")
        box(11, 2 + bob, 10, 3, "hair")
        box(9, 4 + bob, 14, 4, "hair")
        box(10, 3 + bob, 3, 3, "hair_light")
        box(15, 2 + bob, 4, 2, "hair_light")
        box(9, 7 + bob, 3, 3, "hair")
        box(21, 6 + bob, 2, 4, "hair")
        if direction == "down":
            box(12, 6 + bob, 3, 2, "hair")
            box(16, 6 + bob, 3, 1, "hair")
            box(13, 9 + bob, 1 if not blink else 2, 2 if not blink else 1, "outline")
            box(19, 9 + bob, 1 if not blink else 2, 2 if not blink else 1, "outline")
            box(16, 12 + bob, 2, 1, "skin_shadow")
        else:
            box(10, 6 + bob, 13, 6, "hair")
            box(12, 10 + bob, 9, 3, "hair")
            box(12, 7 + bob, 4, 1, "hair_light")
            box(19, 8 + bob, 2, 2, "hair_light")
        hairstyle()
    else:
        # Side profile is drawn facing right, then mirrored for the left cycle.
        for x, stride, color in ((13 - step * 2, -step, "jeans_dark"), (17 + step * 2, step, "jeans")):
            box(x, 22, 4, 6 + stride, "outline")
            box(x + 1, 23, 2, 4 + stride, color)
            box(x, 27 + stride, 6, 2, "shoe")
            box(x, 29 + stride, 6, 1, "sole")
        box(12, 13 + bob, 10, 11, "outline")
        box(13, 14 + bob, 8, 9, "green")
        box(19, 14 + bob, 2, 8, "green_light")
        box(9, 14 + bob, 5, 9, "bag_dark")
        box(9, 15 + bob, 4, 7, "bag")
        box(9, 16 + bob, 2, 3, "bag_light")
        box(14 + step, 15 + bob, 4, 7, "outline")
        box(15 + step, 15 + bob, 3, 5, "cream")
        box(15 + step, 20 + bob, 3, 3, "skin_light")
        box(12, 4 + bob, 10, 10, "outline")
        box(15, 6 + bob, 7, 7, "skin_light")
        box(21, 9 + bob, 3, 2, "skin_light")
        box(19, 13 + bob, 3, 1, "skin_shadow")
        box(11, 2 + bob, 9, 3, "hair")
        box(10, 4 + bob, 13, 4, "hair")
        box(11, 7 + bob, 5, 5, "hair")
        box(12, 3 + bob, 4, 2, "hair_light")
        box(10, 6 + bob, 3, 3, "hair_light")
        box(15, 8 + bob, 2, 3, "skin")
        box(21, 8 + bob, 1 if not blink else 2, 2 if not blink else 1, "outline")
        hairstyle(side=True)
        if direction == "left":
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return image


def build(character):
    filename = character["file"]
    directions = ["down", "left", "right", "up"]
    sheet = Image.new("RGBA", (256, 128))
    metadata = {"image": filename + ".png", "frameWidth": 32, "frameHeight": 32,
                "anchor": {"x": 16, "y": 30}, "directions": directions,
                "idle": {"columns": [0, 1, 2, 3], "durationsMs": [1000, 350, 1300, 130]},
                "walk": {"columns": [4, 5, 6, 7], "durationsMs": [140, 140, 140, 140]}}
    for row, direction in enumerate(directions):
        for column in range(8):
            sheet.alpha_composite(frame(direction, column, character), (column * 32, row * 32))
    sheet.save(OUTPUT / (filename + ".png"))
    (OUTPUT / (filename + ".json")).write_text(json.dumps(metadata, indent=2) + "\n")
    # A shareable preview: four simultaneous walking directions at integer scale.
    frames = []
    for column in range(4, 8):
        preview = Image.new("RGBA", (160, 48), "#e8eeea")
        for i, direction in enumerate(directions):
            preview.alpha_composite(frame(direction, column, character), (i * 40 + 4, 8))
        frames.append(preview.convert("RGB").resize((640, 192), Image.Resampling.NEAREST))
    frames[0].save(OUTPUT / (filename + "-walk.gif"), save_all=True,
                   append_images=frames[1:], duration=140, loop=0, disposal=2)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for character in CHARACTERS:
        build(character)
    catalog = [{key: c[key] for key in ("id", "name", "file")} for c in CHARACTERS]
    (OUTPUT / "catalog.js").write_text("window.StudentCharacters = " + json.dumps(catalog, indent=2) + ";\n")
    previews = []
    for index in range(4, 8):
        image = Image.new("RGBA", (160, 48), "#e8eeea")
        for column, character in enumerate(CHARACTERS):
            image.alpha_composite(frame("down", index, character), (column * 40 + 4, 8))
        previews.append(image.convert("RGB").resize((640, 192), Image.Resampling.NEAREST))
    previews[0].save(OUTPUT / "classmates.gif", save_all=True, append_images=previews[1:],
                     duration=140, loop=0, disposal=2)
    print("Built four students, 128 frames, metadata, and animation previews.")


if __name__ == "__main__":
    main()
