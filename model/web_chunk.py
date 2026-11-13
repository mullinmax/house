"""Split web/*.glb into base64 text chunks (artifacts don't serve .glb) + an index with sha256 so they can be rebuilt:
   python web_chunk.py OUTDIR
Rebuild:  for each entry in glb_chunks.json: b"".join(base64.b64decode(open(chunk).read()) for chunk in entry["chunks"])"""
import base64, hashlib, json, os, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
CH = 8_000_000          # raw bytes per chunk -> ~10.7 MB of base64 text
idx = {}
for f in sorted(os.listdir(D)):
    if not f.endswith(".glb"):
        continue
    b = open(os.path.join(D, f), "rb").read()
    parts = []
    for k in range(0, len(b), CH):
        nm = f"{f}.part{k // CH:02d}.b64.txt"
        open(os.path.join(OUT, nm), "w").write(base64.b64encode(b[k:k + CH]).decode())
        parts.append(nm)
    idx[f] = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), "chunks": parts}
json.dump({"how": "concatenate base64-decoded chunks in order; check sha256", "files": idx}, open(os.path.join(OUT, "glb_chunks.json"), "w"), indent=1)
print(json.dumps({k: (v["bytes"], len(v["chunks"])) for k, v in idx.items()}))
