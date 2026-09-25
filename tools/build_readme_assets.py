"""
Builds the SVG graphics used by README.md (banner, buttons, headers, diagrams).

GitHub READMEs can't load custom fonts or CSS, so every styled piece is an SVG
with the Saira font embedded inside it. Edit the text/colors below and re-run:

    pip install fonttools brotli pillow
    python tools/build_readme_assets.py

Inputs (font, avatars, school logo) are downloaded into tools/.cache on first run.
"""

import base64
import io
import urllib.request
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "readme"
CACHE = Path(__file__).resolve().parent / ".cache"

MULBERRY = "#32292F"
MULBERRY_DARK = "#241D22"
MULBERRY_LIGHT = "#4A3D46"
TURQUOISE = "#99E1D9"
WHITE = "#F4F1F3"
MUTED = "#B9AEB5"

FONT_URL = "https://github.com/google/fonts/raw/main/ofl/saira/Saira%5Bwdth,wght%5D.ttf"
LOGO_URL = "https://uktc-bg.com/uktc-content/themes/uktc-wp/images/logo.png"

TEAM = [
    ("Nikolay Rangelov", "Izu83"),
    ("Kiril Borisov", "KikarrA"),
    ("Ivan Damiankin", "IvanDD916"),
    ("Mitko Totev", "miti0o0"),
]

# (label, anchor) for the contents buttons
CONTENTS = [
    ("ABOUT", "about"),
    ("THE IDEA", "the-idea"),
    ("HOW IT WORKS", "how-it-works"),
    ("FIRST DEMO", "first-demo"),
    ("TEST 2", "test-2"),
    ("PROTOTYPE", "prototype"),
    ("ROADMAP", "roadmap"),
    ("LIMITATIONS", "limitations"),
    ("TEAM", "team"),
    ("THANKS", "thanks"),
]

HEADERS = {
    "about": "About",
    "the-idea": "The Idea",
    "how-it-works": "How It Might Work",
    "first-demo": "First Demo: Wall Dodge",
    "test-2": "Test 2: Building Escape",
    "prototype": "Prototype: Echo Room",
    "roadmap": "Roadmap",
    "limitations": "Limitations",
    "team": "Team",
    "thanks": "Thanks",
    "contents": "Contents",
}

PYTHON_PATH = (
    "M14.25.18l.9.2.73.26.59.3.45.32.34.34.25.34.16.33.1.3.04.26.02.2-.01.13V8.5l-.05.63-.13.55-.21.46-.26.38-.3.31"
    "-.33.25-.35.19-.35.14-.33.1-.3.07-.26.04-.21.02H8.77l-.69.05-.59.14-.5.22-.41.27-.33.32-.27.35-.2.36-.15.37-.1.35"
    "-.07.32-.04.27-.02.21v3.06H3.17l-.21-.03-.28-.07-.32-.12-.35-.18-.36-.26-.36-.36-.35-.46-.32-.59-.28-.73-.21-.88"
    "-.14-1.05-.05-1.23.06-1.22.16-1.04.24-.87.32-.71.36-.57.4-.44.42-.33.42-.24.4-.16.36-.1.32-.05.24-.01h.16l.06.01"
    "h8.16v-.83H6.18l-.01-2.75-.02-.37.05-.34.11-.31.17-.28.25-.26.31-.23.38-.2.44-.18.51-.15.58-.12.64-.1.71-.06.77-.04"
    ".84-.02 1.27.05zm-6.3 1.98l-.23.33-.08.41.08.41.23.34.33.22.41.09.41-.09.33-.22.23-.34.08-.41-.08-.41-.23-.33-.33"
    "-.22-.41-.09-.41.09zm13.09 3.95l.28.06.32.12.35.18.36.27.36.35.35.47.32.59.28.73.21.88.14 1.04.05 1.23-.06 1.23"
    "-.16 1.04-.24.86-.32.71-.36.57-.4.45-.42.33-.42.24-.4.16-.36.09-.32.05-.24.02-.16-.01h-8.22v.82h5.84l.01 2.76.02.36"
    "-.05.34-.11.31-.17.29-.25.25-.31.24-.38.2-.44.17-.51.15-.58.13-.64.09-.71.07-.77.04-.84.01-1.27-.04-1.07-.14-.9-.2"
    "-.73-.25-.59-.3-.45-.33-.34-.34-.25-.34-.16-.33-.1-.3-.04-.25-.02-.2.01-.13v-5.34l.05-.64.13-.54.21-.46.26-.38.3-.32"
    ".33-.24.35-.2.35-.14.33-.1.3-.06.26-.04.21-.02.13-.01h5.84l.69-.05.59-.14.5-.21.41-.28.33-.32.27-.35.2-.36.15-.36.1"
    "-.35.07-.32.04-.28.02-.21V6.07h2.09l.14.01zm-6.47 14.25l-.23.33-.08.41.08.41.23.33.33.23.41.08.41-.08.33-.23.23-.33"
    ".08-.41-.08-.41-.23-.33-.33-.23-.41-.08-.41.08z"
)
NUMPY_PATH = (
    "M10.315 4.876L6.3048 2.8517l-4.401 2.1965 4.1186 2.0683zm1.8381.9277l4.2045 2.1223-4.3622 2.1906-4.125-2.0718z"
    "m5.6153-2.9213l4.3193 2.1658-3.863 1.9402-4.2131-2.1252zm-1.859-.9329L12.021 0 8.1742 1.9193l4.0068 2.0208z"
    "m-3.0401 16.7443V24l4.7107-2.3507-.0053-5.3085zm4.7037-4.2057l-.0052-5.2528-4.6985 2.3356v5.2546zm5.6553-.9845"
    "v5.327l-4.0178 2.0052-.0029-5.3028zm0-1.8626V6.4214l-4.0253 2.001.0034 5.2633zM11.2062 11.571L8.0333 9.9756"
    "v6.895s-3.8804-8.2564-4.2399-8.998c-.0463-.0957-.2371-.2007-.2858-.2262C2.8118 7.2812.773 6.2485.773 6.2485"
    "V18.43l2.8204 1.5076v-6.3674s3.8392 7.3775 3.878 7.458c.0389.0807.4245.8582.8362 1.1314.5485.363 2.8992 1.7766"
    " 2.8992 1.7766z"
)


