"""scene_id_for — sanitise a beat label into a stable HTML/CSS-safe identifier.

Used by `p4_dispatch_beats` to derive `scene_id` from `PlanBeat.beat`. The
result is the slug embedded in `#scene-<id>` selectors and the
`compositions/<id>.html` filename, so it must be:

  - ASCII-only (NFKD fold of accented chars)
  - lowercase
  - dashes for runs of non-alphanumerics
  - bounded length (<=64) to keep filesystem paths and CSS readable

Empty after sanitisation falls back to the literal `"scene"` rather than
raising — the dispatcher catches downstream collisions, and a blank label
will collide with another blank or with the fallback, surfacing both
labels in the error.
"""

from __future__ import annotations

import re
import unicodedata


_DASH_RUN = re.compile(r"[^a-zA-Z0-9]+")


def scene_id_for(beat_label: str) -> str:
    folded = unicodedata.normalize("NFKD", beat_label).encode("ascii", "ignore").decode()
    slugged = _DASH_RUN.sub("-", folded).strip("-").lower()
    return slugged[:64] or "scene"
