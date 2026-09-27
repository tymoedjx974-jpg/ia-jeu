"""Textures PBR provençales générées procéduralement (aucune image externe, libres de droits)."""
import sys, os, time
sys.path.insert(0, ".")
from texlib import *

OUT = "tex"
TEX = {}  # nom -> dict(size_m=..., n=...)


def register(name, size_m, n):
    def deco(fn):
        TEX[name] = dict(fn=fn, size_m=size_m, n=n)
        return fn
    return deco


# ------------------------------------------------------------------ pierre
LIMESTONE = [hex2rgb(h) for h in ("#cbbb9c", "#c0b4a1", "#d3c09a", "#b9a78b", "#c8ad84", "#aa9e8e", "#d9cfb8", "#bca88a",
                                   "#c79a6a", "#9f968a", "#b58f66", "#dcc7a1")]


def rubble(n, size, seed, cmin=0.09, cmax=0.24, wmin=0.12, wmax=0.5, palette=LIMESTONE, joint=(0.006, 0.02)):
    px = size / n
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * px
    wy = noise(n, n / 2, seed + 1, beta=3.5) * 0.018
    wx = noise(n, n / 2, seed + 3, beta=3.5) * 0.018
    Y = (yy + wy) % size
    X = (xx + wx) % size
    hs, t = [], 0.0
    while t < size:
        h = rng.uniform(cmin, cmax)
        hs.append(h)
        t += h
    hs = np.array(hs) * size / t
    starts = np.concatenate([[0], np.cumsum(hs)[:-1]])
    row = np.clip(np.searchsorted(starts, Y, side="right") - 1, 0, len(hs) - 1)
    ID = np.zeros((n, n), np.int64)
    for r in range(len(hs)):
        ws, t = [], 0.0
        while t < size:
            w = rng.uniform(wmin, wmax) * (0.6 + 0.4 * hs[r] / 0.2)
            ws.append(w)
            t += w
        ws = np.array(ws) * size / t
        bs = np.concatenate([[0], np.cumsum(ws)[:-1]])
        off = rng.uniform(0, size)
        m = row == r
        xr = (X[m] + off) % size
        col = np.searchsorted(bs, xr, side="right") - 1
        ID[m] = r * 1000 + col
    # relabel compact
    _, ID = np.unique(ID, return_inverse=True)
    ID = ID.reshape(n, n)
    d = edt_wrap(~edges_of(ID)) * px
    d = np.maximum(d + band(n, n / 22, seed + 2, width=0.5) * 0.006 + band(n, n / 70, seed + 4, width=0.5) * 0.0015, 0)
    jr = rand_per_id(ID, seed + 5)
    j = joint[0] + (joint[1] - joint[0]) * jr + band(n, n / 30, seed + 6) * 0.003
    maxd = ndimage.maximum(d, ID, index=np.arange(ID.max() + 1)).astype(F32)[ID]
    dn = np.clip(d / np.maximum(maxd, 1e-4), 0, 1)
    bulge = (0.008 + 0.022 * rand_per_id(ID, seed + 7)) * np.sqrt(dn)
    edge = smooth(j, j + 0.025 + 0.02 * rand_per_id(ID, seed + 8), d)
    surf = band(n, n / 60, seed + 9) * 0.0025 + band(n, 8, seed + 10) * 0.0007 + noise(n, 3, seed + 11) * 0.0002
    stone = (d > j).astype(F32)
    h = stone * (0.012 * edge + bulge + surf) + (1 - stone) * (noise(n, n / 50, seed + 12) * 0.0015 - 0.004)
    col = palette_pick(ID, palette, seed + 13)
    bright = 0.9 + 0.2 * rand_per_id(ID, seed + 14)
    var = 1 + 0.06 * noise(n, n / 20, seed + 15) + 0.04 * band(n, 6, seed + 16)
    alb = col * (bright * var)[..., None]
    alb *= (0.72 + 0.28 * edge)[..., None]
    # mortier de chaux sableux : grains, légèrement sali dans les creux
    grains = noise(n, 2, seed + 23) * 0.06
    mortar = hex2rgb("#d2c7b0") * (0.88 + 0.08 * noise(n, n / 30, seed + 17) + grains)[..., None]
    mortar = lerp(mortar, mortar * 0.78, smooth(0.0, 1.0, j - d)[..., None] * 0.0 + (1 - smooth(0.0, 0.006, d))[..., None] * 0.35)
    alb = lerp(mortar, alb, stone)
    # salissures qui coulent sous les pierres
    drip = smooth(0.8, 2.2, blur_y(noise(n, n / 35, seed + 24), 25)) * 0.15
    alb *= (1 - drip)[..., None]
    # lichens et coulures d'oxyde
    lich = smooth(2.1, 2.5, noise(n, n / 25, seed + 18) + 0.6 * band(n, 12, seed + 19)) * stone
    alb = lerp(alb, hex2rgb("#bda05a") * (0.9 + 0.1 * band(n, 5, seed + 20))[..., None], lich * 0.7)
    rust = smooth(1.6, 2.6, blur_y(noise(n, n / 40, seed + 21), 30)) * 0.25
    alb = lerp(alb, alb * hex2rgb("#b07a50"), rust)
    rough = np.clip(0.82 + 0.08 * noise(n, n / 40, seed + 22) + 0.1 * (1 - stone) - 0.08 * edge * (1 - dn), 0.5, 1)
    return dict(alb=alb, h=h, rough=rough, stone=stone, ID=ID)


@register("PierreMoellons", 3.0, 2048)
def t_rubble(n, size):
    # moellons de calcaire des murs de village : pierres de 12 à 35 cm, joints de chaux larges et beurrés
    r = rubble(n, size, 101, cmin=0.12, cmax=0.3, wmin=0.18, wmax=0.55, joint=(0.01, 0.028))
    return dict(albedo=r["alb"], height=r["h"], rough=r["rough"])


@register("PierreTaille", 3.0, 2048)
def t_ashlar(n, size):
    px = size / n
    rng = np.random.default_rng(202)
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * px
    hs, t = [], 0.0
    while t < size:
        h = rng.choice([0.28, 0.32, 0.36, 0.42])
        hs.append(h)
        t += h
    hs = np.array(hs) * size / t
    starts = np.concatenate([[0], np.cumsum(hs)[:-1]])
    row = np.clip(np.searchsorted(starts, yy, side="right") - 1, 0, len(hs) - 1)
    ID = np.zeros((n, n), np.int64)
    for r in range(len(hs)):
        ws, t = [], 0.0
        while t < size:
            w = rng.uniform(0.45, 1.0)
            ws.append(w)
            t += w
        ws = np.array(ws) * size / t
        bs = np.concatenate([[0], np.cumsum(ws)[:-1]])
        off = rng.uniform(0, size)
        m = row == r
        col = np.searchsorted(bs, (xx[m] + off) % size, side="right") - 1
        ID[m] = r * 1000 + col
    _, ID = np.unique(ID, return_inverse=True)
    ID = ID.reshape(n, n)
    d = edt_wrap(~edges_of(ID)) * px
    j = 0.004 + 0.002 * band(n, n / 20, 203)
    stone = (d > j).astype(F32)
    chip = smooth(1.8, 2.4, noise(n, n / 60, 204)) * (d < 0.03)
    edge = smooth(j, j + 0.012, d) * (1 - chip * 0.7)
    # layage : fines stries parallèles du taillant, orientées différemment d'un bloc à l'autre
    ang = rand_per_id(ID, 217) * np.pi
    strie = np.sin((xx * np.cos(ang) + yy * np.sin(ang)) * 2 * np.pi / 0.004 + noise(n, 6, 218) * 2.0)
    tool = strie * 0.00025 + band(n, n / 25, 206) * 0.0015 + noise(n, 4, 207) * 0.0002
    h = stone * (0.006 * edge + tool + (rand_per_id(ID, 208) - 0.5) * 0.004) - (1 - stone) * 0.004
    base = [hex2rgb(c) for c in ("#d9c9a8", "#d1bf9b", "#cdbfa6", "#dccfb2", "#c9b28c", "#c4b8a2")]
    col = palette_pick(ID, base, 209)
    var = 1 + 0.05 * noise(n, n / 10, 210) + 0.035 * band(n, 10, 211)
    alb = col * ((0.93 + 0.12 * rand_per_id(ID, 212)) * var)[..., None]
    grime = smooth(0.8, 2.2, blur_y(noise(n, n / 30, 213), 40)) * 0.18
    alb *= (1 - grime)[..., None]
    alb *= (1 + 0.03 * strie)[..., None]
    alb = lerp(alb, alb * 0.8, (1 - edge)[..., None] * 0.5)
    alb = lerp(hex2rgb("#bfb39c"), alb, stone)
    lich = smooth(2.2, 2.6, noise(n, n / 20, 214) + 0.5 * band(n, 10, 215)) * stone
    alb = lerp(alb, hex2rgb("#a9a58c"), lich * 0.6)
    rough = np.clip(0.8 + 0.08 * noise(n, n / 30, 216), 0.5, 1)
    return dict(albedo=alb, height=h, rough=rough)


