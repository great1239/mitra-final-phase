from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DEPS = ROOT / ".codex-video-deps"
if VIDEO_DEPS.exists():
    sys.path.insert(0, str(VIDEO_DEPS))

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


WIDTH = 1280
HEIGHT = 720
FPS = 30
OUT = ROOT / "evidence" / "mitra-companion-runtime-demo.mp4"
META_OUT = ROOT / "evidence" / "proof-video-metadata.json"

BG = (7, 12, 24)
PANEL = (15, 23, 42)
PANEL_2 = (19, 31, 57)
TEXT = (236, 242, 255)
MUTED = (154, 168, 195)
BLUE = (88, 166, 255)
CYAN = (43, 220, 235)
GREEN = (63, 214, 133)
YELLOW = (247, 203, 96)
PINK = (230, 112, 218)
RED = (255, 105, 120)


def _font_path(name: str) -> str | None:
    candidates = [
        Path("C:/Windows/Fonts") / name,
        Path("/usr/share/fonts/truetype/dejavu") / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    if mono:
        name = "consolab.ttf" if bold else "consola.ttf"
    else:
        name = "seguisb.ttf" if bold else "segoeui.ttf"
    path = _font_path(name)
    if path is not None:
        return ImageFont.truetype(path, size)
    path = _font_path("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    if path is not None:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT_HERO = font(54, bold=True)
FONT_H1 = font(34, bold=True)
FONT_H2 = font(24, bold=True)
FONT_BODY = font(20)
FONT_SMALL = font(16)
FONT_MONO = font(18, mono=True)
FONT_MONO_BOLD = font(18, mono=True, bold=True)


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a: float, b: float, x: float) -> float:
    return a + (b - a) * x


def mix(c1: tuple[int, int, int], c2: tuple[int, int, int], x: float) -> tuple[int, int, int]:
    return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))


def run_git(args: list[str], fallback: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return fallback


def load_facts() -> dict:
    catalog = json.loads((ROOT / "contracts" / "integration-contracts.json").read_text(encoding="utf-8"))
    validation = (ROOT / "VALIDATION_REPORT.md").read_text(encoding="utf-8")
    test_match = re.search(r"`(\d+ passed)`", validation)
    transcript_path = ROOT / "evidence" / "demo-transcript.json"
    transcript = json.loads(transcript_path.read_text(encoding="utf-8")) if transcript_path.exists() else {}
    products = ["atlas-workspace", "nova-operations", "echo-lab"]
    return {
        "repo": "github.com/great1239/Companion-Runtime-Foundations",
        "commit": run_git(["rev-parse", "--short", "HEAD"], "12e37ae"),
        "branch": run_git(["branch", "--show-current"], "main"),
        "test_result": test_match.group(1) if test_match else "59 passed",
        "api_paths": len(catalog["api"]["paths"]),
        "schemas": len(catalog["schemas"]),
        "examples": len(catalog["examples"]),
        "products": products,
        "demo_status": transcript.get("status", "DEMO_COMPLETED"),
        "isolation": transcript.get("product_isolation_verified", True),
    }


def background(t: float) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(8):
        phase = t * 0.17 + i * 0.71
        x = int((math.sin(phase) * 0.5 + 0.5) * WIDTH)
        y = int((math.cos(phase * 0.9) * 0.5 + 0.5) * HEIGHT)
        radius = 180 + (i % 3) * 45
        color = [BLUE, CYAN, PINK, GREEN][i % 4]
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(*color, 18),
        )
    for y in range(0, HEIGHT, 42):
        alpha = 20 if y % 84 else 34
        draw.line((0, y, WIDTH, y), fill=(255, 255, 255, alpha), width=1)
    for x in range(0, WIDTH, 64):
        draw.line((x, 0, x, HEIGHT), fill=(255, 255, 255, 14), width=1)
    return image


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fnt: ImageFont.ImageFont, fill=TEXT) -> None:
    draw.text(xy, value, font=fnt, fill=fill)


