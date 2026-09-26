"""
Record GIFs of the 3D wall-dodge page.

The page renders itself frame by frame when opened with #capture=name:mode:trial and sends each
frame to this script, which serves the page and assembles the GIFs (needs Pillow).

    python scripts/capture_gifs.py --open      # opens each clip in your default browser, one after another

Without --open it just serves the page on http://127.0.0.1:8766/ and waits, so you can open the
capture URLs (printed below) yourself. Stop with Ctrl+C when all clips are done.
Output: ../output/gifs/*.gif
"""

import argparse
import base64
import io
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

HERE = Path(__file__).resolve().parent
WEB = HERE.parent / "output" / "web"
GIFS = HERE.parent / "output" / "gifs"
PORT = 8766
BASE = f"http://127.0.0.1:{PORT}/wall_dodge_3d.html"

CLIPS = [
    ("dodge_gap_left", "brain", 0),
    ("dodge_gap_right", "brain", 1),
    ("control_swapped_hit", "swapped", 1),
]
frames = {}
state = {"open_next": False}


def url_for(i):
    name, mode, trial = CLIPS[i]
    return f"{BASE}?clip={name}#capture={name}:{mode}:{trial}"


def build_gif(name, fps):
    imgs = [Image.open(io.BytesIO(frames[name][i])).convert("RGB") for i in sorted(frames[name])]
    sample = imgs[::6] + [imgs[-1]]
    montage = Image.new("RGB", (imgs[0].width, imgs[0].height * len(sample)))
    for i, im in enumerate(sample):
        montage.paste(im, (0, i * im.height))
    palette = montage.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    quant = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in imgs]
    GIFS.mkdir(parents=True, exist_ok=True)
    out = GIFS / f"{name}.gif"
    quant[0].save(out, save_all=True, append_images=quant[1:], duration=int(1000 / fps), loop=0, optimize=True, disposal=1)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB, {len(imgs)} frames)", flush=True)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(WEB), **k)

    def log_message(self, *args):
        pass

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if u.path == "/frame":
            frames.setdefault(q["name"], {})[int(q["i"])] = base64.b64decode(body.split(b",", 1)[1])
        elif u.path == "/done":
            threading.Thread(target=self.finish_clip, args=(q["name"], int(q["fps"])), daemon=True).start()
        self.send_response(204)
        self.end_headers()

    @staticmethod
    def finish_clip(name, fps):
        build_gif(name, fps)
        idx = [c[0] for c in CLIPS].index(name)
        if state["open_next"] and idx + 1 < len(CLIPS):
            webbrowser.open(url_for(idx + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--open", action="store_true", help="open the clips in your default browser automatically")
    args = ap.parse_args()
    state["open_next"] = args.open
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("capture URLs:")
    for i in range(len(CLIPS)):
        print("  ", url_for(i))
    if args.open:
        webbrowser.open(url_for(0))
    print("serving, Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
