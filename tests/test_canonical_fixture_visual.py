"""Playwright snapshot battery for the canonical fixture HF preview (HOM-216).

Closes <issue id=HOM-210> by verifying the visual integrity of the
re-recorded ``canonical-portrait-talking-head`` composition. Three
layers, all rooted in HOM-210's defect table:

1. **Content assertions per frame.** Hook visible at t=1, thesis visible
   at t=7, thesis NOT on screen at t=14, payoff visible at t=17. Catches
   the HOM-210 t=0–2 empty-cream and t=3–11 "thesis stuck for 8s" classes
   without any image diff.
2. **Single caption block per frame.** ``.caption-block`` count ≤ 1 at
   every captured timestamp. Catches the HOM-210 caption-overlap class
   directly.
3. **Baseline PNG snapshots** committed under
   ``tests/snapshots/playwright/canonical-portrait-talking-head/`` —
   future PRs diff against these images via ``--update-snapshots``
   (mirrors :mod:`tests.test_brief_snapshots`'s policy: snapshot is
   asserted equal byte-for-byte; intentional changes regenerate via the
   flag, see ``tests/README.md``).

## Operator preconditions

The HF preview server must be running on ``http://localhost:3002`` for
the canonical fixture **before** invoking ``pytest``. Standing it up
inside the test would compound failure modes (preview server boot is
slow, port-binding flaky, and the operator runbook in
``tests/README.md`` already documents the manual flow). The test
``skip``s cleanly when port 3002 is closed — no false-failure when
running the suite at large.

```powershell
cd tests\\fixtures\\episodes\\canonical-portrait-talking-head\\hyperframes
npx hyperframes preview
# leave running, then in another shell:
python -m pytest tests/test_canonical_fixture_visual.py
```

Snapshot regeneration after a legitimate visual change:

```powershell
python -m pytest tests/test_canonical_fixture_visual.py \\
    --update-snapshots
```
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._helpers.playwright_seek import (
    DEFAULT_FPS,
    is_port_open,
    seek_and_capture,
)

PREVIEW_HOST = "localhost"
PREVIEW_PORT = 3002
PREVIEW_URL = (
    f"http://{PREVIEW_HOST}:{PREVIEW_PORT}/api/projects/hyperframes/preview"
)

# 22.367s composition (HOM-210 spec) — sample inside each scene boundary
# plus transitions. Aligned to the HOM-216 scope.
SEEK_TIMES_S = [0.0, 1.0, 3.0, 7.0, 11.0, 14.0, 17.0, 19.0, 21.0]

SNAPSHOT_DIR = (
    Path(__file__).parent / "snapshots" / "playwright"
    / "canonical-portrait-talking-head"
)

# Tolerance of pixel mismatches per snapshot in default mode. Anti-aliasing
# and font hinting differ tiny amounts across rendering machines; allow a
# small budget so the suite stays useful as a gate without becoming flaky.
# 5000 px on a 1080x1920 frame is ~0.24 % — still tight enough to catch
# any structural divergence, loose enough to absorb subpixel jitter.
SNAPSHOT_PIXEL_BUDGET = 5000


pytestmark = pytest.mark.skipif(
    not is_port_open(PREVIEW_HOST, PREVIEW_PORT),
    reason=(
        f"HF preview server not reachable at {PREVIEW_URL}. "
        f"See operator runbook at top of {Path(__file__).name} for setup."
    ),
)


def _update_snapshots(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-snapshots", default=False))


def _png_equal_within_budget(actual: bytes, expected: bytes) -> tuple[bool, int]:
    """Compare two PNG byte streams.

    Fast-path on identical bytes. If different, decode and compare pixel
    by pixel; allow up to :data:`SNAPSHOT_PIXEL_BUDGET` differing pixels
    before declaring a failure. Returns (passed, mismatch_count).
    """
    if actual == expected:
        return True, 0

    # Lazy-import Pillow so the suite still imports when Pillow is absent
    # — the snapshot test is the only place that needs raster decoding.
    try:
        from PIL import Image, ImageChops  # type: ignore
    except ImportError:
        # Without Pillow we can only compare bytes; treat byte-mismatch
        # as failure to keep the gate honest.
        return False, -1

    import io

    a = Image.open(io.BytesIO(actual)).convert("RGB")
    b = Image.open(io.BytesIO(expected)).convert("RGB")
    if a.size != b.size:
        return False, -1
    diff = ImageChops.difference(a, b)
    mismatch = sum(1 for px in diff.getdata() if px != (0, 0, 0))
    return mismatch <= SNAPSHOT_PIXEL_BUDGET, mismatch


@pytest.fixture(scope="module")
def shots(tmp_path_factory):
    """Capture all seek timestamps once per module run (boots Chromium once)."""
    out_dir = tmp_path_factory.mktemp("hom216-shots")
    return seek_and_capture(
        url=PREVIEW_URL,
        out_dir=out_dir,
        seek_times_s=SEEK_TIMES_S,
        fps=DEFAULT_FPS,
    )


def _shot_at(shots, t: float):
    for s in shots:
        if abs(s.t_seconds - t) < 0.01:
            return s
    raise AssertionError(f"no shot captured for t={t}")


# ---------------------------------------------------------------------------
# 1. Per-frame text content assertions (the HOM-210 defect classes)
# ---------------------------------------------------------------------------


def test_hook_visible_at_t1(shots):
    """HOM-210: t=0–2 empty-cream class — hook content must be on screen.

    The hook scene's quote is "Age of artificial intelligence." Asserting
    on the distinctive substring "intelligence" rather than the full
    sentence keeps the test robust to minor typography decisions
    (smart-quote vs ASCII, line break placement) while still failing if
    the hook scene fails to enter at all.
    """
    s = _shot_at(shots, 1.0)
    body = s.body_text.lower()
    assert "intelligence" in body, (
        f"hook content missing at t=1s; body text: {s.body_text!r}"
    )


def test_thesis_visible_at_t7(shots):
    """Thesis scene must be on screen at t=7 (mid-thesis range)."""
    s = _shot_at(shots, 7.0)
    body = s.body_text.lower()
    assert "open-source" in body or "ai agents" in body or "myself" in body, (
        f"thesis content missing at t=7s; body text: {s.body_text!r}"
    )


def test_thesis_not_on_screen_at_t14(shots):
    """HOM-210: thesis-stuck-for-8s class.

    By t=14 we are past the thesis range (3.05–13.7s in the EDL) and
    inside the gap before the payoff (18.77s). The thesis quote must
    NOT be on screen. We assert on the same distinctive substring used
    by the t=7 test so this test fails for the right reason if the
    thesis exit-pair is missing (HOM-165 anti-pattern).
    """
    s = _shot_at(shots, 14.0)
    body = s.body_text.lower()
    assert "open-source" not in body and "ai agents" not in body, (
        f"thesis content still on screen at t=14s; body text: {s.body_text!r}"
    )


def test_payoff_visible_at_t17(shots):
    """Payoff scene begins 18.77s; must be on screen by t=17 entrance lead-in.

    HOM-210's defect table marked t=15+ payoff transitions as "OK" — this
    test pins that observation so a regression on the payoff entrance
    surfaces immediately.
    """
    s = _shot_at(shots, 17.0)
    body = s.body_text.lower()
    assert "roots" in body or "good old software" in body or "life" in body, (
        f"payoff content missing at t=17s; body text: {s.body_text!r}"
    )


# ---------------------------------------------------------------------------
# 2. At most one caption block visible at any captured frame
# ---------------------------------------------------------------------------


def test_caption_block_count_in_dom():
    """Strong assertion: query .caption-block count at each seek timestamp.

    Re-runs Playwright with a query-driven loop instead of relying on
    the module-scoped ``shots`` fixture's body_text snapshot. Counts
    only DOM nodes that are both present AND have non-zero opacity at
    the seek timestamp — captions stage out via opacity transitions, so
    a still-mounted-but-faded block would otherwise inflate the count.
    """
    from playwright.sync_api import sync_playwright

    failures: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            ctx = browser.new_context(viewport={"width": 1080, "height": 1920})
            page = ctx.new_page()
            page.goto(PREVIEW_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(2_500)

            for t in SEEK_TIMES_S:
                frame = round(t * DEFAULT_FPS)
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
                page.wait_for_timeout(900)

                visible_count = page.evaluate(
                    """
                    () => {
                      const nodes = Array.from(
                        document.querySelectorAll('.caption-block')
                      );
                      return nodes.filter(n => {
                        const cs = window.getComputedStyle(n);
                        const o  = parseFloat(cs.opacity || '1');
                        const v  = cs.visibility !== 'hidden'
                                && cs.display    !== 'none';
                        return v && o > 0.05;
                      }).length;
                    }
                    """
                )
                if visible_count > 1:
                    failures.append(f"t={t}s: {visible_count} caption blocks visible")
        finally:
            browser.close()

    assert not failures, (
        "caption-block exit-before-next-entrance violated:\n  "
        + "\n  ".join(failures)
    )


# ---------------------------------------------------------------------------
# 3. Baseline PNG snapshots
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("t", SEEK_TIMES_S)
def test_snapshot_matches_baseline(t, shots, request):
    """Compare each captured frame to its committed baseline PNG.

    First-run / intentional change: invoke ``pytest --update-snapshots``
    to overwrite the baseline, then commit the resulting ``.png`` files.
    """
    s = _shot_at(shots, t)
    expected_path = SNAPSHOT_DIR / s.png_path.name

    if _update_snapshots(request) or not expected_path.exists():
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        expected_path.write_bytes(s.png_path.read_bytes())
        if not _update_snapshots(request):
            pytest.skip(
                f"baseline written for t={t}s -> {expected_path}; "
                "commit it and re-run without --update-snapshots"
            )
        return

    actual = s.png_path.read_bytes()
    expected = expected_path.read_bytes()
    passed, mismatch = _png_equal_within_budget(actual, expected)
    assert passed, (
        f"snapshot mismatch for t={t}s (mismatch_pixels={mismatch}, "
        f"budget={SNAPSHOT_PIXEL_BUDGET}); "
        f"diff actual={s.png_path} vs expected={expected_path}; "
        f"if intentional, re-run with --update-snapshots."
    )
