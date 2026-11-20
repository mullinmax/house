#!/usr/bin/env python3
"""Writes site/models/textures/butcher_block.jpg: edge grain butcher block for the kitchen island top
(Maxwell 11/20/2026). Staves about 1 1/2 in wide run along the texture's v (the grain direction in site/house.js), each
with its own tone and the grain of white_oak.jpg, broken by staggered butt joints. It tiles in both directions.

    python tools/make_butcher_texture.py [R G B]       (mean colour, default 196 140 88: oiled oak/maple, warm amber)
"""
import os, sys
import numpy as np
from PIL import Image

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "models", "textures")
target = np.array([float(v) for v in sys.argv[1:4]] if len(sys.argv) >= 4 else [196, 140, 88])
N, STAVES = 1024, 21                    # the material tiles every 0.8 m (31.5 in), so 21 staves are 1.5 in each
rng = np.random.default_rng(7)
src = np.asarray(Image.open(os.path.join(T, "white_oak.jpg")).convert("RGB")).astype(float)
lum = src @ [0.299, 0.587, 0.114]
grain = (lum - lum.mean()) / max(lum.std(), 1e-6)
out = np.zeros((N, N, 3))
edges = np.linspace(0, N, STAVES + 1).round().astype(int)
for i in range(STAVES):
    a, b = edges[i], edges[i + 1]
    # each stave is two or three boards end to end; every board picks its own tone and a different patch of grain
    cuts = sorted(rng.choice(np.arange(60, N - 60), size=rng.integers(1, 3), replace=False))
    joints = [0] + list(cuts) + [N]
    for j in range(len(joints) - 1):
        y0, y1 = joints[j], joints[j + 1]
        tone = target * (1 + rng.normal(0, 0.07)) * (1 + rng.normal(0, 0.01, 3))
        sx, sy = rng.integers(0, N - (b - a)), rng.integers(0, N)
        g = np.roll(grain, -sy, axis=0)[y0:y1, sx:sx + (b - a)]
        out[y0:y1, a:b] = tone[None, None, :] * (1 + 0.06 * g[..., None])
        out[y0:y0 + 2, a:b] *= 0.8                                   # butt joint line
    out[:, a:a + 2] *= 0.86                                            # glue line between staves
out *= target.mean() / out.reshape(-1, 3).mean(0).mean()
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(T, "butcher_block.jpg"), quality=88)
print("butcher_block.jpg", out.reshape(-1, 3).mean(0).round())
