"""Aperçu animé du vent et du passage d'un personnage : même calcul que le code HLSL du plugin (VPMaterials.cpp)."""
import sys, os, math
sys.path.insert(0, ".")
import numpy as np
import bl, bpy
import trees

FPV = len(sys.argv) > 2 and sys.argv[2] == "fps"
OUT = "renders/closeup"
os.makedirs(OUT, exist_ok=True)
FPS, NF = 12, int(sys.argv[1]) if len(sys.argv) > 1 else 48
W = dict(  # mêmes réglages que materials.WIND
    Lavande=dict(So=1.0, On=10.0, Fr=2.0, Fl=0.0), HerbeSeche=dict(So=1.0, On=14.0, Fr=2.0, Fl=0.0),
    HerbeVerte=dict(So=1.0, On=14.0, Fr=2.0, Fl=0.0), FeuillesGarrigue=dict(So=0.55, On=4.0, Fr=3.0, Fl=0.0),
    FeuillesOlivier=dict(So=0.25, On=0.0, Fr=5.0, Fl=1.0), EcorceOlivier=dict(So=0.0, On=0.0, Fr=0.0, Fl=1.0))


def sat(x):
    return np.clip(x, 0.0, 1.0)


def offset(P, B, H, A, R, T, F, D, p, inter):
    """Traduction ligne à ligne du code HLSL (unités : cm)."""
    wd = D / max(np.linalg.norm(D), 1e-3)
    wp = np.array([-wd[1], wd[0]])
    h = np.maximum(H, 0.0)
    hm = h * 0.01
    o = np.zeros_like(P)
    gb = np.sin(B[:, :2] @ wd * 0.0008 - T * 1.1) * np.sin(B[:, :2] @ wp * 0.0005 + T * 0.23)
    f = F * (0.8 + 0.35 * gb)
    s = p["Fl"] * f * 1.2 * hm ** 1.5 * (0.75 + 0.25 * np.sin(T * 4.0 / np.sqrt(np.maximum(hm, 1.0)) + R * 6.2832))
    o[:, :2] += wd[None] * s[:, None]
    o[:, 2] -= s * s / np.maximum(2.0 * h, 1.0)
    gp = P[:, :2] @ wd * 0.01
    wave = 0.55 + 0.45 * np.sin(gp * 0.45 - T * 2.4 + 0.8 * np.sin(P[:, :2] @ wp * 0.004))
    o[:, :2] += wd[None] * (p["On"] * A * f * wave)[:, None]
    ph = P @ np.array([0.031, 0.027, 0.043]) + R * 6.2832
    fr = p["Fr"] * A * (0.3 + f)
    o += fr[:, None] * np.column_stack([np.sin(T * 6.3 + ph) * 0.6, np.cos(T * 5.1 + ph * 1.3) * 0.6, np.sin(T * 7.7 + ph * 0.7) * 0.8])
    push = np.zeros_like(P)
    for I in inter:
        r = max(math.floor(I[3]), 1.0)
        st = I[3] - math.floor(I[3])
        d = P[:, :2] - I[None, :2]
        dl = np.linalg.norm(d, axis=1)
        fo = sat(1.0 - dl / r)
        fo = fo * (2.0 - fo)
        dz = P[:, 2] - I[2]
        fo *= st * sat((dz + 80.0) / 40.0) * sat((260.0 - dz) / 60.0)
        push[:, :2] += d / np.maximum(dl, 1.0)[:, None] * fo[:, None]
        push[:, 2] = np.maximum(push[:, 2], fo)
    pl = np.linalg.norm(push[:, :2], axis=1)
    k = sat(push[:, 2]) * p["So"] * sat(h / 60.0) * (1.0 - sat((h - 170.0) / 90.0))
    o[:, :2] += push[:, :2] / np.maximum(pl, 1e-3)[:, None] * (k * np.minimum(h, 100.0) * 0.85 * sat(pl * 4.0))[:, None]
    o[:, 2] -= k * h * 0.4
    return o


bl.reset()
bl.setup_world(sun_elev=30.0, sun_azim=235.0, exposure=-0.7)
bl.setup_render(1280, 720, samples=48)
bpy.context.scene.cycles.transparent_max_bounces = 64
cat = trees.catalog()
rng = np.random.default_rng(3)

# sol : terre sèche
g = 30
X, Y = np.meshgrid(np.linspace(-15, 15, g), np.linspace(-8, 22, g))
Pg = np.column_stack([X.ravel(), Y.ravel(), np.zeros(g * g)]).astype(np.float32)
idx = np.arange(g * g).reshape(g, g)
a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
Ig = np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, d])]).astype(np.int32)
Wt = np.zeros((g * g, 8), np.float32)
Wt[:, 1] = 0.7
Wt[:, 0] = 0.3
bl.mesh_object("Sol", {"Terrain": dict(P=Pg, N=np.tile([0, 0, 1.0], (g * g, 1)).astype(np.float32), UV=Pg[:, :2] / 4.0,
                                         C=np.full((g * g, 4), 255, np.uint8), I=Ig)}, terrain_weights=Wt)

plants = []  # (objet, P locaux, rotation, position, alpha, aléa, matériaux par sommet)


