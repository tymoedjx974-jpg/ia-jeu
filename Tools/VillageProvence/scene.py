"""Assemble une région du village dans Blender (terrain, routes, bâtiments, instances, végétation)."""
import sys, os, pickle, math
sys.path.insert(0, ".")
import numpy as np
import bl, bpy
from common import ZONE, RES, NX, NY, XS, YS

_proto = {}


def terrain_region(x0, y0, x1, y1, step=1, name="Terrain", skirt=True):
    d = np.load("terrain.npz")
    g, sp = d["ground"], d["splat"]
    i0 = max(0, int((x0 - ZONE["xmin"]) / RES)); i1 = min(NX - 1, int((x1 - ZONE["xmin"]) / RES))
    j0 = max(0, int((y0 - ZONE["ymin"]) / RES)); j1 = min(NY - 1, int((y1 - ZONE["ymin"]) / RES))
    ii = np.arange(i0, i1 + 1, step)
    jj = np.arange(j0, j1 + 1, step)
    X, Y = np.meshgrid(XS[ii], YS[jj])
    Z = g[np.ix_(jj, ii)]
    W = sp[np.ix_(jj, ii)].astype(np.float32) / 255.0
    if "shade" in d.files:
        W *= d["shade"][np.ix_(jj, ii)].astype(np.float32)[..., None]
    ny, nx = Z.shape
    P = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]).astype(np.float32)
    gy, gx = np.gradient(Z, RES * step)
    N = np.column_stack([-gx.ravel(), -gy.ravel(), np.ones(nx * ny)])
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    UV = np.column_stack([X.ravel() / 4.0, -Y.ravel() / 4.0]).astype(np.float32)
    idx = np.arange(nx * ny).reshape(ny, nx)
    a, b, c, dd = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    I = np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, dd])]).astype(np.int32)
    C = np.full((nx * ny, 4), 255, np.uint8)
    arr = {"Terrain": dict(P=P, N=N.astype(np.float32), UV=UV, C=C, I=I)}
    return bl.mesh_object(name, arr, terrain_weights=W.reshape(-1, 8))


def load_buildings(path, bbox=None):
    with open(path, "rb") as f:
        B = pickle.load(f)
    objs = []
    for k, arr in B["chunks"].items():
        if not arr:
            continue
        if bbox:
            cx, cy = (k[0] + 0.5) * 128, (k[1] + 0.5) * 128
            if not (bbox[0] - 128 < cx < bbox[2] + 128 and bbox[1] - 128 < cy < bbox[3] + 128):
                continue
        objs.append(bl.mesh_object(f"Bati_{k[0]}_{k[1]}", arr))
    for k, (arr, c) in B["specials"].items():
        objs.append(bl.mesh_object(k, arr))
    return B, objs


def proto(name, builder=None):
    if name in _proto:
        return _proto[name]
    if builder is None:
        from modules import MODULE_BUILDERS
        from modules_zombie import ZOMBIE_BUILDERS
        builder = MODULE_BUILDERS.get(name) or ZOMBIE_BUILDERS[name]
    arr = builder() if callable(builder) else builder
    if hasattr(arr, "arrays"):
        arr = arr.arrays()
    ob = bl.mesh_object("proto_" + name, arr)
    ob.hide_render = True
    ob.hide_viewport = True
    _proto[name] = ob
    return ob


def load_instances(inst, bbox=None, builders=None):
    for name, a in inst.items():
        a = np.asarray(a, np.float32)
        if len(a) == 0:
            continue
        if bbox:
            m = (a[:, 0] > bbox[0]) & (a[:, 0] < bbox[2]) & (a[:, 1] > bbox[1]) & (a[:, 1] < bbox[3])
            a = a[m]
            if len(a) == 0:
                continue
        pr = proto(name, (builders or {}).get(name))
        tints = a[:, 7:10] / 255.0 if a.shape[1] >= 10 else None
        bl.instance_points("I_" + name, pr, a[:, 0:3], a[:, 3], scales=a[:, 4:7], tints=tints)
