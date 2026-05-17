"""Generate the feathered lip-sync paste-back mask.

Run once; commit the output. LatentSync's shipped mask.png is a hard-edged
binary rectangle, which produces a visible seam where the synthesized
mouth region meets the original frame. Gaussian-blurring the edge fades
the composite over ~30px so the seam disappears.

Source: LatentSync repo at the SHA pinned in apps/modal_app/app.py
(LATENTSYNC_REPO_SHA). If the upstream mask changes, re-run this.

Usage:
    curl -sSfL "https://raw.githubusercontent.com/bytedance/LatentSync/<SHA>/latentsync/utils/mask.png" -o /tmp/src.png
    python scripts/gen_feathered_mask.py /tmp/src.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

# Re-binarise + small feather. Blurring the raw mask with a large sigma
# (no threshold) smears the boundary ~80px on a 256-tall image, bleeding
# the synthesised mouth region up into the nose/mustache and producing a
# melted look in the composite. We re-binarise to lock the boundary back
# to the upstream shape, then apply a small feather just to kill the
# paste-back seam.
THRESHOLD = 128
SIGMA_EDGE = 3  # ~6px soft seam on a 256x256 mask

src = Path(sys.argv[1])
dst = Path(__file__).resolve().parent.parent / "apps" / "modal_app" / "assets" / "lipsync_mask_feathered.png"
dst.parent.mkdir(parents=True, exist_ok=True)

img = Image.open(src).convert("L")
binary = img.point(lambda v: 255 if v >= THRESHOLD else 0)
feathered = binary.filter(ImageFilter.GaussianBlur(radius=SIGMA_EDGE))
feathered.save(dst)
print(f"wrote {dst}")