# ------------------------------------------------------------------ enduit à la chaux (teintable)
@register("Enduit", 3.0, 2048)
def t_plaster(n, size):
    px = size / n
    s = 301
    base = hex2rgb("#efe9de")
    low = noise(n, n / 1.5, s, beta=3.0) * 0.035 + noise(n, n / 6, s + 1) * 0.018 + band(n, 3, s + 2) * 0.01
    alb = base * (1 + low)[..., None]
    warm = noise(n, n / 3, s + 3) * 0.02
    alb[..., 0] *= 1 + warm
    alb[..., 2] *= 1 - warm
    st = blur_y(noise(n, n / 25, s + 4), n / 14)
    streak = smooth(0.9, 2.4, st) * 0.1
    alb *= (1 - streak)[..., None]
    h = band(n, n / 9, s + 5) * 0.0015 + band(n, n / 35, s + 6) * 0.0006 + band(n, 5, s + 7) * 0.00015 + noise(n, 2, s + 8) * 0.00005
    # chaux lissée à la truelle : légers arcs
    trowel = blur(smooth(0.6, 1.0, band(n, n / 14, s + 9, width=0.3)), 3) * 0.0008
    h += trowel
    # enduit tombé : pierre apparente
    blob = noise(n, n / 5, s + 10) * 0.75 + noise(n, n / 30, s + 11) * 0.35
    patch = smooth(1.72, 1.8, blob)
    stone = rubble(n, size, s + 12)
    alb = lerp(alb, stone["alb"] * 0.95, patch)
    h = h * (1 - patch) + (stone["h"] - 0.012) * patch
    rim = smooth(1.62, 1.72, blob) * (1 - patch)
    alb *= (1 - 0.18 * rim)[..., None]
    # fissures
    F1, F2, ID, _ = voronoi(n, 5, s + 13)
    crack = ((F2 - F1) < 1.5).astype(F32) * smooth(0.3, 0.9, noise(n, n / 10, s + 14))
    crack = blur(crack, 0.6)
    alb *= (1 - 0.35 * crack)[..., None]
    h -= crack * 0.0015
    rough = np.clip(0.9 + 0.05 * noise(n, n / 20, s + 15) - 0.05 * patch, 0.6, 1)
    mask = np.clip(1 - patch, 0, 1)
    return dict(albedo=alb, height=h, rough=rough, mask=mask)


# ------------------------------------------------------------------ tuiles canal
@register("TuilesCanal", 2.0, 2048)
def t_roof(n, size):
    px = size / n
    s = 401
    rng = np.random.default_rng(s)
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * px
    ncol, nrow = 9, 6
    p = size / ncol
    L = size / nrow
    wob_u = band(n, n / 6, s + 1) * 0.004
    U = (xx + wob_u) % size
    V = yy
    # couloirs (concaves)
    kc = np.floor(U / p + 0.5).astype(np.int64) % ncol
    xc = ((U - kc * p + size / 2) % size) - size / 2
    col_off_c = rng.uniform(0, L, ncol).astype(F32)
    rc = np.floor(((V + col_off_c[kc]) % size) / L).astype(np.int64) % nrow
    fc = (((V + col_off_c[kc]) % size) / L) % 1.0
    jit_c = (rng.random((ncol, nrow)).astype(F32) - 0.5) * 0.012
    xc = xc - jit_c[kc, rc]
    ac = 0.094 * (1.06 - 0.12 * fc)
    inc = np.abs(xc) < ac
    hc = np.where(inc, ac - np.sqrt(np.maximum(ac * ac - xc * xc, 0)), -0.02)
    hc = hc + 0.016 * fc * inc
    # couverts (convexes)
    kv = np.floor(U / p).astype(np.int64) % ncol
    xv = ((U - (kv + 0.5) * p + size / 2) % size) - size / 2
    col_off_v = rng.uniform(0, L, ncol).astype(F32)
    rv = np.floor(((V + col_off_v[kv]) % size) / L).astype(np.int64) % nrow
    fv = (((V + col_off_v[kv]) % size) / L) % 1.0
    jit_v = (rng.random((ncol, nrow)).astype(F32) - 0.5) * 0.012
    xv = xv - jit_v[kv, rv]
    av = 0.084 * (0.94 + 0.12 * fv)
    inv = np.abs(xv) < av
    hv = np.where(inv, 0.052 + np.sqrt(np.maximum(av * av - xv * xv, 0)) * 0.9 + 0.016 * fv, -1.0)
    top = hv > hc
    h = np.where(top, hv, hc)
    tid = np.where(top, 100000 + kv * 100 + rv, kc * 100 + rc)
    _, tid = np.unique(tid, return_inverse=True)
    tid = tid.reshape(n, n)
    h = h + band(n, n / 40, s + 2) * 0.001 + noise(n, 3, s + 3) * 0.00025
    pal = [hex2rgb(c) for c in ("#b8663d", "#a9553a", "#c67d4b", "#9d5b3d", "#c98f68", "#8b5b43", "#b36f4f", "#7e4b37", "#c4704a", "#a86a4c")]
    col = palette_pick(tid, pal, s + 4, weights=[3, 3, 2, 2, 1.5, 1.5, 2, 1, 2, 1.5])
    bright = 0.85 + 0.3 * rand_per_id(tid, s + 5)
    var = 1 + 0.07 * noise(n, n / 25, s + 6) + 0.05 * band(n, 6, s + 7)
    alb = col * (bright * var)[..., None]
    alb = np.where(top[..., None], alb * 1.06, alb * (0.78 + 0.22 * np.clip(np.abs(xc) / 0.09, 0, 1))[..., None])
    # extrémités des tuiles plus sombres (mousse, poussière)
    tip = np.where(top, smooth(0.8, 1.0, fv), smooth(0.85, 1.0, fc))
    alb *= (1 - 0.25 * tip)[..., None]
    # lichens jaunes et gris
    l1 = smooth(1.9, 2.4, noise(n, n / 45, s + 8) + 0.8 * band(n, 9, s + 9)) * top
    alb = lerp(alb, hex2rgb("#cfa84e") * (0.9 + 0.1 * band(n, 4, s + 10))[..., None], l1 * 0.85)
    l2 = smooth(2.0, 2.5, noise(n, n / 30, s + 11) + 0.8 * band(n, 7, s + 12)) * top
    alb = lerp(alb, hex2rgb("#b9b6a4"), l2 * 0.7)
    moss = smooth(2.0, 2.6, noise(n, n / 20, s + 13)) * (~top) * smooth(0.5, 1.0, fc)
    alb = lerp(alb, hex2rgb("#5d5a3a"), moss * 0.7)
    rough = np.clip(0.72 + 0.1 * noise(n, n / 30, s + 14) + 0.1 * l1 + 0.1 * moss, 0.4, 1)
    return dict(albedo=alb, height=h, rough=rough, ao_depth=0.03)