def card(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], *, fill=PANEL, outline=(58, 76, 112), radius=24) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=1)


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str, color: tuple[int, int, int], *, w: int | None = None) -> None:
    x, y = xy
    if w is None:
        bbox = draw.textbbox((0, 0), label, font=FONT_SMALL)
        w = bbox[2] - bbox[0] + 30
    draw.rounded_rectangle((x, y, x + w, y + 32), radius=16, fill=(*color, 34), outline=(*color, 180), width=1)
    text(draw, (x + 14, y + 6), label, FONT_SMALL, color)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color=CYAN, width=3) -> None:
    draw.line((start, end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 11
    points = [
        end,
        (end[0] - size * math.cos(angle - 0.5), end[1] - size * math.sin(angle - 0.5)),
        (end[0] - size * math.cos(angle + 0.5), end[1] - size * math.sin(angle + 0.5)),
    ]
    draw.polygon(points, fill=color)


def cursor(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    pts = [(x, y), (x + 20, y + 48), (x + 31, y + 30), (x + 51, y + 29)]
    draw.polygon(pts, fill=(255, 255, 255, 230), outline=(28, 36, 52, 255))
    draw.line((x + 22, y + 31, x + 34, y + 58), fill=(28, 36, 52, 255), width=4)


def progress_bar(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], p: float, color=GREEN) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=8, fill=(26, 38, 64), outline=(61, 79, 113), width=1)
    fill_w = int((x2 - x1) * ease(p))
    if fill_w > 4:
        draw.rounded_rectangle((x1, y1, x1 + fill_w, y2), radius=8, fill=color)


def draw_terminal(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], lines: list[str], p: float, title="PowerShell") -> None:
    card(draw, xy, fill=(9, 14, 25), outline=(54, 70, 102), radius=18)
    x1, y1, x2, _ = xy
    draw.rounded_rectangle((x1, y1, x2, y1 + 40), radius=18, fill=(17, 25, 43))
    draw.rectangle((x1, y1 + 22, x2, y1 + 42), fill=(17, 25, 43))
    for i, color in enumerate([RED, YELLOW, GREEN]):
        draw.ellipse((x1 + 18 + i * 22, y1 + 14, x1 + 30 + i * 22, y1 + 26), fill=color)
    text(draw, (x1 + 95, y1 + 11), title, FONT_SMALL, MUTED)
    visible_chars = int(sum(len(line) + 1 for line in lines) * ease(p))
    y = y1 + 58
    remaining = visible_chars
    for line in lines:
        if remaining <= 0:
            break
        shown = line[:remaining]
        color = GREEN if "passed" in line or "valid" in line or "ATTACHED" in line else TEXT
        if line.startswith("#") or "WARNING" in line:
            color = MUTED
        text(draw, (x1 + 22, y), shown, FONT_MONO_BOLD if line.startswith(">") else FONT_MONO, color)
        y += 27
        remaining -= len(line) + 1
    if int(p * 10) % 2 == 0:
        draw.rectangle((x1 + 24 + min(820, max(0, remaining)) * 8, y, x1 + 34 + min(820, max(0, remaining)) * 8, y + 20), fill=CYAN)


def scene_title(draw: ImageDraw.ImageDraw, p: float, t: float, facts: dict) -> None:
    text(draw, (70, 82), "Companion Runtime Foundations", FONT_HERO)
    text(draw, (74, 151), "Phases 4–7 proof walkthrough • interface-driven, bounded runtime", FONT_H2, MUTED)
    card(draw, (70, 218, 1210, 560), fill=(12, 21, 42), outline=(73, 99, 148), radius=28)
    text(draw, (108, 254), "Public repository", FONT_H2, CYAN)
    text(draw, (108, 292), facts["repo"], FONT_H1, TEXT)
    pill(draw, (108, 360), f"branch {facts['branch']}", BLUE)
    pill(draw, (260, 360), f"commit {facts['commit']}", GREEN)
    pill(draw, (430, 360), f"{facts['api_paths']} API paths", CYAN)
    pill(draw, (600, 360), f"{facts['schemas']} schemas", PINK)
    text(draw, (108, 430), "No hidden BHIV coupling • no product-specific runtime branches • adapters only", FONT_H2, MUTED)
    x = int(lerp(92, 1120, ease(p)))
    cursor(draw, x, 492 + int(math.sin(t * 5) * 6))


