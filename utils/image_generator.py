import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ──────────────────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────────────────
IMG_W    = 1600
COLS     = 3          # max columns
PAD      = 60         # outer padding
GAP_X    = 28         # horizontal gap between cards
GAP_Y    = 28         # vertical gap between cards
CARD_H   = 270        # fixed card height
CARD_R   = 24         # card corner radius
FONT_PATH = "assets/Vazirmatn-Bold.ttf"

# Palette
BG_TOP      = (7,  12, 28)       # very dark navy
BG_BOT      = (15, 20, 52)       # deep blue
BLOB_COLORS = [
    (56, 80, 220, 55),            # blue blob
    (120, 40, 200, 45),           # purple blob
    (30, 140, 200, 35),           # teal blob
]
CARD_FILL   = (255, 255, 255, 18) # glassmorphism card body
CARD_BORDER = (255, 255, 255, 55) # card border
CARD_GLOW   = (80, 160, 255, 90) # top glow strip
TEXT_NAME   = (100, 180, 255)     # package name
TEXT_DETAIL = (160, 190, 220)     # GB / days
TEXT_PRICE  = (255, 255, 255)     # price
DIVIDER     = (255, 255, 255, 35)

# ──────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────
def to_persian_num(text):
    en = "0123456789"
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return str(text).translate(str.maketrans(en, fa))

def load_fonts(scale=1.0):
    try:
        return {
            "name"  : ImageFont.truetype(FONT_PATH, int(48 * scale)),
            "detail": ImageFont.truetype(FONT_PATH, int(34 * scale)),
            "price" : ImageFont.truetype(FONT_PATH, int(54 * scale)),
        }
    except:
        d = ImageFont.load_default()
        return {"name": d, "detail": d, "price": d}

def text_w(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]

def draw_centered(draw, cx, cy, text, font, fill):
    w, h = text_w(draw, text, font)
    draw.text((cx - w // 2, cy - h // 2), text, font=font, fill=fill)

def truncate(draw, text, font, max_w):
    if text_w(draw, text, font)[0] <= max_w:
        return text
    while len(text) > 1:
        text = text[:-1]
        if text_w(draw, text + "…", font)[0] <= max_w:
            return text + "…"
    return text

# ──────────────────────────────────────────────────────────
#  Background helpers
# ──────────────────────────────────────────────────────────
def make_gradient_bg(W, H):
    """Vertical gradient from BG_TOP to BG_BOT."""
    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOT[0]-BG_TOP[0])*t)
        g = int(BG_TOP[1] + (BG_BOT[1]-BG_TOP[1])*t)
        b = int(BG_TOP[2] + (BG_BOT[2]-BG_TOP[2])*t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return bg

def add_blobs(base_rgb, W, H):
    """Paint a few large, blurred coloured circles for depth / 3-D feel."""
    blob_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(blob_layer)
    # positions chosen to spread nicely across different canvas heights
    blobs = [
        (int(W * 0.18), int(H * 0.25), int(W * 0.28), BLOB_COLORS[0]),
        (int(W * 0.82), int(H * 0.20), int(W * 0.25), BLOB_COLORS[1]),
        (int(W * 0.50), int(H * 0.75), int(W * 0.22), BLOB_COLORS[2]),
        (int(W * 0.85), int(H * 0.78), int(W * 0.18), BLOB_COLORS[0]),
        (int(W * 0.12), int(H * 0.75), int(W * 0.18), BLOB_COLORS[1]),
    ]
    for cx, cy, r, col in blobs:
        bdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    # heavy blur → soft glow
    blob_layer = blob_layer.filter(ImageFilter.GaussianBlur(radius=int(W * 0.06)))
    result = base_rgb.convert("RGBA")
    result = Image.alpha_composite(result, blob_layer)
    return result.convert("RGB")

# ──────────────────────────────────────────────────────────
#  Glass card
# ──────────────────────────────────────────────────────────
def draw_glass_card(canvas_rgba, draw, x, y, w, h, fonts, pkg):
    """Draw one glassmorphism card onto canvas_rgba."""
    pid, name, gb, days, price = pkg

    # ── shadow ──
    shadow = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([8, 8, w + 8, h + 8], radius=CARD_R, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    canvas_rgba.paste(shadow, (x - 4, y - 4), shadow)

    # ── card body ──
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, w - 1, h - 1], radius=CARD_R, fill=CARD_FILL)

    # border
    cd.rounded_rectangle([0, 0, w - 1, h - 1], radius=CARD_R,
                          outline=CARD_BORDER, width=2)

    # top glow strip (3-D raised effect)
    strip_h = 4
    strip = Image.new("RGBA", (w - 40, strip_h), CARD_GLOW)
    strip = strip.filter(ImageFilter.GaussianBlur(2))
    card.paste(strip, (20, 2), strip)

    canvas_rgba.paste(card, (x, y), card)

    # ── text ──
    cx = x + w // 2
    inner_w = w - 56

    # name
    name_t = truncate(draw, to_persian_num(name), fonts["name"], inner_w)
    draw_centered(draw, cx, y + int(h * 0.24), name_t, fonts["name"], TEXT_NAME)

    # divider
    dy = y + int(h * 0.42)
    div = Image.new("RGBA", (inner_w, 1), DIVIDER)
    canvas_rgba.paste(div, (x + 28, dy), div)

    # GB / days
    detail_t = truncate(draw, to_persian_num(f"{gb} گیگ  —  {days} روز"),
                        fonts["detail"], inner_w)
    draw_centered(draw, cx, y + int(h * 0.59), detail_t, fonts["detail"], TEXT_DETAIL)

    # price
    price_t = truncate(draw, to_persian_num(f"{int(price):,} تومان"),
                       fonts["price"], inner_w)
    draw_centered(draw, cx, y + int(h * 0.81), price_t, fonts["price"], TEXT_PRICE)


# ──────────────────────────────────────────────────────────
#  Main generator
# ──────────────────────────────────────────────────────────
def generate_packages_image(packages, seller_name, output_path="temp_packages.png"):
    num_pkgs = len(packages)
    if num_pkgs == 0:
        return output_path

    cols = min(COLS, num_pkgs)
    rows = math.ceil(num_pkgs / cols)

    card_w = (IMG_W - 2 * PAD - (cols - 1) * GAP_X) // cols

    # Dynamic height — expands for more rows
    H = 2 * PAD + rows * CARD_H + (rows - 1) * GAP_Y

    # ── background ──
    bg = make_gradient_bg(IMG_W, H)
    bg = add_blobs(bg, IMG_W, H)

    # ── RGBA canvas ──
    canvas = bg.convert("RGBA")
    draw   = ImageDraw.Draw(canvas)

    # Font scaling: shrink slightly when many packages to keep cards tight
    font_scale = max(0.75, 1.0 - 0.03 * max(0, rows - 2))
    fonts = load_fonts(font_scale)

    # ── cards ──
    # Vertical centering within canvas
    total_h = rows * CARD_H + (rows - 1) * GAP_Y
    start_y = (H - total_h) // 2

    for i, pkg in enumerate(packages):
        r = i // cols
        c_rtl = (cols - 1) - (i % cols)   # RTL: rightmost first

        x = PAD + c_rtl * (card_w + GAP_X)
        y = start_y + r * (CARD_H + GAP_Y)

        draw_glass_card(canvas, draw, x, y, card_w, CARD_H, fonts, pkg)

    # ── save ──
    canvas.convert("RGB").save(output_path)
    return output_path