# ---------------------------------------------------------------- inputs

def fetch(url: str, name: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "echo-fly-readme"})
        path.write_bytes(urllib.request.urlopen(req).read())
    return path.read_bytes()


class Font:
    """One static weight of Saira, subset to the characters we use."""

    def __init__(self, var_font: bytes, weight: int):
        # fixed timestamps so re-running the script gives byte-identical files
        font = TTFont(io.BytesIO(var_font), recalcTimestamp=False)
        instantiateVariableFont(font, {"wght": weight, "wdth": 100}, inplace=True)
        self.font = font
        self.weight = weight
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"]

    def width(self, text: str, size: float, spacing: float = 0) -> float:
        total = 0
        for ch in text:
            glyph = self.cmap.get(ord(ch), ".notdef")
            total += self.hmtx[glyph][0]
        return total * size / self.upm + spacing * max(len(text) - 1, 0)

    def woff2_b64(self, text: str) -> str:
        font = TTFont(io.BytesIO(self._bytes()), recalcTimestamp=False)
        opts = Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        sub = Subsetter(opts)
        sub.populate(text=text + " ")
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        return base64.b64encode(buf.getvalue()).decode()

    def _bytes(self) -> bytes:
        buf = io.BytesIO()
        self.font.save(buf)
        return buf.getvalue()


def png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def circle_avatar(data: bytes, size: int = 200) -> str:
    img = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    img.putalpha(mask)
    return png_b64(img)


# ---------------------------------------------------------------- svg helpers

def font_css(fonts: dict, texts: dict) -> str:
    """fonts: {weight: Font}, texts: {weight: all text drawn at that weight}"""
    rules = []
    for weight, font in fonts.items():
        if texts.get(weight):
            rules.append(
                "@font-face{font-family:'Saira';font-weight:%d;"
                "src:url(data:font/woff2;base64,%s) format('woff2');}" % (weight, font.woff2_b64(texts[weight]))
            )
    return "<style>%s text{font-family:'Saira',sans-serif;}</style>" % "".join(rules)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts = []
        self.texts = {}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size, weight, fill, anchor="start", spacing=0, extra=""):
        self.texts[weight] = self.texts.get(weight, "") + s
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(
            f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{ls} {extra}>{esc(s)}</text>'
        )

    def render(self, fonts):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.title)}">'
            f"<title>{esc(self.title)}</title>{font_css(fonts, self.texts)}{''.join(self.parts)}</svg>"
        )


