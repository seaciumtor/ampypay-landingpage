"""Perspective correction for the hero tablet mockup.

Pushes the upper-left corner of the image plane slightly away from the
viewer (smaller / more recessed) while anchoring the lower-right corner,
so the tablet reads as angled away toward the upper-left.

Tune the warp with the four *_OFFSET constants below: each is the (dx, dy)
pixel displacement applied to that canvas corner in the destination quad.
Positive dx moves right, positive dy moves down. Pulling a corner toward
the image center makes that corner recede.

Usage:  python scripts/perspective_correct.py
Reads   assets/images/hero1-flipped.png
Writes  assets/images/hero1-corrected.png
"""
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'assets', 'images', 'hero1-flipped.png')
OUT = os.path.join(HERE, '..', 'assets', 'images', 'hero1-corrected.png')

# (dx, dy) per corner — subtle tilt about the lower-right corner.
UL_OFFSET = (44, 34)   # upper-left: recedes the most (in and down)
UR_OFFSET = (-12, 16)  # upper-right: slight recede, mid-depth
LL_OFFSET = (18, -8)   # lower-left: slight recede, mid-depth
LR_OFFSET = (0, 0)     # lower-right: anchored (closest to camera)

img = cv2.imread(SRC, cv2.IMREAD_UNCHANGED)  # BGRA, uint8
h, w = img.shape[:2]

src = np.float32([[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]])
dst = np.float32([
    [0 + UL_OFFSET[0],     0 + UL_OFFSET[1]],
    [w - 1 + UR_OFFSET[0], 0 + UR_OFFSET[1]],
    [0 + LL_OFFSET[0],     h - 1 + LL_OFFSET[1]],
    [w - 1 + LR_OFFSET[0], h - 1 + LR_OFFSET[1]],
])

print('source points (UL, UR, LL, LR):')
print(src)
print('destination points (UL, UR, LL, LR):')
print(dst)

M = cv2.getPerspectiveTransform(src, dst)
print('homography matrix:')
print(M)

# Premultiply alpha before resampling so transparent pixels (RGB=0) don't
# bleed dark fringes into the warped edges, then unpremultiply.
f = img.astype(np.float64)
alpha = f[..., 3:4] / 255.0
f[..., :3] *= alpha

warped = cv2.warpPerspective(
    f, M, (w, h),
    flags=cv2.INTER_LANCZOS4,
    borderMode=cv2.BORDER_CONSTANT,
    borderValue=(0, 0, 0, 0),
)

wa = np.clip(warped[..., 3:4], 0, 255) / 255.0
warped[..., :3] = warped[..., :3] / np.maximum(wa, 1e-6)
result = np.clip(warped, 0, 255).astype(np.uint8)

cv2.imwrite(OUT, result)
print(f'wrote {os.path.normpath(OUT)} ({w}x{h})')
