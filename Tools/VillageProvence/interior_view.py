"""Rendus d'intérieur d'une maison visitable : rez-de-chaussée et étage."""
import sys, pickle, math, time
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, scene

src = sys.argv[1] if len(sys.argv) > 1 else "buildings_core.pkl"
hid = sys.argv[2] if len(sys.argv) > 2 else None
B = pickle.load(open(src, "rb"))
v = next((x for x in B["visit"] if hid is None or x["id"].startswith(hid)), B["visit"][0])
pl = v["plan"]
c, a = np.array(pl["c"]), np.array(pl["a"])
q = np.array([-a[1], a[0]])
L, W, s, d, end, xc = pl["L"], pl["W"], pl["s"], pl["d"], pl["end"], pl["xc"]
l0, l1 = pl["l0"], pl["l1"]
Wp = lambda x, y: c + x * a + y * q
bl.reset()
R = 45
bbox = (c[0] - R, c[1] - R, c[0] + R, c[1] + R)
scene.terrain_region(*bbox, step=1, name="Terrain")
_, objs = scene.load_buildings(src, bbox)
scene.load_instances(B["inst"], bbox)
bl.setup_world(sun_elev=28, sun_azim=235, exposure=float(sys.argv[3]) if len(sys.argv) > 3 else 3.0)
bl.setup_render(1280, 720, samples=32)
bpy.context.scene.cycles.max_bounces = 8
far = -end
views = {
    "int_rdc": (Wp(far - d * 0.45, -s * (W / 2 - 0.45)), l0 + 1.6, Wp(end + d * 1.0, s * 0.2), l0 + 1.0, 16),
    "int_etage": (Wp(xc + d * 0.4, -s * (W / 2 - 0.4)), l1 + 1.6, Wp(far - d * 0.6, s * 0.5), l1 + 0.6, 16),
    "int_escalier": (Wp(far - d * 0.8, s * (W / 2 - 1.5)), l0 + 1.5, Wp(end + d * 1.2, s * (W / 2 - 0.5)), l0 + 2.2, 18),
    "int_cuisine": (Wp(far - d * 3.3, s * 0.3), l0 + 1.6, Wp(far - d * 0.6, -s * (W / 2 - 0.3)), l0 + 0.9, 18),
    "int_sdb": (Wp(xc - d * 0.15, pl["band"][0] - s * 0.65 if s > 0 else pl["band"][1] - s * 0.65), l1 + 1.6, Wp(end + d * 0.4, -s * (W / 2 - 0.4)), l1 + 0.7, 16),
}
only = sys.argv[4].split(",") if len(sys.argv) > 4 else None
views = {k: v for k, v in views.items() if only is None or k in only}
for name, (p0, z0, p1, z1, lens) in views.items():
    bl.camera((p0[0], p0[1], z0), (p1[0], p1[1], z1), lens=lens, name=name)
    t = time.time()
    bl.render(f"renders/{name}.png")
    print(name, "%.0fs" % (time.time() - t), flush=True)