def fly_glyph(cx, cy, s, color):
    """Tiny top-down fruit fly: body, head, two wings."""
    return (
        f'<g transform="translate({cx} {cy}) scale({s})">'
        f'<ellipse cx="-9" cy="4" rx="11" ry="5" transform="rotate(-35 -9 4)" fill="{color}" opacity=".35"/>'
        f'<ellipse cx="9" cy="4" rx="11" ry="5" transform="rotate(35 9 4)" fill="{color}" opacity=".35"/>'
        f'<ellipse cx="0" cy="4" rx="4.5" ry="9" fill="{color}"/>'
        f'<circle cx="0" cy="-7.5" r="4" fill="{color}"/>'
        f"</g>"
    )


# ---------------------------------------------------------------- assets

def banner(fonts):
    names = [name for name, _ in TEAM]
    s = Svg(1200, 320, "Echo-Fly: made by " + ", ".join(names[:-1]) + " and " + names[-1] + ", UKTC")
    s.add(
        '<defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{MULBERRY}"/><stop offset=".62" stop-color="{MULBERRY}"/>'
        f'<stop offset="1" stop-color="{TURQUOISE}" stop-opacity=".22"/></linearGradient></defs>'
    )
    s.add(f'<rect x="1" y="1" width="1198" height="318" rx="22" fill="url(#g)" stroke="{MULBERRY_LIGHT}" stroke-width="2"/>')
    s.text(70, 118, "Echo-Fly", 76, 700, TURQUOISE)
    s.text(72, 162, "A simulated blind fruit fly brain, a homemade echolocator, and a lot of question marks", 21, 400, WHITE)
    s.add(f'<rect x="72" y="186" width="70" height="4" rx="2" fill="{TURQUOISE}"/>')
    made_by = "Made by " + " · ".join(names)
    # shrink the line if the names would run into the sonar logo on the right
    size = min(27, 27 * 790 / fonts[600].width(made_by, 27))
    s.text(72, 232, made_by, round(size, 1), 600, WHITE)
    s.text(72, 266, "11th grade project  ·  UKTC  ·  Pravets, Bulgaria", 18, 400, MUTED)

    # status chip
    chip = "EARLIEST STAGE"
    cw = fonts[600].width(chip, 13, 2) + 36
    s.add(f'<rect x="72" y="283" width="{cw:.0f}" height="26" rx="13" fill="none" stroke="{TURQUOISE}" stroke-opacity=".6"/>')
    s.add(f'<circle cx="87" cy="296" r="4" fill="{TURQUOISE}"><animate attributeName="opacity" values="1;.2;1" dur="2s" repeatCount="indefinite"/></circle>')
    s.text(98, 301, chip, 13, 600, TURQUOISE, spacing=2)

    # sonar rings with a fly in the middle
    cx, cy = 1020, 160
    s.add(f'<circle cx="{cx}" cy="{cy}" r="98" fill="none" stroke="{TURQUOISE}" stroke-opacity=".25" stroke-width="2"/>')
    s.add(f'<circle cx="{cx}" cy="{cy}" r="70" fill="none" stroke="{TURQUOISE}" stroke-width="5"/>')
    s.add(f'<circle cx="{cx}" cy="{cy}" r="46" fill="none" stroke="{TURQUOISE}" stroke-opacity=".6" stroke-width="3"/>')
    for delay in (0, 1.2):
        s.add(
            f'<circle cx="{cx}" cy="{cy}" r="30" fill="none" stroke="{TURQUOISE}" stroke-width="2">'
            f'<animate attributeName="r" values="30;120" dur="2.4s" begin="{delay}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values=".8;0" dur="2.4s" begin="{delay}s" repeatCount="indefinite"/></circle>'
        )
    s.add(fly_glyph(cx, cy + 2, 1.5, TURQUOISE))
    # viewfinder corners
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = cx + dx * 118, cy + dy * 118
        s.add(f'<path d="M{x} {y - dy * 26}V{y}H{x - dx * 26}" fill="none" stroke="{WHITE}" stroke-width="4"/>')
    s.add(f'<circle cx="1150" cy="36" r="6" fill="{TURQUOISE}"/>')
    return s.render(fonts)


