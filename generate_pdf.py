from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageFilter, ImageOps
import os
import time
from io import BytesIO
from ai_images import generate_story_images

def create_storybook(name, gender, story, avatar_path):
    safe_name = _sanitize_filename(name or "storybook")
    os.makedirs("static", exist_ok=True)
    output_path = os.path.join("static", f"{int(time.time())}_{safe_name}_storybook.pdf")

    page_size = (8.5 * inch, 8.5 * inch)
    c = canvas.Canvas(output_path, pagesize=page_size)

    # Fonts: use Helvetica which is built-in; register optional TTF if needed in future
    c.setTitle(f"{name}'s Storybook")

    pronoun = "he" if (gender or "").lower() == "boy" else "she"
    possessive = "his" if pronoun == "he" else "her"
    objective = "him" if pronoun == "he" else "her"

    pages = _get_story_pages(story, name, pronoun, possessive, objective)

    # Try generating 12 scene images via API; fallback to avatar-only if unavailable
    api_images = generate_story_images(avatar_path, story, name, gender)
    scene_readers = []
    if api_images and len(api_images) == 12:
        for blob in api_images:
            try:
                pil = Image.open(BytesIO(blob)).convert("RGB")
                pil = ImageOps.fit(pil, (260, 260), method=Image.Resampling.LANCZOS)
                scene_readers.append(ImageReader(pil))
            except Exception:
                scene_readers.append(None)
    else:
        avatar = _cartoonize_avatar(avatar_path, target_size=(260, 260))
        avatar_reader = ImageReader(avatar)

    margin = 72  # 1 inch
    image_x = margin
    image_y = page_size[1] - margin - 260
    text_x = margin
    text_y_top = image_y - 24
    max_width = page_size[0] - 2 * margin

    for idx, text in enumerate(pages):
        if scene_readers and idx < len(scene_readers) and scene_readers[idx] is not None:
            c.drawImage(scene_readers[idx], image_x, image_y, width=260, height=260, mask='auto')
        else:
            c.drawImage(avatar_reader, image_x, image_y, width=260, height=260, mask='auto')
        _draw_wrapped_text(c, text, text_x, text_y_top, max_width, line_height=20)
        c.showPage()

    c.save()
    return output_path


def _sanitize_filename(value):
    keep = [ch for ch in value if ch.isalnum() or ch in (' ', '-', '_')]
    value = ''.join(keep).strip().replace(' ', '_')
    return value or "file"


def _get_story_pages(story_key, name, pronoun, possessive, objective):
    key = (story_key or "").lower()
    if key == "red":
        base = [
            f"Once upon a time, there was a brave child named {name}.",
            f"{name} wore a bright red hood and loved visiting {possessive} grandmother.",
            f"One sunny morning, {pronoun} set off with a basket of treats.",
            f"Along the path, birds chirped while {name} skipped through the forest.",
            f"Suddenly, a shadow appeared between the trees— a clever wolf.",
            f"The wolf asked where {name} was going, and {pronoun} answered politely.",
            f"The wolf suggested a 'shortcut' and hurried ahead.",
            f"At grandmother's house, the wolf put on a disguise and waited.",
            f"{name} noticed something odd: what big eyes, ears, and teeth!",
            f"With quick thinking, {name} called for help and kept the wolf busy.",
            f"A friendly woodcutter arrived, and the wolf fled into the woods.",
            f"Grandmother hugged {name}, and they enjoyed the treats together."
        ]
    else:
        base = [
            f"There was a curious child named {name} who lived with {possessive} mother.",
            f"One day, {pronoun} traded a cow for a handful of magic beans.",
            f"Overnight, a giant beanstalk grew high into the clouds.",
            f"{name} climbed and found a castle where a giant lived.",
            f"Inside, {pronoun} saw treasures and a golden harp that sang.",
            f"'Fee-fi-fo-fum!' thundered the giant, and {name} hid.",
            f"{name} grabbed the harp, who whispered the way home.",
            f"The giant chased {objective} down the beanstalk.",
            f"On the ground, {name} called for an axe without losing courage.",
            f"Chop! Chop! The stalk shook as the giant neared the bottom.",
            f"With a final chop, the beanstalk fell, and the giant vanished.",
            f"{name} and {possessive} mother lived happily, wiser from the adventure."
        ]
    return base


def _cartoonize_avatar(path, target_size=(260, 260)):
    img = Image.open(path).convert("RGB")
    img = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS)
    # Simple 'cartoon' effect: edge enhance + posterize + slight smoothing
    edges = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    poster = ImageOps.posterize(edges, bits=3)
    smooth = poster.filter(ImageFilter.SMOOTH)
    return smooth


def _draw_wrapped_text(c, text, x, top_y, max_width, line_height=18):
    c.setFont("Helvetica", 16)
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        width = pdfmetrics.stringWidth(test, "Helvetica", 16)
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    y = top_y
    for line in lines:
        c.drawString(x, y, line)
        y -= line_height
