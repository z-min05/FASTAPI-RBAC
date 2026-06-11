import random
import string
import io
from PIL import Image, ImageDraw, ImageFont


def generate_captcha(length: int = 4, width: int = 120, height: int = 40) -> tuple[str, bytes]:
    """生成图片验证码，返回 (验证码文本, PNG 图片字节)"""
    chars = random.choices(string.ascii_uppercase + string.digits, k=length)
    code = "".join(chars)

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # 使用较大字体
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default(size=18)

    # 绘制验证码字符
    char_width = width // length
    for i, ch in enumerate(chars):
        x = i * char_width + random.randint(6, 12)
        y = random.randint(2, 8)
        color = (random.randint(0, 120), random.randint(0, 120), random.randint(0, 120))
        draw.text((x, y), ch, fill=color, font=font)

    # 绘制干扰线
    for _ in range(4):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        color = (random.randint(64, 200), random.randint(64, 200), random.randint(64, 200))
        draw.line((x1, y1, x2, y2), fill=color, width=1)

    # 绘制干扰点
    for _ in range(40):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        color = (random.randint(64, 200), random.randint(64, 200), random.randint(64, 200))
        draw.point((x, y), fill=color)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    return code, img_bytes
