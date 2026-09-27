"""Aperçus du village envahi : rue, camp de survivants, toits (planches, échelles), barrage."""
import sys, pickle, math, time
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, scene
from trees import catalog
from modules_zombie import ZOMBIE_BUILDERS
from common import grid_sample
from shapely.geometry import Point

T0 = time.time()
G = np.load("terrain.npz")["ground"]
gz = lambda x, y: float(grid_sample(G, [x], [y])[0])
V = pickle.load(open("vec.pkl", "rb"))
Z = pickle.load(open("envahi_out.pkl", "rb"))


def road_dir(x, y):
    p = Point(x, y)
    r = min(V["roads"], key=lambda r: r["line"].distance(p))
    ln = r["line"]
    s = ln.project(p)
    a, b = ln.interpolate(max(0, s - 2)), ln.interpolate(min(ln.length, s + 2))
    t = np.array([b.x - a.x, b.y - a.y])
    return np.array([ln.interpolate(s).x, ln.interpolate(s).y]), t / np.linalg.norm(t)


def view(name):
    if name == "rue_envahie":
        c, t = road_dir(90.6, -147.7)
        cam = c - t * 11 + np.array([-t[1], t[0]]) * 1.0
        tgt = c + t * 6
        return (cam[0], cam[1], gz(*cam) + 1.7), (tgt[0], tgt[1], gz(*tgt) + 1.3), 20
    if name == "camp":
        cx, cy = next((r["x"], r["y"]) for r in Z["route"] if r["kind"] == "camp")
        return (cx - 8.5, cy - 7.0, gz(cx - 8.5, cy - 7.0) + 1.7), (cx + 1.0, cy + 0.5, gz(cx, cy) + 0.9), 18
    if name == "barrage":
        bx, by = next((r["x"], r["y"]) for r in Z["route"] if r["kind"] == "barrage")
        c, t = road_dir(bx, by)
        # on arrive de l'extérieur du village
        if np.dot(t, np.array([-10 - bx, 20 - by])) < 0:
            t = -t
        cam = c + t * 9 + np.array([-t[1], t[0]]) * 3.5
        tgt = c - t * 8
        return (cam[0], cam[1], gz(*cam) + 2.3), (tgt[0], tgt[1], gz(*tgt) + 0.6), 20
    if name == "facade":
        c, t = road_dir(-34.6, -33.8)
        cam = c - t * 9 + np.array([-t[1], t[0]]) * 0.8
        tgt = c + t * 4
        return (cam[0], cam[1], gz(*cam) + 1.7), (tgt[0], tgt[1], gz(*tgt) + 2.0), 18
    if name == "depart":
        d = [r for r in Z["route"] if r["kind"] == "depart"]
        d.sort(key=lambda r: math.hypot(r["x"] + 10, r["y"] - 20))
        r = d[0]
        p = np.array([r["x"], r["y"]])
        k = min(range(len(V["buildings"])), key=lambda i: V["buildings"][i]["poly"].distance(Point(*p)))
        cen = V["buildings"][k]["poly"].centroid
        out = p - np.array([cen.x, cen.y])
        out /= np.linalg.norm(out)
        cam = p + out * 7.5 + np.array([-out[1], out[0]]) * 2.5
        return (cam[0], cam[1], gz(*cam) + 1.7), (p[0], p[1], gz(*p) + 1.8), 20
    if name == "aerien":
        return (-95.0, -95.0, gz(-10, 20) + 55.0), (-5.0, 15.0, gz(-10, 20) + 2.0), 30
    if name == "toits":
        p = [r for r in Z["route"] if r["kind"] == "planche"]
        p.sort(key=lambda r: math.hypot(r["x"] + 10, r["y"] - 20))
        a = p[1]
        b = p[0]
        d = np.array([b["x"] - a["x"], b["y"] - a["y"]])
        d /= np.linalg.norm(d)
        side = np.array([-d[1], d[0]])
        cam = np.array([a["x"], a["y"]]) - d * 4.0 + side * 3.0
        return (cam[0], cam[1], a["z"] + 4.5), (b["x"] + d[0] * 3, b["y"] + d[1] * 3, b["z"] - 0.5), 16
    raise KeyError(name)


name = sys.argv[1]
loc, look, lens = view(name)
bl.reset()
R = 260.0
bbox = (loc[0] - R, loc[1] - R, loc[0] + R, loc[1] + R)
scene.terrain_region(*bbox, step=1, name="Terrain")
t2 = scene.terrain_region(-2200, -1800, 1800, 2200, step=8, name="TerrainLoin")
t2.location.z = -0.4
far = pickle.load(open("far_out.pkl", "rb"))
bl.mesh_object("Horizon", far)
B, objs = scene.load_buildings("buildings_out.pkl", bbox)
R_ = pickle.load(open("roads_out.pkl", "rb"))
for k, arr in R_.items():
    kx, ky = (k[0] + 0.5) * 128, (k[1] + 0.5) * 128
    if bbox[0] - 128 < kx < bbox[2] + 128 and bbox[1] - 128 < ky < bbox[3] + 128 and arr:
        bl.mesh_object(f"Route_{k[0]}_{k[1]}", arr)
M = pickle.load(open("mobilier_out.pkl", "rb"))
for k, arr in M["chunks"].items():
    if arr:
        bl.mesh_object(f"Mob_{k[0]}_{k[1]}", arr)
scene.load_instances(B["inst"], bbox)
scene.load_instances(M["inst"], bbox)
zb = {k: (lambda k=k: ZOMBIE_BUILDERS[k]()) for k in ZOMBIE_BUILDERS}
scene.load_instances(Z["inst"], bbox, builders=zb)
N = pickle.load(open("nature_out.pkl", "rb"))
C = catalog()
scene.load_instances(N, bbox, builders={k: (lambda k=k: C[k](0)[0]) for k in C})
print("scène %.0fs" % (time.time() - T0), flush=True)
bl.setup_world(sun_elev=22, sun_azim=250, exposure=-0.6)
bl.setup_render(1280, 720, samples=40)
bl.haze()
bpy.context.scene.cycles.max_bounces = 4
bpy.context.scene.cycles.transparent_max_bounces = 64
bl.camera(loc, look, lens=lens, name="Cam")
bl.render(f"renders/{name}.png")
print(name, "%.0fs" % (time.time() - T0), flush=True)