def header(fonts, label):
    size = 44
    w = fonts[700].width(label, size) + 70
    s = Svg(max(int(w), 200), 84, label)
    s.add(f'<rect x="0" y="0" width="{s.w}" height="84" rx="16" fill="{MULBERRY}"/>')
    s.add(f'<rect x="0" y="16" width="6" height="52" rx="3" fill="{TURQUOISE}"/>')
    s.text(32, 58, label, size, 700, TURQUOISE)
    return s.render(fonts)


def button(fonts, label):
    size, spacing = 20, 4
    w = fonts[700].width(label, size, spacing) + 64
    s = Svg(int(w), 62, label)
    s.add(f'<rect x="1" y="1" width="{s.w - 2}" height="60" rx="8" fill="{MULBERRY}" stroke="{MULBERRY_LIGHT}"/>')
    s.text(32, 39, label, size, 700, WHITE, spacing=spacing)
    return s.render(fonts)


def badge(fonts, label, icon):
    size, spacing = 20, 4
    w = fonts[700].width(label, size, spacing) + 100
    s = Svg(int(w), 64, label)
    s.add(f'<rect width="{s.w}" height="64" rx="6" fill="{MULBERRY}"/>')
    s.add(f'<g transform="translate(24 18)">{icon}</g>')
    s.text(68, 40, label, size, 700, WHITE, spacing=spacing)
    return s.render(fonts)


def icon_path(path):
    return f'<g transform="scale(1.17)"><path d="{path}" fill="{TURQUOISE}"/></g>'


ICON_NEURON = (
    f'<g fill="none" stroke="{TURQUOISE}" stroke-width="2.4" stroke-linecap="round">'
    f'<circle cx="14" cy="14" r="5" fill="{TURQUOISE}"/>'
    '<path d="M14 9V2M10 11 3 5M18 11l7-6M14 19v4q0 4 5 5M10 17l-6 6"/></g>'
)
ICON_CHART = (
    f'<g fill="{TURQUOISE}"><rect x="2" y="16" width="6" height="12" rx="1"/>'
    '<rect x="11" y="8" width="6" height="20" rx="1"/><rect x="20" y="2" width="6" height="26" rx="1"/></g>'
)
ICON_FLY = fly_glyph(14, 15, 1.05, TURQUOISE)


def school_tile(fonts, logo: bytes):
    img = Image.open(io.BytesIO(logo)).convert("RGBA")
    img.thumbnail((260, 260), Image.LANCZOS)
    s = Svg(560, 210, "UKTC: Vocational High School of Computer Technologies and Systems, Pravets")
    s.add(f'<rect x="2" y="2" width="556" height="206" rx="26" fill="{MULBERRY}" stroke="{TURQUOISE}" stroke-width="4"/>')
    iw, ih = img.size
    scale = 150 / ih
    s.add(f'<image x="34" y="30" width="{iw * scale:.0f}" height="150" href="data:image/png;base64,{png_b64(img)}"/>')
    s.add(f'<rect x="228" y="52" width="2" height="106" fill="{MUTED}" opacity=".6"/>')
    s.text(258, 102, "UKTC", 48, 700, WHITE, spacing=4)
    s.text(260, 136, "uktc-bg.com", 20, 400, TURQUOISE, spacing=1)
    return s.render(fonts)


def member(fonts, name, handle, avatar: bytes):
    s = Svg(240, 290, f"{name} (@{handle})")
    s.add(f'<circle cx="120" cy="108" r="102" fill="{MULBERRY}" stroke="{TURQUOISE}" stroke-width="5"/>')
    s.add(f'<image x="24" y="12" width="192" height="192" href="data:image/png;base64,{circle_avatar(avatar)}"/>')
    s.text(120, 248, name, 22, 600, TURQUOISE, anchor="middle")
    s.text(120, 276, "@" + handle, 17, 400, MUTED, anchor="middle")
    return s.render(fonts)