def place(name, pos, yaw):
    mb, _, _ = cat[name](0)
    arr = mb.arrays()
    ob = bl.mesh_object(f"{name}_{len(plants)}", arr, location=pos)
    mats = list(arr.keys())
    P = np.concatenate([arr[m]["P"] for m in mats]).astype(np.float64)
    A = np.concatenate([arr[m]["C"][:, 3] for m in mats]).astype(np.float64) / 255.0
    M = np.concatenate([[m] * len(arr[m]["P"]) for m in mats])
    cy, sy = math.cos(yaw), math.sin(yaw)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1.0]])
    plants.append((ob, P, Rz, np.array(pos, float), A, rng.random(), M))


# rangs de lavande le long de x, espacés de 1,6 m, herbes sèches entre les rangs, garrigue et un olivier au fond
for j in range(7):
    y = -1.5 + j * 1.6
    for i in range(-3, 4):
        place(f"Lavande_Rang_{(i + j) % 3}", (i * 4.0 + rng.normal(0, 0.1), y, 0.0), rng.normal(0, 0.03))
for k in range(90):
    place(f"Herbe_Seche_{k % 3}", (rng.uniform(-13, 13), rng.uniform(-3, 12), 0.0), rng.uniform(0, 6.28))
for k in range(5):
    place(f"Buisson_Garrigue_{k % 4}", (rng.uniform(-9, 9), rng.uniform(10, 13), 0.0), rng.uniform(0, 6.28))
place("Arbre_Olivier_1", (5.5, 15.0, 0.0), 0.7)
place("Arbre_Olivier_2", (-7.0, 17.0, 0.0), 2.1)

# personnage (capsule) qui traverse les rangs en courant
bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.2, location=(0, 0, 0.9))
body = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=(0, 0, 1.68))
head = bpy.context.object
mat = bpy.data.materials.new("Perso")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.45, 0.06, 0.04, 1)
for o_ in (body, head):
    o_.data.materials.append(mat)

cam = bl.camera((-3.5, -6.5, 4.8), (0.2, 3.0, 0.0), lens=30.0)
if FPV:
    # vue à la première personne : on ne voit pas son propre corps
    body.hide_render = head.hide_render = True
    cam.data.lens = 19.0

wind_dir = np.array([0.5, 0.866])  # mistral qui pousse vers le sud-sud-est (+y = sud dans le générateur ? ici repère local)
path0, path1 = np.array([-1.8, -3.2]), np.array([1.6, 7.5])
speed = 2.0
if FPV:
    path0, path1, speed = np.array([0.3, -4.5]), np.array([0.8, 5.5]), 1.45
trail = []
for fr_i in range(NF):
    T = fr_i / FPS
    L = np.linalg.norm(path1 - path0)
    t = min(1.0, T * speed / L)
    feet = np.append(path0 + (path1 - path0) * t, 0.0)
    body.location = (feet[0], feet[1], 0.9)
    head.location = (feet[0], feet[1], 1.68)
    if FPV:
        import mathutils
        fwd = (path1 - path0) / np.linalg.norm(path1 - path0)
        side = np.array([fwd[1], -fwd[0]])
        step = 2 * math.pi * 1.8 * T
        eye = np.array([*(feet[:2] + side * 0.025 * math.sin(step / 2)), 1.65 + 0.025 * math.sin(step)])
        look = np.array([*(feet[:2] + fwd * 4.0 + side * 0.15 * math.sin(T * 0.7)), 0.25])
        cam.location = eye.tolist()
        cam.rotation_euler = (mathutils.Vector(look.tolist()) - mathutils.Vector(eye.tolist())).to_track_quat("-Z", "Y").to_euler()
    if not trail or np.linalg.norm(trail[-1][0] - feet) > 0.3:
        trail.append((feet.copy(), T))
    trail = [(p_, t_) for p_, t_ in trail if T - t_ < 3.0][-6:]
    R = 55.0
    inter = [np.array([*(feet * 100), R + 0.99])]
    for p_, t_ in trail:
        st = 0.9 * math.exp(-(T - t_) / 1.2)
        if st >= 0.08 and np.linalg.norm(p_[:2] - feet[:2]) * 100 >= R * 0.5:
            inter.append(np.array([*(p_ * 100), math.floor(R * 0.9) + min(st, 0.99)]))
    inter = inter[:16]
    F = 0.6 * (1 + 0.6 * (0.5 + 0.5 * math.sin(T * 0.9)) - 0.3)
    for ob, P, Rz, pos, A, rnd, M in plants:
        Pl = P * 100.0
        Pw_rel = Pl @ Rz.T
        Pw = Pw_rel + pos * 100.0
        B = np.repeat((pos * 100.0)[None], len(P), axis=0)
        o = np.zeros_like(Pw)
        for m in np.unique(M):
            sel = M == m
            o[sel] = offset(Pw[sel], B[sel], Pl[sel, 2], A[sel], rnd, T, F, wind_dir, W.get(m, W["HerbeSeche"]), inter)
        new_local = ((Pw_rel + o) / 100.0) @ Rz
        ob.data.vertices.foreach_set("co", new_local.astype(np.float32).ravel())
        ob.data.update()
    ob_loc = bpy.context.scene
    bpy.context.scene.render.filepath = os.path.abspath(f"{OUT}/f{fr_i:03d}.png")
    bpy.ops.render.render(write_still=True)
    print("image", fr_i, flush=True)
