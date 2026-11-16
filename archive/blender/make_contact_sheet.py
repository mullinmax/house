"""Labeled contact sheet of rendered stills.  python make_contact_sheet.py renders/v2_realism out.jpg"""
import glob, os, sys
from PIL import Image, ImageDraw, ImageFont

src = sys.argv[1] if len(sys.argv) > 1 else "renders/v2_realism"
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, "contact_sheet.jpg")
pick = ["stills/exterior_southwest", "stills/exterior_southeast", "stills/exterior_northeast", "stills/interior_living_sofa",
        "stills/interior_kitchen", "stills/interior_dining_kitchen", "stills/interior_pantry_fridge", "stills/interior_bed1",
        "stills/interior_barn_door", "dollhouse/dollhouse_southwest", "dollhouse/dollhouse_kitchen_closeup", "dollhouse/dollhouse_plan_topdown"]
fs = [os.path.join(src, p + ".png") for p in pick if os.path.exists(os.path.join(src, p + ".png"))]
W, H, cols, lab = 640, 360, 3, 26
rows = (len(fs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * W, rows * (H + lab)), "#F5F6F2")
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("arial.ttf", 16)
except Exception:
    font = ImageFont.load_default()
for i, f in enumerate(fs):
    x, y = (i % cols) * W, (i // cols) * (H + lab)
    sheet.paste(Image.open(f).convert("RGB").resize((W, H), Image.LANCZOS), (x, y))
    d.text((x + 8, y + H + 4), os.path.splitext(os.path.basename(f))[0].replace("_", " "), fill="#23271F", font=font)
sheet.save(out, quality=86)
print("wrote", out, len(fs), "images")
