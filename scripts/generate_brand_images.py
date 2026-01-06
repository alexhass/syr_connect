import os
from PIL import Image

# Path to source logo
SOURCE_PATH = r"syr_logo_cmyk.original.png"
TARGET_DIR = r"..\\custom_components\\syr_connect"

# Output file definitions: (filename, size, square, dark)
FILES = [
    ("icon.png", (256, 256), True, False),
    ("icon@2x.png", (512, 512), True, False),
    ("logo.png", (256, 128), False, False),
    ("logo@2x.png", (512, 256), False, False),
    # ("dark_icon.png", (256, 256), True, True),
    # ("dark_icon@2x.png", (512, 512), True, True),
    # ("dark_logo.png", (256, 128), False, True),
    # ("dark_logo@2x.png", (512, 256), False, True),
]

def process_image(src, dest, size, square, dark):
    img = Image.open(src).convert("RGBA")
    # Trim whitespace
    bbox = img.getbbox()
    img = img.crop(bbox)
    # Resize and pad if needed
    if square:
        max_side = max(size)
        new_img = Image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        offset = ((max_side - img.width) // 2, (max_side - img.height) // 2)
        new_img.paste(img, offset)
        img = new_img.resize(size, Image.LANCZOS)
    else:
        img = img.resize(size, Image.LANCZOS)
    # Optionally darken for dark variants
    if dark:
        # Simple darken: multiply alpha, or overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 60))
        img = Image.alpha_composite(img, overlay)
    img.save(dest, format="PNG", optimize=True)

if __name__ == "__main__":
    for fname, size, square, dark in FILES:
        out_path = os.path.join(TARGET_DIR, fname)
        process_image(SOURCE_PATH, out_path, size, square, dark)
    print("All brand images generated in scripts/")