# ------------------------------------------------------------------ génoise (rangée de tuiles en bordure de toit)
@register("Genoise", 1.12, 1024)
def t_genoise(n, size):
    px = size / n
    s = 451
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * px
    nt = 7
    p = size / nt
    k = np.floor(xx / p).astype(np.int64) % nt
    xl = (xx - (k + 0.5) * p)
    rows = 10
    Lr = size / rows
    r = np.floor(yy / Lr).astype(np.int64)
    yl = yy - r * Lr
    shift = (r % 2) * 0.5 * p
    k2 = np.floor((xx + shift) / p).astype(np.int64) % nt
    xl = (xx + shift) - (np.floor((xx + shift) / p) + 0.5) * p
    R = p * 0.46
    cy = Lr * 0.72
    dy = yl - cy
    ring = np.sqrt(xl ** 2 + dy ** 2)
    arch = (dy < 0) & (ring < R) & (ring > R - 0.018)
    inner = (dy < 0) & (ring <= R - 0.018)
    tid = r * 100 + k2
    pal = [hex2rgb(c) for c in ("#b8663d", "#a9553a", "#c67d4b", "#9d5b3d", "#b36f4f")]
    tile_col = palette_pick(tid, pal, s + 1)
    mortar = hex2rgb("#d8cdb6") * (0.92 + 0.06 * noise(n, n / 10, s + 2))[..., None]
    alb = np.where(arch[..., None], tile_col * (0.9 + 0.1 * band(n, 8, s + 3))[..., None], mortar)
    alb = np.where(inner[..., None], mortar * 0.55, alb)
    h = np.where(arch, 0.012, 0.0) + np.where(inner, -0.02 * (1 - ring / R), 0.0) + band(n, 10, s + 4) * 0.0005
    h += -0.004 * smooth(0.9, 1.0, yl / Lr)
    rough = np.where(arch, 0.7, 0.9).astype(F32)
    return dict(albedo=alb, height=h, rough=rough)


# ------------------------------------------------------------------ calade (galets posés de chant)
def pebbles(n, size, seed, cell_m=0.1, elong=1.7, gap_px=(3, 7), amp=(0.018, 0.035), palette=None, flow_scale=4.0, soil_col="#8c7d66"):
    px = size / n
    cells = int(round(size / cell_m))
    rng = np.random.default_rng(seed)
    gx = gy = cells
    sx = n / gx
    ii, jj = np.meshgrid(np.arange(gx), np.arange(gy))
    ptx = ((ii + 0.5 + (rng.random((gy, gx)) - 0.5) * 0.8) * sx).ravel() % n
    pty = ((jj + 0.5 + (rng.random((gy, gx)) - 0.5) * 0.8) * sx).ravel() % n
    flow = noise(n, n / flow_scale, seed + 1)
    th = (flow[pty.astype(int) % n, ptx.astype(int) % n] * 1.2 + rng.normal(0, 0.25, ptx.size)).astype(F32)
    el = (elong * (0.8 + 0.4 * rng.random(ptx.size))).astype(F32)
    tree = cKDTree(np.stack([ptx, pty], -1), boxsize=[n, n])
    F1 = np.empty((n, n), F32)
    F2 = np.empty((n, n), F32)
    ID = np.empty((n, n), np.int64)
    K = 10
    for y0 in range(0, n, 256):
        yy, xx = np.mgrid[y0:y0 + 256, 0:n].astype(F32) + 0.5
        q = np.stack([xx.ravel(), yy.ravel()], -1)
        _, idx = tree.query(q, k=K, workers=-1)
        dx = ((q[:, 0:1] - ptx[idx] + n / 2) % n) - n / 2
        dy = ((q[:, 1:2] - pty[idx] + n / 2) % n) - n / 2
        c, s_ = np.cos(th[idx]), np.sin(th[idx])
        a = (dx * c + dy * s_) / el[idx]
        b = -dx * s_ + dy * c
        d = np.sqrt(a * a + b * b)
        o = np.argsort(d, axis=1)
        d1 = np.take_along_axis(d, o[:, :1], 1)[:, 0]
        d2 = np.take_along_axis(d, o[:, 1:2], 1)[:, 0]
        i1 = np.take_along_axis(idx, o[:, :1], 1)[:, 0]
        F1[y0:y0 + 256] = d1.reshape(256, n)
        F2[y0:y0 + 256] = d2.reshape(256, n)
        ID[y0:y0 + 256] = i1.reshape(256, n)
    e = F2 - F1
    g = gap_px[0] + (gap_px[1] - gap_px[0]) * rand_per_id(ID, seed + 2, ptx.size)
    peb = smooth(g, g + 3, e)
    dome = np.sqrt(np.clip((e - g) / (sx * 0.45), 0, 1))
    a_ = amp[0] + (amp[1] - amp[0]) * rand_per_id(ID, seed + 3, ptx.size)
    h = peb * a_ * dome + band(n, 6, seed + 4) * 0.0004 - (1 - peb) * 0.01 + (1 - peb) * noise(n, 6, seed + 5) * 0.002
    pal = palette or [hex2rgb(c) for c in ("#d4ccbd", "#bdb19d", "#a89e90", "#cbb592", "#8f877d", "#ddd7cb", "#b8a48a", "#9c8f80")]
    col = palette_pick(ID, pal, seed + 6)
    alb = col * (0.88 + 0.22 * rand_per_id(ID, seed + 7, ptx.size))[..., None] * (1 + 0.05 * band(n, 10, seed + 8))[..., None]
    soil = hex2rgb(soil_col) * (0.85 + 0.15 * noise(n, 20, seed + 9))[..., None]
    alb = lerp(soil, alb * (0.75 + 0.25 * dome)[..., None], peb)
    rough = np.clip(0.55 + 0.35 * (1 - dome) + 0.3 * (1 - peb), 0.4, 1)
    return dict(alb=alb, h=h, rough=rough, peb=peb, ID=ID)


@register("Calade", 2.0, 2048)
def t_calade(n, size):
    r = pebbles(n, size, 501)
    return dict(albedo=r["alb"], height=r["h"], rough=r["rough"], ao_depth=0.02)


