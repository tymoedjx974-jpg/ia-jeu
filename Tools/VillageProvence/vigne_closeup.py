"""Aperçu rapproché d'une vigne palissée (rangs, feuillage, grappes, piquets et fils)."""
import sys, os, math
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, trees
bl.reset()
bl.setup_world(sun_elev=40.0, sun_azim=140.0, exposure=-0.3)
bl.setup_render(1280, 720, samples=48)
bpy.context.scene.cycles.transparent_max_bounces = 64
cat = trees.catalog()
rng = np.random.default_rng(5)
g = 40
X, Y = np.meshgrid(np.linspace(-30, 30, g), np.linspace(-10, 60, g))
Pg = np.column_stack([X.ravel(), Y.ravel(), np.zeros(g * g)]).astype(np.float32)
idx = np.arange(g * g).reshape(g, g)
a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
Ig = np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, d])]).astype(np.int32)
Wt = np.zeros((g * g, 8), np.float32); Wt[:, 1] = 0.55; Wt[:, 0] = 0.3; Wt[:, 5] = 0.15
bl.mesh_object("Sol", {"Terrain": dict(P=Pg, N=np.tile([0, 0, 1.0], (g * g, 1)).astype(np.float32), UV=Pg[:, :2] / 4.0,
                                         C=np.full((g * g, 4), 255, np.uint8), I=Ig)}, terrain_weights=Wt)
n = 0
protos = {}
def place(name, pos, yaw):
    global n
    if name not in protos:
        mb, _, _ = cat[name](0)
        protos[name] = mb.arrays()
    ob = bl.mesh_object(f"{name}_{n}", protos[name], location=pos)
    ob.rotation_euler[2] = yaw; n += 1
# rangs le long de y, espacés de 2,3 m
for j in range(-5, 6):
    for k in range(12):
        place(f"Vigne_Rang_{(j + k) % 3}", (j * 2.3, -4 + k * 4.8, 0), math.pi / 2)
for k in range(220):
    place(f"Herbe_Seche_{k % 3}", (rng.uniform(-12, 12), rng.uniform(-4, 50), 0), rng.uniform(0, 6.28))
if "loin" in sys.argv[1:]:
    bl.camera((-18.0, -14.0, 9.0), (2.0, 20.0, 0.5), lens=30.0)
    bl.render("renders/vignes_loin.png")
else:
    bl.camera((1.15, -3.0, 1.55), (0.6, 8.0, 0.9), lens=24.0)
    bl.render("renders/vignes_pres.png")
