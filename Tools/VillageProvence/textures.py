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
LIMESTONE = [hex2rgb(h) for h in ("#cbbb9c", "#c0b4a1", "#d3c09a", "#b9a78b", "#c8ad84", "#aa9e8e", "#d9cfb8", "#bca88a")]


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
    bulge = (0.004 + 0.016 * rand_per_id(ID, seed + 7)) * np.sqrt(dn)
    edge = smooth(j, j + 0.025 + 0.02 * rand_per_id(ID, seed + 8), d)
    surf = band(n, n / 60, seed + 9) * 0.0025 + band(n, 8, seed + 10) * 0.0007 + noise(n, 3, seed + 11) * 0.0002
    stone = (d > j).astype(F32)
    h = stone * (0.012 * edge + bulge + surf) + (1 - stone) * (noise(n, n / 50, seed + 12) * 0.0015 - 0.004)
    col = palette_pick(ID, palette, seed + 13)
    bright = 0.9 + 0.2 * rand_per_id(ID, seed + 14)
    var = 1 + 0.06 * noise(n, n / 20, seed + 15) + 0.04 * band(n, 6, seed + 16)
    alb = col * (bright * var)[..., None]
    alb *= (0.8 + 0.2 * edge)[..., None]
    mortar = hex2rgb("#cdc3ae") * (0.9 + 0.08 * noise(n, n / 30, seed + 17))[..., None]
    alb = lerp(mortar, alb, stone)
    # lichens et coulures d'oxyde
    lich = smooth(2.1, 2.5, noise(n, n / 25, seed + 18) + 0.6 * band(n, 12, seed + 19)) * stone
    alb = lerp(alb, hex2rgb("#bda05a") * (0.9 + 0.1 * band(n, 5, seed + 20))[..., None], lich * 0.7)
    rust = smooth(1.6, 2.6, blur_y(noise(n, n / 40, seed + 21), 30)) * 0.25
    alb = lerp(alb, alb * hex2rgb("#b07a50"), rust)
    rough = np.clip(0.82 + 0.08 * noise(n, n / 40, seed + 22) + 0.1 * (1 - stone) - 0.08 * edge * (1 - dn), 0.5, 1)
    return dict(alb=alb, h=h, rough=rough, stone=stone, ID=ID)


@register("PierreMoellons", 3.0, 2048)
def t_rubble(n, size):
    r = rubble(n, size, 101)
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
    tool = band(n, 5, 205, aniso=3.0) * 0.0004 + band(n, n / 25, 206) * 0.0015 + noise(n, 4, 207) * 0.0002
    h = stone * (0.006 * edge + tool + (rand_per_id(ID, 208) - 0.5) * 0.004) - (1 - stone) * 0.004
    base = [hex2rgb(c) for c in ("#d9c9a8", "#d1bf9b", "#cdbfa6", "#dccfb2", "#c9b28c", "#c4b8a2")]
    col = palette_pick(ID, base, 209)
    var = 1 + 0.05 * noise(n, n / 10, 210) + 0.035 * band(n, 10, 211)
    alb = col * ((0.93 + 0.12 * rand_per_id(ID, 212)) * var)[..., None]
    grime = smooth(0.8, 2.2, blur_y(noise(n, n / 30, 213), 40)) * 0.18
    alb *= (1 - grime)[..., None]
    alb = lerp(hex2rgb("#c9bea8"), alb, stone)
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
def planks(n, size, seed, width=0.12, base_col="#8a7a66", paint=None, age=0.5, vertical=True):
    px = size / n
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) * px
    npl = max(1, int(round(size / width)))
    w = size / npl
    k = np.floor(xx / w).astype(np.int64)
    xl = xx - k * w
    gap = (xl < 0.004) | (xl > w - 0.004)
    rng = np.random.default_rng(seed)
    grain = band(n, 40, seed + 1, aniso=12.0) * 0.6 + band(n, 12, seed + 2, aniso=20.0) * 0.4
    knots = smooth(2.5, 3.0, noise(n, n / 12, seed + 3))
    wood = hex2rgb(base_col) * (0.85 + 0.25 * rand_per_id(k % npl, seed + 4, npl))[..., None]
    wood = wood * (1 + 0.12 * grain + 0.1 * band(n, n / 10, seed + 5, aniso=8.0))[..., None]
    wood = lerp(wood, wood * 0.5, knots)
    h = grain * 0.0006 - gap * 0.003 + band(n, n / 8, seed + 6) * 0.0005
    alb = wood
    mask = np.zeros((n, n), F32)
    rough = np.clip(0.8 + 0.1 * grain, 0, 1)
    if paint is not None:
        flake = smooth(0.9 + 1.4 * (1 - age), 1.2 + 1.4 * (1 - age), noise(n, n / 8, seed + 7) + 0.6 * band(n, 30, seed + 8, aniso=6.0))
        pcol = np.ones(3, F32) * 0.92 if paint == "white" else hex2rgb(paint)
        painted = pcol * (0.95 + 0.05 * grain)[..., None]
        alb = lerp(painted, wood, flake)
        mask = 1 - flake
        h = h + (1 - flake) * 0.0004
        rough = np.clip(lerp(0.55 + 0.1 * noise(n, 20, seed + 9), rough, flake), 0, 1)
    alb = np.where(gap[..., None], alb * 0.35, alb)
    return dict(albedo=alb, height=h, rough=rough, mask=mask)


@register("BoisPeint", 1.0, 1024)
def t_wood_painted(n, size):
    return planks(n, size, 701, width=0.13, base_col="#8f8375", paint="white", age=0.55)


@register("BoisBrut", 1.0, 1024)
def t_wood_raw(n, size):
    return planks(n, size, 751, width=0.16, base_col="#8a7560")


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


@register("EcorceOlivier", 1.0, 1024)
def t_bark_olive(n, size):
    s = 1851
    fib = band(n, n / 30, s, aniso=0.12) * 0.7 + band(n, n / 80, s + 1, aniso=0.15) * 0.3
    wx = noise(n, n / 3, s + 2) * 40
    fib = warp(fib, wx, wx * 0)
    groove = smooth(0.8, 2.0, -fib)
    alb = hex2rgb("#8a8578") * (1 + 0.15 * fib)[..., None]
    alb = lerp(alb, hex2rgb("#3c3a34"), groove * 0.7)
    lich = smooth(1.8, 2.4, noise(n, n / 20, s + 3))
    alb = lerp(alb, hex2rgb("#a9ab93"), lich * 0.6)
    h = fib * 0.004 - groove * 0.006
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.85, F32))


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
    s = 1951
    fis = band(n, n / 14, s, aniso=0.2) + 0.4 * band(n, n / 40, s + 1, aniso=0.25)
    wx = noise(n, n / 4, s + 2) * 20
    fis = warp(fis, wx, wx * 0)
    ridge = smooth(-0.3, 0.8, fis)
    alb = hex2rgb("#6c665c") * (0.7 + 0.4 * ridge)[..., None] * (1 + 0.06 * band(n, 6, s + 3))[..., None]
    moss = smooth(1.7, 2.3, noise(n, n / 10, s + 4))
    alb = lerp(alb, hex2rgb("#6f7447"), moss * 0.5)
    h = ridge * 0.01
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.9, F32))


@register("Eau", 2.0, 512)
def t_water(n, size):
    s = 2001
    h = band(n, n / 6, s) * 0.004 + band(n, n / 16, s + 1) * 0.0015
    alb = np.ones((n, n, 3), F32) * hex2rgb("#2f5f6b")
    return dict(albedo=alb, height=h, rough=np.full((n, n), 0.05, F32))


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