# ------------------------------------------------------------------ dallage de pierre (places)
@register("Dallage", 3.0, 2048)
def t_flag(n, size):
    px = size / n
    s = 551
    F1, F2, ID, _ = voronoi(n, (6, 7), s, jitter=0.7, stretch=(1.0, 1.2))
    wx = band(n, n / 12, s + 1) * 6
    wy = band(n, n / 12, s + 2) * 6
    e = warp(F2 - F1, wx, wy)
    ID = warp(ID.astype(F32), wx, wy, order=0).astype(np.int64)
    joint = 4 + 3 * band(n, n / 20, s + 3)
    stone = smooth(joint, joint + 2, e)
    bevel = smooth(joint, joint + 18, e)
    h = stone * (0.004 * bevel + (rand_per_id(ID, s + 4) - 0.5) * 0.004 + band(n, n / 30, s + 5) * 0.0012 + band(n, 5, s + 6) * 0.0003) - (1 - stone) * 0.006
    pal = [hex2rgb(c) for c in ("#cdbfa3", "#c3b69f", "#d6c8aa", "#bba98c", "#d0c4b0", "#b6ac9c")]
    alb = palette_pick(ID, pal, s + 7) * (0.9 + 0.18 * rand_per_id(ID, s + 8))[..., None]
    alb *= (1 + 0.06 * noise(n, n / 15, s + 9) + 0.03 * band(n, 6, s + 10))[..., None]
    wear = smooth(0.5, 2.0, noise(n, n / 6, s + 11))
    alb = lerp(alb, alb * 0.85, wear * 0.4)
    alb = lerp(hex2rgb("#5e5446"), alb, stone)
    rough = np.clip(0.7 + 0.1 * noise(n, n / 20, s + 12) - 0.15 * wear * stone + 0.2 * (1 - stone), 0.4, 1)
    return dict(albedo=alb, height=h, rough=rough)


# ------------------------------------------------------------------ enrobé (routes)
@register("Asphalte", 4.0, 2048)
def t_asphalt(n, size):
    px = size / n
    s = 601
    agg = band(n, 4, s) * 0.6 + band(n, 2, s + 1) * 0.4
    spec = smooth(1.2, 2.2, agg)
    base = hex2rgb("#4a4845") * (1 + 0.1 * noise(n, n / 6, s + 2) + 0.05 * band(n, 30, s + 3))[..., None]
    alb = lerp(base, hex2rgb("#8d8a84"), spec * 0.6)
    patch = smooth(1.3, 1.5, noise(n, n / 3, s + 4))
    alb = lerp(alb, alb * 0.72, patch)
    F1, F2, ID, _ = voronoi(n, 4, s + 5)
    crack = ((F2 - F1) < 2.0).astype(F32) * smooth(0.5, 1.2, noise(n, n / 8, s + 6))
    crack = blur(crack, 0.7)
    alb = lerp(alb, hex2rgb("#262523"), crack * 0.8)
    stain = smooth(1.8, 2.6, noise(n, n / 10, s + 7)) * 0.4
    alb *= (1 - stain)[..., None]
    h = agg * 0.0012 - crack * 0.004 + band(n, n / 20, s + 8) * 0.001 - patch * 0.0005
    rough = np.clip(0.86 + 0.06 * noise(n, 40, s + 9) - 0.25 * stain, 0.4, 1)
    return dict(albedo=alb, height=h, rough=rough)


@register("Gravier", 2.0, 1024)
def t_gravel(n, size):
    r = pebbles(n, size, 651, cell_m=0.018, elong=1.3, gap_px=(1, 3), amp=(0.004, 0.009),
                palette=[hex2rgb(c) for c in ("#d8d0c0", "#c9bda6", "#b8ab96", "#e2dccf", "#a89b88", "#cbb89a")], flow_scale=1.0)
    dust = smooth(0.5, 1.8, noise(n, n / 8, 652))
    alb = lerp(r["alb"], hex2rgb("#c7b9a0"), dust * 0.35)
    return dict(albedo=alb, height=r["h"], rough=np.clip(r["rough"] + 0.15, 0, 1))


# ------------------------------------------------------------------ bois
def planks(n, size, seed, width=0.12, base_col="#8a7a66", paint=None, age=0.5, vertical=True, grey=0.3):
    """Planches à veinage réaliste : cernes de croissance (dosse), nœuds, fibres, fentes, patine grise ; peinture écaillée en option."""
    px = size / n
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * px
    npl = max(1, int(round(size / width)))
    w = size / npl
    k = np.floor(xx / w).astype(np.int64) % npl
    xl = xx - np.floor(xx / w) * w
    gap = (xl < 0.0035) | (xl > w - 0.0035)
    rng = np.random.default_rng(seed)
    # chaque planche a sa propre découpe dans le tronc : position du cœur, profondeur, espacement des cernes
    cu = (rand_per_id(k, seed + 1, npl) - 0.5) * 6 * w
    d0 = 0.04 + 0.25 * rand_per_id(k, seed + 2, npl)
    sp = 0.0035 + 0.003 * rand_per_id(k, seed + 3, npl)
    wav = noise(n, n / 3, seed + 4, beta=3.0) * 0.012 + noise(n, n / 12, seed + 5, beta=2.5) * 0.002
    r = np.sqrt((xl - w / 2 - cu) ** 2 + d0 ** 2) + wav
    # nœuds : les cernes s'enroulent autour, tache sombre au centre
    knot_h = np.zeros((n, n), F32)
    knot_c = np.zeros((n, n), F32)
    for _ in range(max(2, npl // 2)):
        kx, ky = rng.uniform(0, size), rng.uniform(0, size)
        kr = rng.uniform(0.008, 0.02)
        dx = (xx - kx + size / 2) % size - size / 2
        dy = ((yy - ky + size / 2) % size - size / 2) * 0.55
        dd = np.sqrt(dx ** 2 + dy ** 2)
        infl = np.exp(-(dd / (kr * 4.0)) ** 2)
        r = r + infl * (kr * 3.0 - dd * 0.6)
        knot_c = np.maximum(knot_c, smooth(kr, kr * 0.4, dd))
        knot_h = np.maximum(knot_h, infl)
    rings = (r / sp) % 1.0
    late = smooth(0.62, 0.9, rings) * (1 - smooth(0.9, 1.0, rings))
    fib = band(n, 30, seed + 6, aniso=18.0) * 0.5 + band(n, 8, seed + 7, aniso=30.0) * 0.5
    # fentes le long du fil
    crack = np.zeros((n, n), F32)
    for _ in range(npl * 2):
        cx0 = rng.uniform(0, size)
        cy0, L = rng.uniform(0, size), rng.uniform(0.05, 0.35)
        dist = np.abs((xx - cx0 + size / 2) % size - size / 2 + 0.002 * np.sin(yy * 40))
        along = ((yy - cy0) % size) < L
        crack = np.maximum(crack, (dist < 0.0012) * along * 1.0)
    crack = blur(crack, 0.6)
    tone = 0.82 + 0.3 * rand_per_id(k, seed + 8, npl)
    wood = hex2rgb(base_col) * tone[..., None]
    wood = wood * (1 - 0.3 * late + 0.06 * fib)[..., None]
    wood = lerp(wood, hex2rgb("#3b2a1c"), knot_c * 0.85)
    # patine grise du bois exposé
    gr = np.clip(grey + 0.35 * noise(n, n / 6, seed + 9), 0, 1)
    wood = lerp(wood, hex2rgb("#8f8b84") * (1 - 0.2 * late)[..., None], gr[..., None] * 0.6)
    wood = lerp(wood, wood * 0.3, crack[..., None])
    h = late * 0.0005 + fib * 0.00015 - crack * 0.0015 - gap * 0.003 + knot_h * 0.0003
    alb = wood
    mask = np.zeros((n, n), F32)
    rough = np.clip(0.72 + 0.12 * late + 0.1 * gr, 0, 1)
    if paint is not None:
        # la peinture s'écaille en lanières dans le sens du fil, surtout près des joints et du bas
        edge_near = 1 - smooth(0.0, 0.02, np.minimum(xl, w - xl))
        fl_noise = band(n, 25, seed + 10, aniso=10.0) + 0.8 * noise(n, n / 8, seed + 11) + 0.7 * edge_near
        th = 1.1 + 1.4 * (1 - age)
        flake = smooth(th, th + 0.15, fl_noise)
        pcol = np.ones(3, F32) * 0.92 if paint == "white" else hex2rgb(paint)
        brush = band(n, 12, seed + 12, aniso=14.0)
        painted = pcol * (0.94 + 0.04 * brush - 0.08 * late * 0.4)[..., None]
        chalk = smooth(0.5, 1.8, noise(n, n / 10, seed + 13)) * 0.12
        painted = lerp(painted, np.ones(3, F32) * 0.97, chalk[..., None])
        # liseré sombre au bord des écailles
        rim = smooth(th - 0.25, th, fl_noise) * (1 - flake)
        alb = lerp(painted, wood, flake[..., None])
        alb = lerp(alb, alb * 0.75, rim[..., None] * 0.6)
        mask = (1 - flake) * (1 - rim * 0.5)
        h = h * (0.3 + 0.7 * flake) + (1 - flake) * 0.0005
        rough = np.clip(lerp(0.5 + 0.1 * noise(n, 20, seed + 14) + chalk, rough, flake), 0, 1)
    alb = np.where(gap[..., None], alb * 0.3, alb)
    return dict(albedo=alb, height=h, rough=rough, mask=mask)


@register("BoisPeint", 1.0, 1024)
def t_wood_painted(n, size):
    return planks(n, size, 701, width=0.13, base_col="#8f7a62", paint="white", age=0.5, grey=0.45)


@register("BoisBrut", 1.0, 1024)
def t_wood_raw(n, size):
    return planks(n, size, 751, width=0.16, base_col="#9a7b58", grey=0.15)


@register("Fer", 1.0, 512)
def t_iron(n, size):
    s = 801
    base = hex2rgb("#2b2a28") * (1 + 0.08 * noise(n, n / 6, s))[..., None]
    rust = smooth(1.3, 2.3, noise(n, n / 10, s + 1) + 0.5 * band(n, 6, s + 2))
    alb = lerp(base, hex2rgb("#6b3a22"), rust * 0.7)
    h = band(n, 8, s + 3) * 0.0003 + rust * 0.0004
    rough = np.clip(0.55 + 0.35 * rust, 0, 1)
    return dict(albedo=alb, height=h, rough=rough, metal=0.6)


@register("TerreCuite", 1.0, 1024)
def t_terracotta(n, size):
    s = 851
    base = hex2rgb("#b8683e") * (1 + 0.08 * noise(n, n / 4, s) + 0.04 * band(n, 6, s + 1))[..., None]
    salt = smooth(1.5, 2.5, noise(n, n / 8, s + 2)) * 0.5
    alb = lerp(base, hex2rgb("#d8c8b0"), salt * 0.5)
    h = band(n, 10, s + 3) * 0.0004 + band(n, 3, s + 4) * 0.0001
    return dict(albedo=alb, height=h, rough=np.clip(0.8 + 0.1 * noise(n, 30, s + 5), 0, 1))


@register("Toile", 1.0, 512)
def t_canvas(n, size):
    s = 901
    yy, xx = np.mgrid[0:n, 0:n].astype(F32)
    per = n / 128
    weave = np.sin(xx / per * np.pi) * np.sin(yy / per * np.pi)
    alb = np.ones((n, n, 3), F32) * 0.93 * (1 + 0.04 * weave + 0.04 * noise(n, n / 5, s))[..., None]
    h = weave * 0.0002
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.9, F32), mask=np.ones((n, n), F32))