def pipeline(fonts):
    steps = [
        ("Virtual world", "walls / a building"),
        ("Sonar ping", "beams bounce back"),
        ("Sensory neurons", "echo → firing rate"),
        ("Fly connectome", "~140k neurons"),
        ("Motor neurons", "turn / walk / back up"),
    ]
    bw, bh, gap, x0, y0 = 196, 104, 36, 20, 30
    w = x0 * 2 + len(steps) * bw + (len(steps) - 1) * gap
    s = Svg(w, 250, "Pipeline: virtual world, sonar ping, sensory neurons, fly connectome, motor neurons, then the fly moves and pings again")
    s.add(f'<rect width="{w}" height="250" rx="20" fill="{MULBERRY_DARK}"/>')
    s.add(
        f'<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0 0L10 5L0 10z" fill="{TURQUOISE}"/></marker></defs>'
    )
    for i, (title, sub) in enumerate(steps):
        x = x0 + i * (bw + gap)
        hero = i == 3
        s.add(
            f'<rect x="{x}" y="{y0}" width="{bw}" height="{bh}" rx="12" '
            f'fill="{TURQUOISE if hero else MULBERRY}" stroke="{TURQUOISE}" stroke-width="2"/>'
        )
        s.text(x + bw / 2, y0 + 46, title, 21, 700, MULBERRY if hero else TURQUOISE, anchor="middle")
        s.text(x + bw / 2, y0 + 76, sub, 16, 400, MULBERRY if hero else MUTED, anchor="middle")
        if i < len(steps) - 1:
            s.add(
                f'<line x1="{x + bw + 4}" y1="{y0 + bh / 2}" x2="{x + bw + gap - 4}" y2="{y0 + bh / 2}" '
                f'stroke="{TURQUOISE}" stroke-width="2.5" marker-end="url(#a)"/>'
            )
    # loop back: fly moves → ping again
    lx1 = x0 + (len(steps) - 1) * (bw + gap) + bw / 2
    lx2 = x0 + bw / 2
    ly = y0 + bh + 60
    s.add(
        f'<path d="M{lx1} {y0 + bh + 4}V{ly}H{lx2}V{y0 + bh + 10}" fill="none" stroke="{TURQUOISE}" '
        f'stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#a)"/>'
    )
    s.text(w / 2, ly - 12, "the fly moves (or dodges), then pings again", 17, 500, WHITE, anchor="middle")
    return s.render(fonts)


