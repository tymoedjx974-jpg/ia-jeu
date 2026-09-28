"""Rendus d'aperçu de la scène complète (Cycles)."""
import sys, os, pickle, math, time
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, scene
from trees import catalog

T0 = time.time()
from common import grid_sample
_G = np.load("terrain.npz")["ground"]


def _z(x, y, h):
    return float(grid_sample(_G, [x], [y])[0]) + h


# nom : ((x, y, hauteur au-dessus du sol), (x, y, hauteur de la cible), focale)
_V = {
    "vue_generale": ((-620, 330, 90), (-10, 20, 8), 30),
    "aerien_village": ((250, -310, 210), (-15, 20, 5), 30),
    "aerien_ceinture": ((620, -900, 480), (-80, 30, 0), 24),
    "quartier_ocres": ((585.2, -115.3, 1.7), (579.6, -85.8, 3.0), 22),
    "grand_pont": ((208.8, -52.6, 8.1), (306.8, -153.4, 70.0), 18),
    "gorges": ((251.0, 72.0, 51.6), (336.3, -141.6, 79.3), 24),
    "sol_couches": ((200.0, -214.0, 1.4), (212.0, -200.0, 0.1), 24),
    "tache": ((-300.0, 300.0, 40.0), (-10.0, 280.0, 0.0), 28),
    "borie": ((-333.0, -100.0, 1.7), (-321.5, -88.9, 2.2), 26),
    "mas_lavande": ((-470, 40, 2.0), (-330, -10, 10), 30),
    "lavande_village": ((-360, 290, 1.8), (-60, 80, 14), 30),
    "place": ((-8.5, 16.0, 1.65), (6, 6, 2.5), 20),
    "eglise": ((-4.0, 36.0, 1.65), (-40, 58, 6), 20),
    "lavande": ((-1050, 945, 1.6), (-15, 15, 16), 55),
    "ocres": ((520, -540, 28), (400, -320, 2), 24),
    "vignes": ((22, 1318, 2.2), (-15, 15, 14), 50),
    "relief": ((265, 425, 1.8), (175, 330, 0.5), 24),
}
VIEWS = {k: ((a[0], a[1], _z(a[0], a[1], a[2])), (b[0], b[1], _z(b[0], b[1], b[2])), f) for k, (a, b, f) in _V.items()}
views = [v for v in sys.argv[1:] if v in VIEWS] or ["vue_generale"]
samples = 40
bl.reset()
cx, cy = np.mean([VIEWS[v][0][0] for v in views] + [VIEWS[v][1][0] for v in views]), np.mean([VIEWS[v][0][1] for v in views] + [VIEWS[v][1][1] for v in views])
RAD = 1300.0
bbox = (cx - RAD, cy - RAD, cx + RAD, cy + RAD)
# terrain détaillé autour de la vue, grossier ailleurs, horizon lointain
scene.terrain_region(*bbox, step=1, name="Terrain")
t2 = scene.terrain_region(-2200, -1800, 1800, 2200, step=6, name="TerrainLoin")
t2.location.z = -0.35
far = pickle.load(open("far_out.pkl", "rb"))
bl.mesh_object("Horizon", far)
print("terrain %.0fs" % (time.time() - T0), flush=True)
B, objs = scene.load_buildings("buildings_out.pkl", bbox)
R = pickle.load(open("roads_out.pkl", "rb"))
for k, arr in R.items():
    kx, ky = (k[0] + 0.5) * 128, (k[1] + 0.5) * 128
    if bbox[0] - 128 < kx < bbox[2] + 128 and bbox[1] - 128 < ky < bbox[3] + 128 and arr:
        bl.mesh_object(f"Route_{k[0]}_{k[1]}", arr)
M = pickle.load(open("mobilier_out.pkl", "rb"))
for k, arr in M["chunks"].items():
    if arr:
        bl.mesh_object(f"Mob_{k[0]}_{k[1]}", arr)
scene.load_instances(B["inst"], bbox)
scene.load_instances(M["inst"], bbox)
print("bâti %.0fs" % (time.time() - T0), flush=True)
N = pickle.load(open("nature_out.pkl", "rb"))
C = catalog()
builders = {k: (lambda k=k: C[k](0)[0]) for k in C}
scene.load_instances(N, bbox, builders=builders)
print("végétation %.0fs" % (time.time() - T0), flush=True)
bl.setup_world(sun_elev=int(os.environ.get("SUN_ELEV", 24)), sun_azim=int(os.environ.get("SUN_AZIM", 250)))
# légère brume atmosphérique pour la profondeur
w = bpy.context.scene.world
bl.setup_render(1280, 720, samples=samples)
bl.haze()
bpy.context.scene.cycles.max_bounces = 4
bpy.context.scene.cycles.transparent_max_bounces = 64
for v in views:
    loc, look, lens = VIEWS[v]
    bl.camera(loc, look, lens=lens, name="Cam_" + v)
    t = time.time()
    bl.render(f"renders/{v}.png")
    print(v, "rendu en %.0fs" % (time.time() - t), flush=True)