# ------------------------------------------------------------------ sols naturels (couches du terrain)
def scatter_stones(n, size, seed, density=1.0, cell_m=0.05, cols=None, amp=0.012):
    F1, F2, ID, _ = voronoi(n, int(size / cell_m), seed, jitter=1.0)
    keep = rand_per_id(ID, seed + 1) < 0.18 * density
    rad = (0.25 + 0.4 * rand_per_id(ID, seed + 2)) * (n / (size / cell_m))
    st = keep & (F1 < rad)
    dome = np.where(st, np.sqrt(np.clip(1 - (F1 / np.maximum(rad, 1)) ** 2, 0, 1)), 0).astype(F32)
    cols = cols or [hex2rgb(c) for c in ("#d6cfc0", "#bfb39f", "#a99e8d", "#cdb896")]
    col = palette_pick(ID, cols, seed + 3)
    return dome, col, amp


def grass_blades(n, size, seed, count, length_m=(0.03, 0.09), cols=None, width_px=1.4):
    """Brins d'herbe/paille dessinés (raccordables)."""
    from PIL import ImageDraw
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (n, n), (0, 0, 0))
    hmap = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(img)
    dh = ImageDraw.Draw(hmap)
    cols = cols or [(200, 180, 110)]
    for _ in range(count):
        x, y = rng.random() * n, rng.random() * n
        L = rng.uniform(*length_m) / size * n
        a = rng.uniform(0, 2 * np.pi)
        c = cols[rng.integers(len(cols))]
        c = tuple(int(np.clip(v * rng.uniform(0.8, 1.15), 0, 255)) for v in c)
        x2, y2 = x + np.cos(a) * L, y + np.sin(a) * L
        w = max(1, int(round(width_px * rng.uniform(0.7, 1.4))))
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                d.line([(x + ox, y + oy), (x2 + ox, y2 + oy)], fill=c, width=w)
                dh.line([(x + ox, y + oy), (x2 + ox, y2 + oy)], fill=int(rng.uniform(120, 255)), width=w)
    return np.asarray(img, F32) / 255.0, np.asarray(hmap, F32) / 255.0


def ground(n, size, seed, base, var=0.12, pebble_density=1.0, pebble_cols=None, blades=0, blade_cols=None, clods=0.0, blade_len=(0.03, 0.09)):
    px = size / n
    alb = hex2rgb(base) * (1 + var * noise(n, n / 3, seed) + 0.6 * var * band(n, n / 25, seed + 1) + 0.3 * var * band(n, 6, seed + 2))[..., None]
    h = noise(n, n / 4, seed + 3) * 0.006 + band(n, n / 20, seed + 4) * 0.003 + band(n, 6, seed + 5) * 0.0007
    if clods > 0:
        F1, F2, ID, _ = voronoi(n, int(size / 0.06), seed + 6)
        cl = smooth(0, 14, F2 - F1) * (rand_per_id(ID, seed + 7) < 0.6)
        h += cl * clods * 0.02
        alb *= (0.85 + 0.15 * cl)[..., None]
    if pebble_density > 0:
        dome, col, amp = scatter_stones(n, size, seed + 8, pebble_density, cols=pebble_cols)
        h += dome * amp
        alb = lerp(alb, col * (0.8 + 0.2 * dome)[..., None], np.clip(dome * 3, 0, 1))
    if blades:
        bc, bh = grass_blades(n, size, seed + 9, blades, blade_len, blade_cols)
        m = (bh > 0).astype(F32)
        alb = lerp(alb, bc, m)
        h += bh * 0.006
    rough = np.clip(0.9 + 0.05 * noise(n, 30, seed + 10), 0, 1)
    return dict(albedo=alb, height=h, rough=rough)


@register("SolSec", 4.0, 2048)
def t_dry(n, size):
    return ground(n, size, 1001, "#a38f5e", pebble_density=0.8, blades=22000,
                  blade_cols=[(206, 178, 110), (186, 160, 96), (160, 146, 90), (214, 196, 136), (140, 126, 74), (150, 140, 80)])


@register("TerreLabouree", 4.0, 2048)
def t_earth(n, size):
    return ground(n, size, 1101, "#7e5a42", var=0.1, pebble_density=0.8, clods=1.0,
                  pebble_cols=[hex2rgb(c) for c in ("#cfc5b3", "#b5a58c", "#a38f76")])


