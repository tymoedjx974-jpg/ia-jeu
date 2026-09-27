"""Vidéo de visite : on s'approche d'une maison, la porte s'ouvre, on entre (vue à la première personne)."""
import sys, os, pickle, math, time
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, scene
from modules import MODULE_BUILDERS
from common import grid_sample

HID = sys.argv[1] if len(sys.argv) > 1 else "a461b56b"
FPS = 12
ONLY = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
OUT = "renders/visite"
os.makedirs(OUT, exist_ok=True)
B = pickle.load(open("buildings_out.pkl", "rb"))
dr = next(d for d in B["doors"] if d["house"].startswith(HID))
G = np.load("terrain.npz")["ground"]
yaw = dr["yaw"]
u = np.array([math.cos(yaw), math.sin(yaw)])
inw = np.array([-u[1], u[0]])
mid = np.array([dr["x"], dr["y"]]) + u * 0.43
l0 = dr["z"]
bl.reset()
R = 40
bbox = (mid[0] - R, mid[1] - R, mid[0] + R, mid[1] + R)
scene.terrain_region(*bbox, step=1, name="Terrain")
scene.load_buildings("buildings_out.pkl", bbox)
scene.load_instances(B["inst"], bbox)
leaf = bl.mesh_object("Vantail", MODULE_BUILDERS[dr["leaf"]]().arrays(), location=(dr["x"], dr["y"], dr["z"]))
leaf.scale = (dr["sx"], 1, 1)
bl.setup_world(sun_elev=38, sun_azim=160, exposure=0.0)
bl.setup_render(960, 540, samples=int(os.environ.get("SAMPLES", 20)))
bpy.context.scene.cycles.max_bounces = 6
cam = bl.camera((0, 0, 0), (1, 0, 0), lens=18.0, name="Oeil")


def gz(p):
    return float(grid_sample(G, [p[0]], [p[1]])[0])


def side(k):
    """Point à k mètres devant la porte le long de l'axe d'entrée (k < 0 : dehors), décalé de 0 vers le côté."""
    return mid + inw * k


# trajectoire (temps s, position le long de l'axe, décalage latéral, cible regardée)
tgt_piano = (-1743.2, 2162.9)
tgt_horloge = (-1742.96, 2165.3)
tgt_cheminee = (-1737.0, 2163.0)
tgt_table = (-1739.3, 2170.7)
KEYS = [  # t, k (m depuis la porte), décalage latéral, cible (x, y, z relative au sol intérieur)
    (0.0, -5.0, 0.0, None),
    (3.0, -1.1, 0.0, None),
    (4.0, -0.9, 0.0, None),
    (6.0, 1.6, 0.0, None),
    (7.5, 3.0, 0.1, ("t", tgt_table, 0.9)),
    (9.0, 4.4, 0.1, ("t", tgt_horloge, 1.4)),
    (10.5, 5.2, 0.0, ("t", tgt_piano, 1.1)),
    (12.5, 5.6, 0.0, ("t", tgt_cheminee, 1.0)),
    (13.5, 5.6, 0.0, ("t", tgt_cheminee, 1.0)),
]
T_END = KEYS[-1][0]
OPEN0, OPEN1 = 2.3, 3.6         # la porte s'ouvre quand on arrive devant


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def at(t):
    for (t0, k0, s0, g0), (t1, k1, s1, g1) in zip(KEYS, KEYS[1:]):
        if t0 <= t <= t1:
            f = smooth((t - t0) / (t1 - t0))
            return t0, t1, f, (k0 + (k1 - k0) * f), (s0 + (s1 - s0) * f), g0, g1
    return KEYS[-1][0], KEYS[-1][0], 1.0, KEYS[-1][1], KEYS[-1][2], KEYS[-1][3], KEYS[-1][3]


def look_point(g, pos):
    if g is None:
        p = pos + inw * 4.0
        return np.array([p[0], p[1], l0 + 1.3])
    _, xy, h = g
    return np.array([xy[0], xy[1], l0 + h])


import mathutils
n = int(T_END * FPS) + 1
t_start = time.time()
for i in range(n):
    if ONLY and i not in ONLY:
        continue
    t = i / FPS
    t0, t1, f, k, lat, g0, g1 = at(t)
    pos = side(k) + u * lat
    # hauteur des yeux : sol extérieur dehors, sol de la maison dedans ; léger balancement de la marche
    z_ground = l0 if k > -0.3 else max(gz(pos), l0 - 1.2) + (l0 - max(gz(pos), l0 - 1.2)) * smooth((k + 1.5) / 1.2)
    moving = 1.0 if t < KEYS[-2][0] else 0.0
    bob = 0.025 * math.sin(2 * math.pi * 1.8 * t) * moving
    eye = np.array([pos[0], pos[1], z_ground + 1.65 + bob])
    la, lb = look_point(g0, pos), look_point(g1, pos)
    ff = smooth(f * 1.3)
    look = la + (lb - la) * ff
    cam.location = eye.tolist()
    cam.rotation_euler = (mathutils.Vector(look.tolist()) - mathutils.Vector(eye.tolist())).to_track_quat("-Z", "Y").to_euler()
    # porte
    o = smooth((t - OPEN0) / (OPEN1 - OPEN0))
    leaf.rotation_euler[2] = yaw + math.radians(100) * o
    # exposition : dehors en plein soleil, dedans plus sombre (comme l'adaptation de l'œil / l'exposition auto d'Unreal)
    bpy.context.scene.view_settings.exposure = 0.0 + 2.6 * smooth((k + 0.5) / 2.5)
    bpy.context.scene.render.filepath = os.path.abspath(f"{OUT}/f{i:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("image", i, "/", n, "%.0fs" % (time.time() - t_start), flush=True)
