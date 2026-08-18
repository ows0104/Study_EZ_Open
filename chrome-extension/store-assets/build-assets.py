"""ImageGen 원본을 실제 투명 아이콘과 스토어 프로모션 이미지로 정리한다."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
EXTENSION = HERE.parent
RAW = HERE / "icon-source-raw.png"
SOURCE = HERE / "icon-source.png"


def clean_icon() -> Image.Image:
    """원본에 구워진 밝은 체크무늬를 색상 채도 마스크로 제거한다."""
    original = Image.open(RAW).convert("RGB")
    pixels = original.load()
    alpha = Image.new("L", original.size)
    mask = alpha.load()

    for y in range(original.height):
        for x in range(original.width):
            red, green, blue = pixels[x, y]
            chroma = max(red, green, blue) - min(red, green, blue)
            # 배경은 거의 무채색이고 심볼은 파란색이다. 경계의 안티앨리어싱은
            # 18~62 사이를 부드럽게 남긴다.
            value = max(0, min(255, round((chroma - 18) * 255 / 44)))
            mask[x, y] = value

    bounds = alpha.getbbox()
    if not bounds:
        raise RuntimeError("아이콘 전경을 찾지 못했습니다.")

    alpha = alpha.crop(bounds)
    width, height = alpha.size
    colored = Image.new("RGBA", (width, height))
    out = colored.load()
    opacity = alpha.load()
    left = (62, 99, 221)
    right = (35, 66, 166)
    for y in range(height):
        for x in range(width):
            ratio = x / max(1, width - 1)
            rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(left, right))
            out[x, y] = (*rgb, opacity[x, y])

    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    max_width, max_height = 824, 760
    scale = min(max_width / width, max_height / height)
    resized = colored.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
    canvas.alpha_composite(resized, ((1024 - resized.width) // 2, (1024 - resized.height) // 2))
    canvas.save(SOURCE, optimize=True)
    return canvas


def build_icons(icon: Image.Image) -> None:
    target = EXTENSION / "icons"
    target.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 128):
        icon.resize((size, size), Image.Resampling.LANCZOS).save(target / f"icon-{size}.png", optimize=True)


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
    draw.text((188, 86), "StudyEZ", font=font(38, bold=True), fill="#172554")
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
    draw.text((1230, 23), "StudyEZ 사용자", font=font(11), fill="#7A7F88")

    scaled = raw.resize((1280, 680), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1280, 800), "#F4F6FF")
    canvas.paste(scaled, (0, 60))
    canvas.save(HERE / "screenshot-calendar-1280x800.png", optimize=True)


if __name__ == "__main__":
    cleaned = clean_icon() if RAW.exists() else Image.open(SOURCE).convert("RGBA")
    build_icons(cleaned)
    build_promo(cleaned)
    build_store_screenshot()
    print(f"icons + {HERE / 'small-promo-440x280.png'}")