@register("Ocre", 4.0, 2048)
def t_ochre(n, size):
    s = 1201
    r = ground(n, size, s, "#c7682a", var=0.08, pebble_density=0.4,
               pebble_cols=[hex2rgb(c) for c in ("#d8904a", "#b85a2a", "#e0b070")])
    bands = blur_x(band(n, n / 30, s + 20, aniso=0.15), 3)
    yellow = smooth(0.3, 1.5, noise(n, n / 3, s + 21) + 0.5 * bands)
    red = smooth(0.8, 2.0, noise(n, n / 4, s + 22))
    alb = lerp(r["albedo"], hex2rgb("#d99a3e") * (1 + 0.05 * bands)[..., None], yellow * 0.6)
    alb = lerp(alb, hex2rgb("#9e3b1e"), red * 0.55)
    ripple = band(n, n / 60, s + 23, aniso=0.3) * 0.002
    return dict(albedo=alb, height=r["height"] + ripple, rough=r["rough"])


@register("Roche", 4.0, 2048)
def t_rock(n, size):
    s = 1301
    F1, F2, ID, _ = voronoi(n, 10, s, jitter=1.0)
    wx, wy = band(n, n / 10, s + 1) * 20, band(n, n / 10, s + 2) * 20
    e = warp(F2 - F1, wx, wy)
    crack = 1 - smooth(1, 6, e)
    h = noise(n, n / 3, s + 3) * 0.03 + band(n, n / 20, s + 4) * 0.006 + band(n, 8, s + 5) * 0.0015 - crack * 0.02
    alb = hex2rgb("#bdb6a8") * (1 + 0.1 * noise(n, n / 5, s + 6) + 0.05 * band(n, 10, s + 7))[..., None]
    alb = lerp(alb, hex2rgb("#6e675c"), crack * 0.7)
    lich = smooth(1.8, 2.4, noise(n, n / 30, s + 8) + 0.6 * band(n, 8, s + 9))
    alb = lerp(alb, hex2rgb("#9b9a82"), lich * 0.6)
    lich2 = smooth(2.2, 2.6, noise(n, n / 40, s + 10))
    alb = lerp(alb, hex2rgb("#c9a44f"), lich2 * 0.6)
    return dict(albedo=alb, height=h, rough=np.clip(0.85 + 0.08 * noise(n, 20, s + 11), 0, 1))


@register("SolForet", 4.0, 2048)
def t_forest(n, size):
    s = 1401
    r = ground(n, size, s, "#5f4b34", var=0.12, pebble_density=0.3, blades=26000, blade_len=(0.04, 0.09),
               blade_cols=[(150, 95, 55), (120, 80, 45), (170, 115, 70), (95, 70, 45), (135, 105, 70)])
    leaves = smooth(1.2, 1.6, noise(n, 30, s + 30)) * smooth(0.0, 1.0, noise(n, n / 6, s + 31))
    alb = lerp(r["albedo"], hex2rgb("#8a6a3e"), leaves * 0.7)
    return dict(albedo=alb, height=r["height"] + leaves * 0.002, rough=r["rough"])


@register("Herbe", 4.0, 2048)
def t_grass(n, size):
    return ground(n, size, 1501, "#6d6e3a", var=0.12, pebble_density=0.15, blades=60000, blade_len=(0.02, 0.06),
                  blade_cols=[(120, 135, 60), (105, 120, 50), (150, 150, 80), (140, 130, 70), (90, 105, 45), (175, 165, 95)])


@register("Chemin", 4.0, 2048)
def t_dirt(n, size):
    return ground(n, size, 1601, "#a08c70", var=0.08, pebble_density=1.4,
                  pebble_cols=[hex2rgb(c) for c in ("#d8d0c0", "#c2b49c", "#ae9e86", "#e0d8c8")])


@register("Chaume", 4.0, 2048)
def t_straw(n, size):
    return ground(n, size, 1701, "#b39a62", var=0.08, pebble_density=0.3, blades=30000, blade_len=(0.03, 0.08),
                  blade_cols=[(222, 196, 130), (205, 178, 110), (235, 214, 150), (190, 160, 95), (170, 140, 90)])


# ------------------------------------------------------------------ écorces
@register("EcorcePlatane", 1.0, 1024)
def t_bark_plane(n, size):
    s = 1801
    F1, F2, ID, _ = voronoi(n, 7, s, jitter=1.0, stretch=(1.0, 0.7))
    wx, wy = band(n, n / 8, s + 1) * 25, band(n, n / 8, s + 2) * 25
    ID = warp(ID.astype(F32), wx, wy, order=0).astype(np.int64)
    e = warp(F2 - F1, wx, wy)
    pal = [hex2rgb(c) for c in ("#d8d3b4", "#b4b08a", "#8f8b6c", "#c9c09a", "#9c9478", "#e2dcc2")]
    alb = palette_pick(ID, pal, s + 3) * (1 + 0.05 * noise(n, n / 10, s + 4))[..., None]
    rim = 1 - smooth(1, 5, e)
    alb = lerp(alb, alb * 0.7, rim)
    h = (rand_per_id(ID, s + 5) - 0.5) * 0.002 - rim * 0.001 + band(n, 6, s + 6) * 0.0002
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.75, F32))


def _nz(a):
    return (a - a.mean()) / (a.std() + 1e-6)


def _warp(a, dx, dy):
    from scipy.ndimage import map_coordinates
    n = a.shape[0]
    yy, xx = np.mgrid[0:n, 0:n].astype(F32)
    return map_coordinates(a, [yy + dy, xx + dx], order=1, mode="grid-wrap").astype(F32)


@register("EcorceOlivier", 1.0, 1024)
def t_bark_olive(n, size):
    """Olivier (d'après photos de vieux troncs) : écorce gris-brun très rugueuse, sillons profonds et irréguliers
    qui suivent la torsion du tronc, crêtes cassées en blocs, grain fin, lichens gris-vert et jaunes."""
    s = 1851
    # torsion lente + ondulation irrégulière des sillons
    yy = np.mgrid[0:n, 0:n][0].astype(F32) / n
    dx = n * 0.06 * np.sin(2 * np.pi * yy) + _nz(band(n, n / 4, s + 1)) * n * 0.025 + _nz(band(n, n / 16, s + 2)) * n * 0.006
    ridge = _nz(band(n, n / 11, s + 3, aniso=7.0)) + 0.45 * _nz(band(n, n / 26, s + 4, aniso=5.0)) + 0.15 * _nz(band(n, n / 70, s + 11, aniso=3.0))
    ridge = _warp(ridge, dx, 0 * dx)
    ridge = _nz(ridge)
    furrow = smooth(-0.55, -1.25, ridge)                   # sillons profonds
    crest = smooth(0.0, 1.4, ridge)
    # cassures transversales : les crêtes se découpent en blocs
    cr = _nz(band(n, n / 14, s + 5, aniso=0.12))
    crack = smooth(1.2, 1.9, cr) * crest
    grain = _nz(band(n, 5, s + 6, aniso=2.5))
    low = _nz(band(n, n / 3, s + 7))
    base = lerp(hex2rgb("#8a8375"), hex2rgb("#a59e90"), smooth(-1.2, 1.2, low)[..., None])
    alb = base * (0.82 + 0.22 * crest + 0.05 * grain)[..., None]
    alb = lerp(alb, hex2rgb("#5f574b"), smooth(-0.1, -0.7, ridge)[..., None] * 0.45)
    alb = lerp(alb, hex2rgb("#221f1a"), furrow[..., None] * 0.85)
    alb = lerp(alb, hex2rgb("#2e2a24"), crack[..., None] * 0.7)
    # lichens et mousse
    l1 = smooth(1.0, 1.8, _nz(noise(n, n / 12, s + 8)) + 0.4 * grain) * (1 - furrow)
    alb = lerp(alb, hex2rgb("#aeb09a"), l1[..., None] * 0.55)
    l2 = smooth(2.0, 2.6, _nz(noise(n, n / 30, s + 9)) + 0.3 * grain) * (1 - furrow)
    alb = lerp(alb, hex2rgb("#b58e3c"), l2[..., None] * 0.5)
    moss = smooth(0.8, 1.6, _nz(band(n, n / 8, s + 10))) * furrow
    alb = lerp(alb, hex2rgb("#3c4629"), moss[..., None] * 0.45)
    h = ridge * 0.006 + crest * 0.004 - furrow * 0.012 - crack * 0.005 + grain * 0.0005
    rough = np.clip(0.84 + 0.08 * furrow - 0.05 * l1, 0, 1).astype(F32)
    return dict(albedo=alb, height=h, rough=rough, ao_depth=0.01)


