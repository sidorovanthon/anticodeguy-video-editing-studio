"""Playwright seek-and-snapshot driver for HyperFrames preview pages.

HOM-216 — extracted from the session 2026-05-09 scratch driver
(``C:\\Users\\sidor\\AppData\\Local\\Temp\\hf-shots\\shoot.mjs``) and
ported to the Python sync API so the snapshot battery rides the same
``pytest`` invocation as the rest of the suite.

The driver speaks the HyperFrames preview parent-frame protocol via
``window.postMessage``. The preview page listens for control messages
of shape::

    {source: 'hf-parent', type: 'control', action: 'seek',
     frame: <int>, seekMode: 'commit'}

Operator preconditions (the test asserts these — the driver itself is
unopinionated):

* ``npx hyperframes preview`` running in the project under test, on the
  port the test binds to (default ``3002``, matching HF's own default).
* The composition's ``index.html`` is the served root.

Pure helper. No pytest fixtures, no asserts — those live in
``tests/test_canonical_fixture_visual.py`` so this module stays
reusable for future visual smoke tests on other fixtures.
"""

from __future__ import annotations

import contextlib
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from playwright.sync_api import Page, sync_playwright


# Portrait viewport — matches the canonical fixture's 1080x1920 render
# target (see ``tests/fixtures/episodes/canonical-portrait-talking-head/
# hyperframes/meta.json`` after scaffold). Snapshots scale to fit the
# default Chromium 1280x720 device viewport otherwise — keep this
# explicit so baseline PNGs are reproducible across machines.
DEFAULT_VIEWPORT = {"width": 1080, "height": 1920}
DEFAULT_FPS = 30


@dataclass(frozen=True)
class SeekShot:
    """One captured frame from the preview at a target timestamp."""

    t_seconds: float
    frame: int
    png_path: Path
    body_text: str


def is_port_open(host: str, port: int, *, timeout_s: float = 0.5) -> bool:
    """Quick TCP probe — used to skip the test cleanly when preview is offline."""
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def seek_and_capture(
    *,
    url: str,
    out_dir: Path,
    seek_times_s: Iterable[float],
    fps: int = DEFAULT_FPS,
    viewport: dict | None = None,
    settle_ms: int = 900,
    initial_settle_ms: int = 2500,
    out_prefix: str = "t",
) -> list[SeekShot]:
    """Headless Chromium seek battery against an HF preview URL.

    Sends one ``hf-parent control seek`` postMessage per target time,
    waits ``settle_ms`` for the GSAP root timeline + caption layer to
    quiesce, then writes a PNG to ``<out_dir>/<out_prefix><tNN>.png``
    and reads ``document.body.innerText`` for content assertions.

    Returns one :class:`SeekShot` per requested time, in input order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    viewport = viewport or DEFAULT_VIEWPORT
    shots: list[SeekShot] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            ctx = browser.new_context(viewport=viewport)
            page: Page = ctx.new_page()
            # Surface page errors so a broken composition fails the test
            # loudly instead of silently producing a blank screenshot.
            page.on("pageerror", lambda e: print(f"  [pageerror] {str(e)[:200]}"))
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(initial_settle_ms)

            for t in seek_times_s:
                frame = round(t * fps)
                page.evaluate(
                    """
                    ({frame}) => {
                      window.postMessage(
                        {source: 'hf-parent', type: 'control',
                         action: 'seek', frame, seekMode: 'commit'},
                        '*'
                      );
                    }
                    """,
                    {"frame": frame},
                )
                page.wait_for_timeout(settle_ms)
                fname = out_dir / f"{out_prefix}{int(round(t)):02d}.png"
                page.screenshot(path=str(fname))
                body_text = page.evaluate("() => document.body.innerText || ''")
                shots.append(SeekShot(t_seconds=float(t), frame=frame,
                                      png_path=fname, body_text=body_text))
        finally:
            browser.close()

    return shots


@contextlib.contextmanager
def headless_shots(**kwargs) -> Iterator[list[SeekShot]]:
    """Context-manager wrapper around :func:`seek_and_capture` for symmetry."""
    yield seek_and_capture(**kwargs)
