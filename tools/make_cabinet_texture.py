#!/usr/bin/env python3
"""Writes site/models/textures/cabinet_natural.jpg: the light natural wood of the kitchen cabinets in Danielle Gross's
11/19/2026 north wall rendering (Carter Lumber). It reuses the grain of white_oak.jpg, recoloured to that wood.

    python tools/make_cabinet_texture.py [R G B [name contrast]]   (mean colour, default 250 190 136)

Also makes vanity_oak.jpg, the washed light oak of the Moreno Bath VIV 72 master vanity (Maxwell 11/28/2026), sampled
from the listing photos:  python tools/make_cabinet_texture.py 192 175 144 vanity_oak.jpg 0.10
"""
import os, sys
import numpy as np
from PIL import Image

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "models", "textures")
target = np.array([float(v) for v in sys.argv[1:4]] if len(sys.argv) >= 4 else [250, 190, 136])
src = np.asarray(Image.open(os.path.join(T, "white_oak.jpg")).convert("RGB")).astype(float)
lum = src @ [0.299, 0.587, 0.114]
grain = (lum - lum.mean()) / max(lum.std(), 1e-6)        # zero mean, unit spread
name = sys.argv[4] if len(sys.argv) >= 5 else "cabinet_natural.jpg"
contrast = float(sys.argv[5]) if len(sys.argv) >= 6 else 0.07
out = target[None, None, :] * (1 + contrast * grain[..., None])   # 7 % grain contrast, a little darker in the late wood
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(T, name), quality=88)
print(name, out.reshape(-1, 3).mean(0).round())