@register("EcorcePin", 1.0, 1024)
def t_bark_pine(n, size):
    s = 1901
    F1, F2, ID, _ = voronoi(n, (6, 10), s, jitter=1.0, stretch=(1.0, 0.45))
    e = F2 - F1
    plate = smooth(2, 9, e)
    pal = [hex2rgb(c) for c in ("#8c5a3e", "#7a4c35", "#9c6b4c", "#6e4a38", "#a57a5a")]
    alb = palette_pick(ID, pal, s + 1) * (1 + 0.08 * band(n, 8, s + 2))[..., None]
    alb = lerp(hex2rgb("#2c2019"), alb, plate)
    h = plate * 0.012 + band(n, 6, s + 3) * 0.0006
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.9, F32))


@register("EcorceChene", 1.0, 1024)
def t_bark_oak(n, size):
    """Chêne vert : écorce gris sombre découpée en petites plaques rectangulaires par des fissures profondes."""
    s = 1951
    F1, F2, ID, _ = voronoi(n, (9, 14), s, jitter=0.8, stretch=(1.0, 0.55))
    wx, wy = band(n, n / 10, s + 1) * 10, band(n, n / 10, s + 2) * 4
    e = warp(F2 - F1, wx, wy)
    ID = warp(ID.astype(F32), wx, wy, order=0).astype(np.int64)
    plate = smooth(1.5, 7.0, e)
    pal = [hex2rgb(c) for c in ("#5f5a52", "#6b655b", "#57524b", "#716a5f", "#4f4b45", "#7a7266")]
    alb = palette_pick(ID, pal, s + 3) * (0.9 + 0.2 * rand_per_id(ID, s + 4))[..., None]
    alb = alb * (1 + 0.1 * band(n, 6, s + 5) + 0.05 * band(n, 20, s + 6, aniso=3.0))[..., None]
    alb = lerp(hex2rgb("#1d1a17"), alb, plate[..., None])
    moss = smooth(1.8, 2.3, noise(n, n / 12, s + 7)) * plate
    alb = lerp(alb, hex2rgb("#77804a"), moss[..., None] * 0.45)
    lich = smooth(2.1, 2.5, noise(n, n / 25, s + 8)) * plate
    alb = lerp(alb, hex2rgb("#b3b49a"), lich[..., None] * 0.6)
    h = plate * 0.01 + (rand_per_id(ID, s + 9) - 0.5) * 0.003 + band(n, 6, s + 10) * 0.0006
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.9, F32))


@register("Eau", 2.0, 512)
def t_water(n, size):
    s = 2001
    h = band(n, n / 6, s) * 0.004 + band(n, n / 16, s + 1) * 0.0015
    alb = np.ones((n, n, 3), F32) * hex2rgb("#2f5f6b")
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.05, F32))



# ------------------------------------------------------------------ intérieurs : tomettes, faïence, tissu provençal
def hex_cells(n, size, d, seed):
    """Pavage hexagonal raccordable (pointes vers le haut) : distance au joint et identifiant de tomette."""
    from scipy.spatial import cKDTree
    nx = int(round(size / d))
    ny = int(round(size / (d * math.sqrt(3))))
    sx, sy = size / nx, size / (ny * 2)          # pas horizontal, pas vertical (deux rangées par période)
    pts, ids = [], []
    k = 0
    for j in range(2 * ny):
        for i in range(nx):
            pts.append(((i + 0.5 * (j % 2)) * sx, j * sy))
            ids.append(k)
            k += 1
    pts = np.array(pts)
    ids = np.array(ids)
    rep = np.concatenate([pts + np.array([ox, oy]) for ox in (-size, 0, size) for oy in (-size, 0, size)])
    rid = np.tile(ids, 9)
    tree = cKDTree(rep)
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * (size / n)
    q = np.column_stack([xx.ravel(), yy.ravel()])
    dd, ii = tree.query(q, k=2)
    edge = ((dd[:, 1] - dd[:, 0]) * 0.5).reshape(n, n)   # demi-écart aux deux centres les plus proches ~ distance au joint
    ID = rid[ii[:, 0]].reshape(n, n)
    return edge, ID


import math


@register("Tomettes", 1.12, 1024)
def t_tomettes(n, size):
    s = 1201
    edge, ID = hex_cells(n, size, 0.16, s)
    joint = 0.0025
    tile = smooth(joint, joint + 0.004, edge)
    bev = smooth(joint, joint + 0.02, edge)
    pal = [hex2rgb(c) for c in ("#a4492b", "#b35a36", "#9a4128", "#bf6a41", "#8f3c26", "#b5603a", "#c47850")]
    alb = palette_pick(ID, pal, s + 1) * (0.88 + 0.22 * rand_per_id(ID, s + 2))[..., None]
    alb *= (1 + 0.07 * noise(n, n / 10, s + 3) + 0.05 * band(n, 5, s + 4))[..., None]
    wear = smooth(0.4, 1.8, noise(n, n / 5, s + 5))
    alb = lerp(alb, alb * 1.12 + 0.03, wear * 0.35)
    alb = lerp(hex2rgb("#8a7f70"), alb, tile)
    h = tile * (0.0015 * bev + (rand_per_id(ID, s + 6) - 0.5) * 0.0012 + band(n, 20, s + 7) * 0.0002) - (1 - tile) * 0.002
    rough = np.clip(0.42 + 0.18 * wear + 0.08 * noise(n, n / 12, s + 8) + 0.4 * (1 - tile), 0.3, 0.95)
    return dict(albedo=alb, height=h, rough=rough)


@register("Faience", 1.0, 1024)
def t_faience(n, size):
    s = 1301
    k = 10                       # carreaux de 10 cm
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * (size / n)
    fx, fy = (xx * k / size) % 1.0, (yy * k / size) % 1.0
    ID = (np.floor(xx * k / size) + k * np.floor(yy * k / size)).astype(np.int64)
    e = np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy)) * (size / k)
    tile = smooth(0.0012, 0.0025, e)
    # émail blanc cassé, quelques carreaux décorés (motif bleu ou ocre) ; teinte par instance via le masque
    base = hex2rgb("#efe9dc") * (0.95 + 0.06 * rand_per_id(ID, s + 1))[..., None]
    r = np.hypot(fx - 0.5, fy - 0.5)
    ang = np.arctan2(fy - 0.5, fx - 0.5)
    motif = smooth(0.34, 0.3, r * (1.0 - 0.3 * np.cos(4 * ang))) * smooth(0.12, 0.15, r) + smooth(0.08, 0.06, r)
    deco = (rand_per_id(ID, s + 2) < 0.22).astype(F32)
    col = np.where((rand_per_id(ID, s + 3) < 0.6)[..., None], hex2rgb("#2d5a8a"), hex2rgb("#c9892f"))
    alb = lerp(base, col, (np.clip(motif, 0, 1) * deco)[..., None])
    alb = lerp(hex2rgb("#d6cfc1"), alb, tile)
    pillow = np.clip(e / 0.01, 0, 1) ** 0.5
    h = tile * (0.0008 * pillow + band(n, 30, s + 4) * 0.0001) - (1 - tile) * 0.0012
    rough = np.clip(0.08 + 0.05 * noise(n, n / 20, s + 5) + 0.7 * (1 - tile), 0.05, 0.9)
    return dict(albedo=alb, height=h, rough=rough, mask=tile * (1 - np.clip(motif, 0, 1) * deco))


