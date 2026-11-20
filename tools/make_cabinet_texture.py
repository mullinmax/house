#!/usr/bin/env python3
"""Writes site/models/textures/cabinet_natural.jpg: the light natural wood of the kitchen cabinets in Danielle Gross's
11/19/2026 north wall rendering (Carter Lumber). It reuses the grain of white_oak.jpg, recoloured to that wood.

    python tools/make_cabinet_texture.py [R G B]       (mean colour of the texture, default 250 190 136)
"""
import os, sys
import numpy as np
from PIL import Image

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "models", "textures")
target = np.array([float(v) for v in sys.argv[1:4]] if len(sys.argv) >= 4 else [250, 190, 136])
src = np.asarray(Image.open(os.path.join(T, "white_oak.jpg")).convert("RGB")).astype(float)
lum = src @ [0.299, 0.587, 0.114]
grain = (lum - lum.mean()) / max(lum.std(), 1e-6)        # zero mean, unit spread
out = target[None, None, :] * (1 + 0.07 * grain[..., None])   # 7 % grain contrast, a little darker in the late wood
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(T, "cabinet_natural.jpg"), quality=88)
print("cabinet_natural.jpg", out.reshape(-1, 3).mean(0).round())
