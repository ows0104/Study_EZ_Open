"""선택한 ImageGen B 시안을 정확한 스토어용 래스터 자산으로 만든다."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
EXTENSION = HERE.parent
WEB_PUBLIC = EXTENSION.parent / "web" / "public"
SOURCE = HERE / "icon-source.png"


def latin_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size=size)


def centered_tracking_text(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.FreeTypeFont, tracking: int) -> None:
    widths = [draw.textlength(letter, font=font) for letter in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (1024 - total) / 2
    for letter, width in zip(text, widths, strict=False):
        draw.text((round(x), y), letter, font=font, fill="#172554", stroke_width=0)
        x += width + tracking


def build_icon() -> Image.Image:
    """B 시안의 STUDY/EZ 타이포를 글자 오류·가짜 투명 배경 없이 다시 그린다."""
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((68, 68, 956, 956), radius=190, fill="#F8F9FC", outline="#E4E8F2", width=5)

    centered_tracking_text(draw, "STUDY", 222, latin_font(132), tracking=18)
    ez_font = latin_font(430)
    ez_box = draw.textbbox((0, 0), "EZ", font=ez_font)
    ez_width = ez_box[2] - ez_box[0]
    draw.text(((1024 - ez_width) / 2, 352), "EZ", font=ez_font, fill="#172554")
    draw.rounded_rectangle((244, 824, 780, 862), radius=19, fill="#3E63DD")

    canvas.save(SOURCE, optimize=True)
    return canvas


def build_icons(icon: Image.Image) -> None:
    target = EXTENSION / "icons"
    target.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 128):
        icon.resize((size, size), Image.Resampling.LANCZOS).save(target / f"icon-{size}.png", optimize=True)


def build_web_icons(icon: Image.Image) -> None:
    """같은 원본으로 웹 탭·바로가기·설치 아이콘을 만든다."""
    WEB_PUBLIC.mkdir(parents=True, exist_ok=True)
    targets = {
        "favicon-32.png": 32,
        "apple-touch-icon.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
    }
    for filename, size in targets.items():
        icon.resize((size, size), Image.Resampling.LANCZOS).save(WEB_PUBLIC / filename, optimize=True)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = "malgunbd.ttf" if bold else "malgun.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / filename), size=size)


def build_promo(icon: Image.Image) -> None:
    promo = Image.new("RGB", (440, 280), "#F4F6FF")
    draw = ImageDraw.Draw(promo)
    draw.ellipse((-72, 150, 128, 350), fill="#E3E9FF")
    draw.ellipse((330, -88, 510, 92), fill="#E8ECFF")
    draw.rounded_rectangle((24, 24, 416, 256), radius=28, fill="#FFFFFF", outline="#DCE3FA", width=2)

    mark = icon.resize((126, 126), Image.Resampling.LANCZOS)
    promo.paste(mark, (42, 77), mark)
    draw.text((188, 86), "Study EZ", font=font(36, bold=True), fill="#172554")
    draw.text((190, 138), "예습 브리지", font=font(23, bold=True), fill="#3E63DD")
    draw.text((190, 178), "강의 자료에서 AI 예습까지", font=font(14), fill="#667085")
    promo.save(HERE / "small-promo-440x280.png", optimize=True)


def build_store_screenshot() -> None:
    raw_path = HERE / "live-calendar-panel-raw.png"
    if not raw_path.exists():
        return
    raw = Image.open(raw_path).convert("RGB")
    draw = ImageDraw.Draw(raw)
    # 운영 계정 이메일은 기능과 무관하므로 스토어 공개 이미지에서 가린다.
    draw.rectangle((1215, 16, 1355, 42), fill="#FAFAFC")
    draw.text((1230, 23), "Study EZ 사용자", font=font(11), fill="#7A7F88")

    scaled = raw.resize((1280, 680), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1280, 800), "#F4F6FF")
    canvas.paste(scaled, (0, 60))
    canvas.save(HERE / "screenshot-calendar-1280x800.png", optimize=True)


def update_existing_screenshot_brand() -> None:
    path = HERE / "screenshot-calendar-1280x800.png"
    if not path.exists():
        return
    screenshot = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((1074, 73, 1196, 96), fill="#FAFAFC")
    draw.text((1084, 78), "Study EZ 사용자", font=font(10), fill="#7A7F88")
    screenshot.save(path, optimize=True)


if __name__ == "__main__":
    selected = build_icon()
    build_icons(selected)
    build_web_icons(selected)
    build_promo(selected)
    build_store_screenshot()
    update_existing_screenshot_brand()
    print(f"icons + {HERE / 'small-promo-440x280.png'}")