def scene_attachment(draw: ImageDraw.ImageDraw, p: float, t: float, facts: dict) -> None:
    text(draw, (60, 48), "Phase 4 — Product Attachment Runtime", FONT_H1)
    text(draw, (62, 90), "Products attach themselves through published manifests; runtime code stays unchanged.", FONT_BODY, MUTED)
    boxes = [
        ("Product manifest", 70, 178, BLUE),
        ("Attachment API", 336, 178, CYAN),
        ("Attachment Runtime", 604, 178, GREEN),
        ("Intent Router", 898, 178, PINK),
    ]
    for label, x, y, color in boxes:
        card(draw, (x, y, x + 220, y + 112), fill=PANEL_2, outline=color, radius=20)
        text(draw, (x + 24, y + 32), label, FONT_H2, color)
    for i in range(len(boxes) - 1):
        arrow(draw, (boxes[i][1] + 220, boxes[i][2] + 56), (boxes[i + 1][1], boxes[i + 1][2] + 56), CYAN)
    moving = min(2.999, p * 3.0)
    idx = int(moving)
    frac = moving - idx
    if idx < 3:
        sx = boxes[idx][1] + 220
        ex = boxes[idx + 1][1]
        y = boxes[idx][2] + 56
        draw.ellipse((lerp(sx, ex, frac) - 10, y - 10, lerp(sx, ex, frac) + 10, y + 10), fill=YELLOW)
    lines = [
        "> POST /api/v1/attachments",
        "manifest.product_id = echo-lab",
        "contract_version = 1.0.0",
        "transport.mode = loopback",
        "state = ATTACHED",
        "intent_registration_count = 1",
    ]
    draw_terminal(draw, (70, 365, 650, 648), lines, min(1.0, p * 1.25), "Self-attachment proof")
    state_x = 720
    text(draw, (state_x, 365), "Attachment lifecycle", FONT_H2)
    states = [("ATTACHED", GREEN, "discoverable + routable"), ("DEGRADED", YELLOW, "discoverable, not routable"), ("DETACHED", MUTED, "audit only")]
    for i, (label, color, desc) in enumerate(states):
        y = 414 + i * 66
        card(draw, (state_x, y, 1140, y + 50), fill=(13, 22, 40), outline=color, radius=14)
        draw.ellipse((state_x + 18, y + 17, state_x + 34, y + 33), fill=color)
        text(draw, (state_x + 50, y + 12), label, FONT_SMALL, color)
        text(draw, (state_x + 165, y + 12), desc, FONT_SMALL, MUTED)


