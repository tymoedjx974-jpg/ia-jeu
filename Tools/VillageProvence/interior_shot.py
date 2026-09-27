"""Rendu d'un intérieur quelconque (maison, plain-pied, commerce) : vue en diagonale depuis un angle de la pièce.

    python interior_shot.py <id> <niveau 0/1/2> <angle 0-3> [sortie.png] [exposition]
"""
import sys, pickle, math
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, scene

hid, lev, corner = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
out = sys.argv[4] if len(sys.argv) > 4 else "renders/interieur.png"
expo = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
B = pickle.load(open("buildings_out.pkl", "rb"))
v = next(x for x in B["visit"] if x["id"].startswith(hid))
pl = v["plan"]
c, a = np.array(pl["c"]), np.array(pl["a"])
q = np.array([-a[1], a[0]])
L, W = pl["L"], pl["W"]
z = pl["lv"][lev] if "lv" in pl else pl["l0"]
Wp = lambda x, y: c + x * a + y * q
bl.reset()
R = 35
bbox = (c[0] - R, c[1] - R, c[0] + R, c[1] + R)
scene.terrain_region(*bbox, step=1, name="Terrain")
scene.load_buildings("buildings_out.pkl", bbox)
scene.load_instances(B["inst"], bbox)
bl.setup_world(sun_elev=35, sun_azim=200, exposure=expo)
bl.setup_render(1280, 720, samples=28)
bpy.context.scene.cycles.max_bounces = 8
if corner < 0 and pl.get("entree"):
    # depuis la porte d'entrée, vers l'intérieur
    ex, ey, dx, dy = pl["entree"]
    p0 = Wp(ex + dx * 0.9, ey + dy * 0.9)
    p1 = Wp(ex + dx * 6.0, ey + dy * 6.0)
else:
    sx, sy = [(-1, -1), (1, 1), (-1, 1), (1, -1)][corner]
    p0 = Wp(sx * (L / 2 - 0.45), sy * (W / 2 - 0.45))
    p1 = Wp(-sx * (L / 2 - 0.8), -sy * (W / 2 - 0.8))
bl.camera((p0[0], p0[1], z + 1.65), (p1[0], p1[1], z + 0.8), lens=15)
bl.render(out)