@register("TissuProvence", 0.5, 512)
def t_tissu(n, size):
    """Indienne provençale : petites fleurs et rinceaux sur un fond teinté par instance (masque = fond)."""
    s = 1401
    yy, xx = np.mgrid[0:n, 0:n].astype(F32)
    per = n / 6
    u, v = (xx % per) / per, (yy % per) / per
    row = np.floor(yy / per) % 2
    u = (u + 0.5 * row) % 1.0
    r = np.hypot(u - 0.5, v - 0.5)
    ang = np.arctan2(v - 0.5, u - 0.5)
    petals = smooth(0.40, 0.36, r * (1.0 - 0.3 * np.cos(5 * ang)))
    heart = smooth(0.12, 0.1, r)
    vine = smooth(0.06, 0.035, np.abs(np.sin((xx / per + 0.25 * np.sin(yy / per * 2 * np.pi)) * np.pi)) * 0.25)
    ground_ = 1.0 - np.clip(petals + vine * 0.8, 0, 1)
    alb = np.ones((n, n, 3), F32) * 0.92
    alb = lerp(alb, hex2rgb("#f3e6c4"), petals[..., None])
    alb = lerp(alb, hex2rgb("#b3372a"), heart[..., None])
    alb = lerp(alb, hex2rgb("#3f6b3a"), (vine * (1 - petals))[..., None] * 0.9)
    weave = np.sin(xx / 1.5 * np.pi) * np.sin(yy / 1.5 * np.pi)
    alb *= (1 + 0.03 * weave)[..., None]
    h = weave * 0.00015
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.92, F32), mask=ground_)



@register("Carrosserie", 1.0, 1024)
def t_carrosserie(n, size):
    """Peinture de voiture abandonnée : poussière, coulures, rayures, plaques de rouille (masque = peinture, teintée par instance)."""
    s = 1501
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) / n
    dust = np.clip(0.35 + 0.5 * noise(n, n / 3, s) + 0.25 * (yy ** 1.5), 0, 1)
    streak = np.clip(noise(n, n / 40, s + 1, aniso=8.0) * 0.5 + 0.5, 0, 1) * yy
    rust = smooth(1.2, 2.0, noise(n, n / 6, s + 2) + 0.8 * band(n, n / 30, s + 3))
    scr = np.zeros((n, n), F32)
    rng = np.random.default_rng(s + 4)
    for _ in range(90):
        x0, y0 = rng.random(2) * n
        ang = rng.normal(0, 0.4)
        L = rng.uniform(0.03, 0.2) * n
        t = np.linspace(0, 1, int(L))
        px = ((x0 + np.cos(ang) * L * t) % n).astype(int)
        py = ((y0 + np.sin(ang) * L * t) % n).astype(int)
        scr[py, px] = 1.0
    scr = np.clip(blur(scr, 0.8) * 3, 0, 1)
    paint = np.ones((n, n, 3), F32) * 0.85
    alb = lerp(paint, hex2rgb("#b9ab92"), (dust * 0.45 + streak * 0.25)[..., None])
    alb = lerp(alb, hex2rgb("#d8d4cc"), scr[..., None] * 0.6)
    alb = lerp(alb, hex2rgb("#6b3a1e") * (0.8 + 0.3 * noise(n, n / 50, s + 5))[..., None], rust[..., None])
    h = rust * 0.0006 * noise(n, n / 60, s + 6) - scr * 0.0002
    rough = np.clip(0.35 + 0.45 * dust + 0.4 * rust, 0.2, 1)
    mask = np.clip(1 - rust - scr * 0.5, 0, 1)
    return dict(albedo=alb, height=h, rough=rough, mask=mask)



@register("Brique", 1.0, 1024)
def t_brique(n, size):
    """Briques de terre cuite faites main (22 x 5,5 cm), appareil en panneresses, joints de chaux, extrémités plus cuites."""
    s = 2101
    px = size / n
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * px
    bh, bw, jt = size / 16, size / 4.5, 0.009
    wy = noise(n, n / 4, s, beta=3.0) * 0.003
    row = np.floor((yy + wy) / bh).astype(np.int64)
    xs = (xx + (row % 2) * bw / 2 + noise(n, n / 5, s + 1, beta=3.0) * 0.003) % size
    colk = np.floor(xs / bw).astype(np.int64)
    ID = row * 100 + colk
    fy = ((yy + wy) / bh) % 1.0 * bh
    fx = (xs / bw) % 1.0 * bw
    d = np.minimum(np.minimum(fy, bh - fy), np.minimum(fx, bw - fx))
    d = d + band(n, n / 40, s + 2) * 0.0015
    brick = smooth(jt / 2, jt / 2 + 0.002, d)
    bev = smooth(jt / 2, jt / 2 + 0.01, d)
    pal = [hex2rgb(c) for c in ("#b5553a", "#a34a33", "#c46a45", "#9b4632", "#bb6040", "#8f3f2c", "#c77b52")]
    alb = palette_pick(ID, pal, s + 3) * (0.88 + 0.22 * rand_per_id(ID, s + 4))[..., None]
    burnt = smooth(0.35, 0.0, np.minimum(fx, bw - fx) / bw) * (rand_per_id(ID, s + 5) > 0.6)
    alb = lerp(alb, alb * 0.55, burnt[..., None] * 0.6)
    alb *= (1 + 0.08 * noise(n, n / 25, s + 6) + 0.05 * band(n, 4, s + 7))[..., None]
    efflo = smooth(1.9, 2.5, noise(n, n / 12, s + 8)) * 0.35
    alb = lerp(alb, hex2rgb("#e2d9c6"), efflo[..., None])
    mortar = hex2rgb("#cfc4ad") * (0.9 + 0.1 * noise(n, 3, s + 9))[..., None]
    alb = lerp(mortar, alb, brick[..., None])
    h = brick * (0.004 * bev + (rand_per_id(ID, s + 10) - 0.5) * 0.002 + band(n, 10, s + 11) * 0.0004) - (1 - brick) * 0.004
    rough = np.clip(0.85 + 0.08 * noise(n, n / 20, s + 12) - efflo * 0.1, 0.5, 1)
    return dict(albedo=alb, height=h, rough=rough)


def build(names=None, preview_dir="texprev"):
    os.makedirs(preview_dir, exist_ok=True)
    for name, cfg in TEX.items():
        if names and name not in names:
            continue
        t = time.time()
        n, size = cfg["n"], cfg["size_m"]
        r = cfg["fn"](n, size)
        alb = np.clip(r["albedo"], 0, 1).astype(F32)
        px = size / n
        ao = ao_from_height(r["height"], px, depth_m=r.get("ao_depth", 0.012))
        mask = r.get("mask")
        nrm, ao = save_set(name, OUT, alb, r["height"], px, r["rough"], ao=ao, mask=mask, alpha=r.get("alpha"))
        pv = preview(alb, nrm, ao, tiles=2)
        pv.thumbnail((768, 768))
        pv.save(f"{preview_dir}/{name}.jpg", quality=88)
        print(f"{name}: {time.time() - t:.1f}s", flush=True)


if __name__ == "__main__":
    build(sys.argv[1:] or None)