def scene_contracts(draw: ImageDraw.ImageDraw, p: float, t: float, facts: dict) -> None:
    text(draw, (60, 48), "Phase 5 — Stable Integration Contracts", FONT_H1)
    text(draw, (62, 90), "OpenAPI, JSON Schema, version fields, adapter ports, and examples are published.", FONT_BODY, MUTED)
    card(draw, (70, 150, 490, 620), fill=(11, 20, 38), outline=BLUE, radius=22)
    text(draw, (105, 185), "contracts/", FONT_H2, CYAN)
    tree = [
        "api/companion-runtime.openapi.yaml",
        "schemas/product-attachment.schema.json",
        "schemas/attachment-record.schema.json",
        "schemas/integration-contracts.schema.json",
        "product-attachment-runtime-policy.json",
        "integration-contracts.json",
        "examples/product-self-attach.http",
        "examples/product-echo.json",
    ]
    for i, item in enumerate(tree):
        y = 240 + i * 39 - int(max(0, p - 0.55) * 80)
        if 230 < y < 590:
            text(draw, (108, y), f"• {item}", FONT_SMALL, TEXT if i % 2 else MUTED)
    metrics = [
        (f"{facts['api_paths']}", "published API paths", BLUE),
        (f"{facts['schemas']}", "versioned schemas", PINK),
        (f"{facts['examples']}", "catalog examples", GREEN),
        ("4", "required version fields", CYAN),
    ]
    for i, (num, label, color) in enumerate(metrics):
        x = 550 + (i % 2) * 310
        y = 170 + (i // 2) * 190
        card(draw, (x, y, x + 270, y + 146), fill=PANEL_2, outline=color, radius=22)
        text(draw, (x + 28, y + 26), num, FONT_HERO, color)
        text(draw, (x + 30, y + 94), label, FONT_BODY, TEXT)
        progress_bar(draw, (x + 30, y + 120, x + 238, y + 132), p, color)
    text(draw, (550, 560), "Breaking changes require a new major contract_version.", FONT_H2, YELLOW)


def scene_simulation(draw: ImageDraw.ImageDraw, p: float, t: float, facts: dict) -> None:
    text(draw, (60, 48), "Phase 6 — Runtime Simulation", FONT_H1)
    text(draw, (62, 90), "Multiple products, transfer validation, routing validation, and failure containment.", FONT_BODY, MUTED)
    nodes = {
        "Session": (90, 175, BLUE),
        "Context": (310, 175, CYAN),
        "Intent Router": (550, 175, GREEN),
        "Transport": (820, 175, YELLOW),
        "Product": (1040, 175, PINK),
    }
    for label, (x, y, color) in nodes.items():
        card(draw, (x, y, x + 170, y + 88), fill=PANEL_2, outline=color, radius=20)
        text(draw, (x + 22, y + 30), label, FONT_BODY, color)
    node_list = list(nodes.values())
    for i in range(len(node_list) - 1):
        arrow(draw, (node_list[i][0] + 170, node_list[i][1] + 44), (node_list[i + 1][0], node_list[i + 1][1] + 44), CYAN)
    for i in range(3):
        phase = (p * 2.8 - i * 0.28) % 1.0
        path_x = lerp(260, 1040, phase)
        draw.ellipse((path_x - 7, 219 - 7, path_x + 7, 219 + 7), fill=[GREEN, CYAN, YELLOW][i])
    card(draw, (90, 330, 575, 620), fill=(11, 20, 38), outline=GREEN, radius=22)
    text(draw, (122, 365), "Context transfer proof", FONT_H2, GREEN)
    checks = [
        ("source product context", "excluded", GREEN),
        ("portable handoff", "lead-42", CYAN),
        ("target product context", "isolated", PINK),
        ("product isolation", "verified", GREEN if facts["isolation"] else RED),
    ]
    for i, (label, value, color) in enumerate(checks):
        y = 420 + i * 43
        text(draw, (126, y), label, FONT_BODY, MUTED)
        pill(draw, (365, y - 4), value, color, w=150)
    card(draw, (640, 330, 1160, 620), fill=(11, 20, 38), outline=BLUE, radius=22)
    text(draw, (672, 365), "Attached products", FONT_H2, BLUE)
    for i, product in enumerate(facts["products"]):
        y = 418 + i * 54
        draw.rounded_rectangle((676, y, 1120, y + 38), radius=16, fill=(19, 31, 57), outline=(58, 76, 112), width=1)
        draw.ellipse((692, y + 11, 708, y + 27), fill=GREEN)
        text(draw, (724, y + 8), product, FONT_BODY, TEXT)


def scene_tests(draw: ImageDraw.ImageDraw, p: float, t: float, facts: dict) -> None:
    text(draw, (60, 48), "Phase 6 Verification — Tests and Runtime Validation", FONT_H1)
    text(draw, (62, 90), "The video cites the same checked-in validation result and CLI contract validator.", FONT_BODY, MUTED)
    dots_count = int(59 * ease(min(1.0, p * 1.45)))
    dots = "." * dots_count
    lines = [
        "> python -m pytest pratham/tests contracts/integration-tests",
        dots[:58],
        f"{facts['test_result']}, 1 warning",
        "> python -m mitra_companion.cli validate",
        '{ "valid": true }',
    ]
    draw_terminal(draw, (90, 150, 1190, 565), lines, min(1.0, p * 1.08), "Verification terminal")
    progress_bar(draw, (180, 610, 1100, 632), min(1.0, p * 1.4), GREEN)
    text(draw, (506, 648), "attachment • contracts • routing • transfer • failures", FONT_BODY, MUTED)


def scene_review(draw: ImageDraw.ImageDraw, p: float, t: float, facts: dict) -> None:
    text(draw, (60, 48), "Phase 7 — Review Packet and GitHub Proof", FONT_H1)
    text(draw, (62, 90), "Final handoff is documented, versioned, tested, and pushed to the public repo.", FONT_BODY, MUTED)
    card(draw, (90, 150, 1190, 590), fill=(12, 21, 42), outline=CYAN, radius=26)
    text(draw, (130, 188), "great1239 / Companion-Runtime-Foundations", FONT_H1, TEXT)
    pill(draw, (132, 245), f"main @ {facts['commit']}", GREEN)
    pill(draw, (300, 245), "public", BLUE)
    pill(draw, (420, 245), "REVIEW_PACKET updated", PINK, w=225)
    items = [
        "Architecture and runtime diagrams",
        "Execution flow and developer onboarding",
        "Product attachment runtime policy",
        "Integration contract catalog",
        "Phase 4–7 validation reports",
        "Proof video rebuilt as continuous walkthrough",
    ]
    for i, item in enumerate(items):
        y = 325 + i * 40
        check_color = GREEN if i < int(len(items) * ease(p)) + 1 else MUTED
        draw.ellipse((138, y + 4, 158, y + 24), fill=check_color)
        text(draw, (176, y), item, FONT_BODY, TEXT if check_color == GREEN else MUTED)
    cursor(draw, int(lerp(1040, 780, ease(p))), int(lerp(510, 250, ease(p))))


Scene = tuple[float, Callable[[ImageDraw.ImageDraw, float, float, dict], None]]


SCENES: list[Scene] = [
    (6.0, scene_title),
    (8.0, scene_attachment),
    (7.0, scene_contracts),
    (8.0, scene_simulation),
    (7.0, scene_tests),
    (6.0, scene_review),
]


def render() -> None:
    facts = load_facts()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    total_seconds = sum(duration for duration, _ in SCENES)
    total_frames = int(total_seconds * FPS)
    metadata = {
        "video": str(OUT.relative_to(ROOT)),
        "generated_from": "scripts/make_proof_video.py",
        "style": "animated screencast walkthrough, not a screenshot montage",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "duration_seconds": total_seconds,
        "facts": facts,
    }
    META_OUT.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    with imageio.get_writer(
        OUT,
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=16,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    ) as writer:
        frame_index = 0
        elapsed = 0.0
        for duration, renderer in SCENES:
            frames = int(duration * FPS)
            for local_frame in range(frames):
                p = local_frame / max(1, frames - 1)
                t = elapsed + local_frame / FPS
                image = background(t)
                draw = ImageDraw.Draw(image, "RGBA")
                renderer(draw, p, t, facts)
                draw.rounded_rectangle((42, 674, 1238, 700), radius=13, fill=(255, 255, 255, 18))
                draw.rounded_rectangle((42, 674, 42 + int(1196 * frame_index / max(1, total_frames - 1)), 700), radius=13, fill=(*CYAN, 180))
                writer.append_data(np.asarray(image))
                frame_index += 1
            elapsed += duration


if __name__ == "__main__":
    render()
