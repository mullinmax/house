"""Downscale the images embedded in a .glb before gltfpack.

    python tools/shrink_textures.py in.glb out.glb --max 1024

Images larger than --max on their long side are resized. Opaque PNGs are re-encoded as JPEG
(quality 85); images with real alpha stay PNG. Buffer views are repacked, everything else is kept.
"""
import argparse, io, json, struct
from PIL import Image


def read_glb(path):
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + n])
    off = 20 + n
    bl = struct.unpack('<I', b[off:off + 4])[0]
    return j, bytearray(b[off + 8:off + 8 + bl])


def write_glb(path, j, binbuf):
    js = json.dumps(j, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    binbuf += b'\0' * ((4 - len(binbuf) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binbuf)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack('<II', len(binbuf), 0x004E4942)); f.write(binbuf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--max', type=int, default=1024)
    a = ap.parse_args()
    j, buf = read_glb(a.src)
    views = j['bufferViews']
    img_views = {im['bufferView']: im for im in j.get('images', []) if 'bufferView' in im}
    before = after = 0
    new = bytearray()
    for i, v in enumerate(views):
        data = bytes(buf[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']])
        if i in img_views:
            im = img_views[i]
            before += len(data)
            pic = Image.open(io.BytesIO(data)); pic.load()
            w, h = pic.size
            if max(w, h) > a.max:
                s = a.max / max(w, h)
                pic = pic.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
            has_alpha = pic.mode in ('RGBA', 'LA') and pic.getchannel('A').getextrema()[0] < 250
            out = io.BytesIO()
            if has_alpha:
                pic.save(out, 'PNG', optimize=True); im['mimeType'] = 'image/png'
            else:
                pic.convert('RGB').save(out, 'JPEG', quality=85, optimize=True); im['mimeType'] = 'image/jpeg'
            if out.tell() < len(data) or max(w, h) > a.max or im['mimeType'] != 'image/png':
                data = out.getvalue()
            after += len(data)
        while len(new) % 4: new += b'\0'
        v['byteOffset'] = len(new); v['byteLength'] = len(data)
        new += data
    j['buffers'][0]['byteLength'] = len(new)
    write_glb(a.dst, j, new)
    print(f'{a.src}: images {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
