"""Aperçu rapproché d'une oliveraie (feuillage argenté et olives)."""
import sys, os, math
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, trees
bl.reset()
bl.setup_world(sun_elev=38.0, sun_azim=150.0, exposure=-0.3)
bl.setup_render(1280, 720, samples=48)
bpy.context.scene.cycles.transparent_max_bounces = 64
cat = trees.catalog()
rng = np.random.default_rng(5)
g = 40
X, Y = np.meshgrid(np.linspace(-25, 25, g), np.linspace(-10, 40, g))
Pg = np.column_stack([X.ravel(), Y.ravel(), np.zeros(g * g)]).astype(np.float32)
idx = np.arange(g * g).reshape(g, g)
a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
Ig = np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, d])]).astype(np.int32)
Wt = np.zeros((g * g, 8), np.float32); Wt[:, 1] = 0.6; Wt[:, 0] = 0.4
bl.mesh_object("Sol", {"Terrain": dict(P=Pg, N=np.tile([0, 0, 1.0], (g * g, 1)).astype(np.float32), UV=Pg[:, :2] / 4.0,
                                         C=np.full((g * g, 4), 255, np.uint8), I=Ig)}, terrain_weights=Wt)
n = 0
def place(name, pos, yaw, s=1.0):
    global n
    mb, _, _ = cat[name](0)
    ob = bl.mesh_object(f"{name}_{n}", mb.arrays(), location=pos)
    ob.rotation_euler[2] = yaw; ob.scale = (s, s, s); n += 1
for j in range(4):
    for i in range(-2, 3):
        place(f"Arbre_Olivier_{(i + j) % 4}", (i * 7.5 + rng.normal(0, 0.6) + (j % 2) * 3.7, 3 + j * 7.5 + rng.normal(0, 0.6), 0), rng.uniform(0, 6.28), rng.uniform(0.9, 1.2))
for k in range(160):
    place(f"Herbe_Seche_{k % 3}", (rng.uniform(-20, 20), rng.uniform(-6, 30), 0), rng.uniform(0, 6.28))
if "pied" in sys.argv[1:]:
    # gros plan sur le pied de l'olivier le plus proche
    bl.camera((-1.0, 0.9, 1.0), (0.45, 3.98, 0.45), lens=28.0)
    bl.render("renders/oliviers_pied.png")
else:
    bl.camera((-2.2, -3.0, 1.7), (1.5, 6.0, 2.6), lens=24.0)
    bl.render("renders/oliviers.png")
