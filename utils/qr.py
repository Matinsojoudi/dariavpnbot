import os
import re
import qrcode
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display


def link_to_qrcode(link, output_file="qrcode.png"):
    """Generate a QR code image from a link."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=0,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_file)


def _detect_white_qr_slot(bg_img, brightness=245, min_size=200):
    """Detect the white square placeholder in a template image."""
    rgb = bg_img.convert("RGB")
    w, h = rgb.size
    pixels = rgb.load()

    best = None
    for x_start, x_end in ((0, w // 2), (w // 2, w)):
        min_x, min_y, max_x, max_y = x_end, h, x_start, 0
        found = False
        for y in range(h):
            for x in range(x_start, x_end):
                r, g, b = pixels[x, y]
                if r > brightness and g > brightness and b > brightness:
                    found = True
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        if not found:
            continue

        bw = max_x - min_x + 1
        bh = max_y - min_y + 1
        size = min(bw, bh)
        if size < min_size:
            continue

        squareness = size / max(bw, bh)
        score = size * squareness
        sq_left = min_x + (bw - size) // 2
        sq_top = min_y + (bh - size) // 2
        if best is None or score > best[0]:
            best = (score, sq_left, sq_top, size)

    if best is None:
        return None
    return best[1], best[2], best[3]


def _paste_qr_on_bg(bg, qr, left, top, size, margin_ratio=0.038):
    """Resize QR and paste it centered inside a square slot."""
    margin = max(14, int(size * margin_ratio))
    inner = size - 2 * margin
    if inner < 50:
        inner = size
        margin = 0
    qr_resized = qr.resize((inner, inner), Image.LANCZOS)
    bg.paste(qr_resized, (left + margin, top + margin), qr_resized)


_FALLBACK_SLOTS = {
    "sub_link": (1270, 290, 582),
    "invite_link": (791, 248, 626),
}


def draw_premium_subscription_card(qr_path, output_path, service_name, volume_gb, duration_days):
    """Generate a sleek, modern subscription card with dynamic details using native Pillow RTL layout."""
    width, height = 1000, 550
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    
    # 1. Slate-Indigo Diagonal Gradient Background
    for y in range(height):
        for x in range(width):
            factor = (x + y) / (width + height)
            r = int(15 + (30 - 15) * factor)
            g = int(23 + (27 - 23) * factor)
            b = int(42 + (75 - 42) * factor)
            img.putpixel((x, y), (r, g, b, 255))
            
    # Decorative Neon/Cyan/Indigo Glow Polygons
    draw.polygon([(800, 0), (1000, 0), (1000, 200)], fill=(99, 102, 241, 18))
    draw.polygon([(0, 350), (0, 550), (200, 550)], fill=(6, 182, 212, 12))
    
    # Load fonts
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font_path = os.path.join(base_dir, "assets", "Vazirmatn-Bold.ttf")
    try:
        title_font = ImageFont.truetype(font_path, 40)
        label_font = ImageFont.truetype(font_path, 28)
        value_font = ImageFont.truetype(font_path, 30)
    except IOError:
        title_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        value_font = ImageFont.load_default()
        
    # Draw soft-rounded container for QR code
    qr_box_left = 75
    qr_box_top = 100
    qr_box_size = 350
    draw.rounded_rectangle(
        [qr_box_left, qr_box_top, qr_box_left + qr_box_size, qr_box_top + qr_box_size],
        radius=24,
        fill=(255, 255, 255, 255)
    )
    
    # Paste QR Code
    if os.path.exists(qr_path):
        qr_img = Image.open(qr_path).convert("RGBA")
        padding = 24
        qr_resized = qr_img.resize((qr_box_size - 2 * padding, qr_box_size - 2 * padding), Image.Resampling.LANCZOS)
        img.paste(qr_resized, (qr_box_left + padding, qr_box_top + padding), qr_resized)
        
    # Vertical divider line
    draw.line([(500, 80), (500, 470)], fill=(255, 255, 255, 20), width=3)
    
    # Right Side Content Area
    right_x = 920
    
    # Header Title & Subtitle
    draw.text((550, 80), "KING VPN STORE", fill=(6, 182, 212), font=title_font)
    draw.text((right_x, 140), "کارت اشتراک سرویس شما", fill=(255, 255, 255), font=value_font, direction="rtl", anchor="rt")
    
    # Detail rows
    y_name = 220
    y_vol = 300
    y_days = 380
    
    # Row 1: Username
    draw.text((right_x, y_name), "👤 نام کاربری:", fill=(156, 163, 175), font=label_font, direction="rtl", anchor="rt")
    draw.text((550, y_name), service_name, fill=(255, 255, 255), font=value_font)
    
    # Row 2: Volume
    draw.text((right_x, y_vol), "📊 حجم سرویس:", fill=(156, 163, 175), font=label_font, direction="rtl", anchor="rt")
    draw.text((550, y_vol), f"{volume_gb} GB", fill=(255, 255, 255), font=value_font)
    
    # Row 3: Duration
    draw.text((right_x, y_days), "⏳ مدت اعتبار:", fill=(156, 163, 175), font=label_font, direction="rtl", anchor="rt")
    draw.text((550, y_days), f"{duration_days} روز", fill=(255, 255, 255), font=value_font)
    
    # Footer Decoration
    draw.rounded_rectangle(
        [550, 440, 930, 490],
        radius=12,
        fill=(16, 185, 129, 20),
        outline=(16, 185, 129, 100),
        width=2
    )
    draw.text((910, 447), "وضعیت سرویس: فعال", fill=(52, 211, 153), font=label_font, direction="rtl", anchor="rt")
    
    # Save Output
    img.save(output_path, "PNG")


def place_qr_on_template(qr_path, bg_path, output_path, photo_type, sub_link=None):
    """Place a QR code onto a template image, or generate a premium card dynamically if sub_link is provided."""
    if photo_type == "sub_link" and sub_link:
        try:
            # Extract UUID from sub_link
            uuid_match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', sub_link)
            if uuid_match:
                user_uuid = uuid_match.group(0)
                # Fetch user details
                from hiddify.client import HiddifyClient
                client = HiddifyClient()
                client.reload_config()
                user = client.get_user(user_uuid)
                
                if user and user.get("name"):
                    name = user.get("name")
                    vol = f"{user.get('usage_limit_GB'):g}"
                    days = f"{user.get('package_days')}"
                    
                    draw_premium_subscription_card(
                        qr_path=qr_path,
                        output_path=output_path,
                        service_name=name,
                        volume_gb=vol,
                        duration_days=days
                    )
                    return
        except Exception as e:
            print("Error generating dynamic premium subscription card:", e)
            
    # Fallback to standard static template overlay
    try:
        bg = Image.open(bg_path).convert("RGBA")
        qr = Image.open(qr_path).convert("RGBA")

        slot = _detect_white_qr_slot(bg)
        if slot is None:
            slot = _FALLBACK_SLOTS.get(photo_type)
        if slot is None:
            bg.save(output_path)
            return

        left, top, size = slot
        margin_ratio = 0.044 if photo_type == "invite_link" else 0.038
        _paste_qr_on_bg(bg, qr, left, top, size, margin_ratio=margin_ratio)
        bg.save(output_path)
    except Exception as e:
        print("Fallback static template overlay failed:", e)
        # If fallback also fails, save the raw QR code as final output to prevent crash
        if os.path.exists(qr_path):
            Image.open(qr_path).save(output_path)