def demo(fonts):
    """Top-down view of the first demo: stationary fly, wall with a gap coming at it."""
    W, H = 900, 520
    s = Svg(W, H, "First demo: a stationary fly sends sonar beams at an incoming wall and has to dodge toward the gap")
    s.add(f'<rect width="{W}" height="{H}" rx="20" fill="{MULBERRY_DARK}"/>')
    # lane
    lane_x0, lane_x1 = 190, 710
    s.add(f'<rect x="{lane_x0}" y="30" width="{lane_x1 - lane_x0}" height="{H - 60}" rx="8" fill="{MULBERRY}"/>')
    fx, fy = 450, 430
    # the wall (left part solid, gap on the right) sliding toward the fly
    gap_x0, gap_x1 = 540, 700
    wall_y, wall_h = 120, 22
    s.add(f'<rect x="{lane_x0 + 10}" y="{wall_y}" width="{gap_x0 - lane_x0 - 10}" height="{wall_h}" rx="4" fill="{WHITE}"/>')
    s.add(
        f'<rect x="{gap_x0}" y="{wall_y}" width="{gap_x1 - gap_x0}" height="{wall_h}" rx="4" fill="none" '
        f'stroke="{TURQUOISE}" stroke-dasharray="6 5" stroke-width="2"/>'
    )
    s.text(gap_x0 + (gap_x1 - gap_x0) / 2, 104, "GAP", 15, 700, TURQUOISE, anchor="middle", spacing=3)
    s.text(lane_x0 + 18, 104, "WALL", 15, 700, WHITE, spacing=3)
    # "incoming" chevrons drifting toward the fly
    for i, x in enumerate((260, 450, 640)):
        s.add(
            f'<path d="M{x - 12} 60l12 10 12-10" fill="none" stroke="{MUTED}" stroke-width="2.5">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;0 22" dur="1.4s" '
            f'begin="{i * 0.2}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;0" dur="1.4s" begin="{i * 0.2}s" repeatCount="indefinite"/></path>'
        )
    s.text(W / 2, 52, "INCOMING", 13, 600, MUTED, anchor="middle", spacing=3)
    # sonar beams: a beam that hits the solid wall stops there (strong echo),
    # one that lands in the gap keeps going (weak echo)
    import math
    hit_y = wall_y + wall_h
    for ang in (-40, -20, 0, 20, 40):
        rad = math.radians(ang)
        hit_x = fx + math.tan(rad) * (fy - hit_y)
        strong = lane_x0 + 10 <= hit_x < gap_x0
        if strong:
            x2, y2 = hit_x, hit_y
        else:
            # extend until it leaves the lane (top or side)
            t_top = (fy - 40) / math.cos(rad)
            t_side = ((lane_x1 - 6 - fx) / math.sin(rad)) if ang > 0 else ((lane_x0 + 6 - fx) / math.sin(rad)) if ang < 0 else t_top
            t = min(t_top, t_side)
            x2, y2 = fx + math.sin(rad) * t, fy - math.cos(rad) * t
        s.add(
            f'<line x1="{fx}" y1="{fy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{TURQUOISE}" '
            f'stroke-width="{3 if strong else 1.5}" stroke-opacity="{.95 if strong else .4}" '
            f'stroke-dasharray="{"0" if strong else "4 6"}"/>'
        )
    # ping rings
    for delay in (0, 0.9):
        s.add(
            f'<circle cx="{fx}" cy="{fy}" r="14" fill="none" stroke="{TURQUOISE}" stroke-width="2">'
            f'<animate attributeName="r" values="14;110" dur="1.8s" begin="{delay}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values=".9;0" dur="1.8s" begin="{delay}s" repeatCount="indefinite"/></circle>'
        )
    s.add(fly_glyph(fx, fy, 2, TURQUOISE))
    # dodge arrows
    s.add(
        f'<defs><marker id="d" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
        f'<path d="M0 0L10 5L0 10z" fill="{TURQUOISE}"/></marker>'
        f'<marker id="dm" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
        f'<path d="M0 0L10 5L0 10z" fill="{MUTED}"/></marker></defs>'
    )
    s.add(f'<line x1="{fx + 40}" y1="{fy + 8}" x2="{fx + 150}" y2="{fy + 8}" stroke="{TURQUOISE}" stroke-width="3" marker-end="url(#d)"/>')
    s.add(f'<line x1="{fx - 40}" y1="{fy + 8}" x2="{fx - 150}" y2="{fy + 8}" stroke="{MUTED}" stroke-width="2" stroke-dasharray="5 5" marker-end="url(#dm)"/>')
    s.text(fx + 96, fy + 38, "dodge?", 16, 600, TURQUOISE, anchor="middle")
    s.text(fx - 96, fy + 38, "or here?", 16, 400, MUTED, anchor="middle")
    s.text(fx, fy + 62, "the fly (stays in place)", 15, 500, WHITE, anchor="middle")
    # side notes
    s.text(95, 200, "strong", 17, 700, TURQUOISE, anchor="middle")
    s.text(95, 222, "echoes", 17, 700, TURQUOISE, anchor="middle")
    s.text(95, 246, "(wall is close)", 14, 400, MUTED, anchor="middle")
    s.text(805, 200, "weak", 17, 700, TURQUOISE, anchor="middle")
    s.text(805, 222, "echo", 17, 700, TURQUOISE, anchor="middle")
    s.text(805, 246, "(open gap)", 14, 400, MUTED, anchor="middle")
    return s.render(fonts)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    var = fetch(FONT_URL, "saira.ttf")
    fonts = {w: Font(var, w) for w in (400, 500, 600, 700)}

    files = {
        "banner.svg": banner(fonts),
        "pipeline.svg": pipeline(fonts),
        "demo-wall-dodge.svg": demo(fonts),
        "school-uktc.svg": school_tile(fonts, fetch(LOGO_URL, "uktc_logo.png")),
        "badge-python.svg": badge(fonts, "PYTHON", icon_path(PYTHON_PATH)),
        "badge-brian2.svg": badge(fonts, "BRIAN2", ICON_NEURON),
        "badge-flywire.svg": badge(fonts, "FLYWIRE", ICON_FLY),
        "badge-numpy.svg": badge(fonts, "NUMPY", icon_path(NUMPY_PATH)),
        "badge-matplotlib.svg": badge(fonts, "MATPLOTLIB", ICON_CHART),
    }
    for name, handle in TEAM:
        avatar = fetch(f"https://github.com/{handle}.png?size=256", f"avatar_{handle}.png")
        files[f"team-{handle.lower()}.svg"] = member(fonts, name, handle, avatar)
    for label, anchor in CONTENTS:
        files[f"btn-{anchor}.svg"] = button(fonts, label)
    for anchor, label in HEADERS.items():
        files[f"h-{anchor}.svg"] = header(fonts, label)

    for fname, svg in files.items():
        (OUT / fname).write_text(svg, encoding="utf-8")
    print(f"wrote {len(files)} files to {OUT}")


if __name__ == "__main__":
    main()
