"""Château des Ocres : une très grande forteresse provençale dans la forêt dense, du côté du quartier perché.

Plan (repère local : a vers la porte, tournée vers le quartier ; b à gauche) :
- enceinte irrégulière d'environ 190 x 150 m, courtines de 15 m à chemin de ronde crénelé, tours rondes à talus et
  mâchicoulis (certaines coiffées de toits coniques en tuiles), châtelet d'entrée à deux tours et herse ;
- fossé sec de 8 m de profondeur tout autour, franchi par une levée de terre bordée de parapets ;
- basse-cour (communs, écuries, grange, puits) séparée de la haute-cour par un mur à deux tours-portes ;
- haute-cour : donjon carré de 46 m à échauguettes, logis seigneurial à trois niveaux, chapelle à clocher-mur ;
- escaliers de pierre vers le chemin de ronde (parkour : on peut faire le tour des remparts).
Le château est posé sur une plate-forme aplanie, sur une butte au-dessus de la forêt."""
import math
import numpy as np
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from geomlib import box, revolve, planar_polygon, WHITE

STONE, WALL, ROOF, DARK = "PierreGard", "PierreGard", "TuilesCanal", (24, 21, 18, 255)
HW, TW = 15.0, 3.2               # courtines : hauteur au-dessus de la cour, épaisseur
HT = 23.0                        # tours
MOAT_IN, MOAT_OUT, MOAT_D = 5.0, 22.0, 8.0
ENC = [(92, -26), (92, 26), (64, 66), (-18, 74), (-78, 52), (-96, 4), (-82, -52), (-14, -74), (58, -66)]
ROOFED = {2, 4, 6}               # tours d'angle coiffées d'un toit conique


class Frame:
    def __init__(self, C, u):
        self.C = np.asarray(C, float)
        self.u = np.asarray(u, float) / np.linalg.norm(u)
        self.n = np.array([-self.u[1], self.u[0]])
        self.yaw = math.atan2(self.u[1], self.u[0])

    def P(self, a, b):
        return self.C + self.u * a + self.n * b


# ------------------------------------------------------------------ choix du site et plan
def pick_site(band, avoid, ground_at, C_old, C_new, rng):
    """Point haut et régulier de la forêt dense, du côté du quartier perché (plus près de lui que du vieux village)."""
    x0, y0, x1, y1 = band.bounds
    inner = band.buffer(-120.0)
    X, Y = np.meshgrid(np.arange(x0, x1, 30.0), np.arange(y0, y1, 30.0))
    X, Y = X.ravel(), Y.ravel()
    pts = shapely.points(X, Y)
    ok = shapely.contains(inner, pts) & (shapely.distance(avoid, pts) > 170.0)
    ok &= shapely.distance(C_new, pts) < shapely.distance(C_old, pts) - 250.0
    X, Y = X[ok], Y[ok]
    if not len(X):
        return None
    ang = np.linspace(0, 2 * math.pi, 16, endpoint=False)
    off = np.array([(r * math.cos(t), r * math.sin(t)) for r in (0.0, 60.0, 110.0) for t in ang])
    zz = ground_at((X[:, None] + off[None, :, 0]).ravel(), (Y[:, None] + off[None, :, 1]).ravel()).reshape(len(X), -1)
    score = zz.mean(1) - 0.9 * zz.std(1) - 0.012 * shapely.distance(C_new, shapely.points(X, Y))
    k = int(np.argmax(score))
    return Point(X[k], Y[k])


def layout(site, C_new, ground_at):
    """ground_at : fonction vectorielle (xs, ys) -> altitudes."""
    F = Frame((site.x, site.y), (C_new.x - site.x, C_new.y - site.y))
    enc = Polygon([F.P(a, b) for a, b in ENC])
    Q = np.array([F.P(a, b) for a in np.arange(-90, 91, 10) for b in np.arange(-70, 71, 10)])
    Q = Q[shapely.contains(enc, shapely.points(Q[:, 0], Q[:, 1]))]
    zs = ground_at(Q[:, 0], Q[:, 1])
    Z0 = float(np.percentile(zs, 70)) + 3.0
    gate = F.P(92, 0)
    L = dict(C=F.C, u=F.u, n=F.n, yaw=F.yaw, Z0=Z0, enc=enc, gate=gate)
    # tours : aux angles, au milieu des longues courtines, et le châtelet
    towers = []
    for k, (a, b) in enumerate(ENC):
        if k in (0, 1):
            continue
        towers.append((F.P(a, b), 6.5, HT, k in ROOFED))
    for k in range(len(ENC)):
        a0, b0 = ENC[k]
        a1, b1 = ENC[(k + 1) % len(ENC)]
        if math.hypot(a1 - a0, b1 - b0) > 70 and k != 0:
            towers.append((F.P((a0 + a1) / 2, (b0 + b1) / 2), 5.2, HT - 3.0, False))
    towers += [(F.P(94, -10.5), 6.8, HT + 3.0, True), (F.P(94, 10.5), 6.8, HT + 3.0, True)]
    towers += [(F.P(92, -26), 5.5, HT - 2.0, False), (F.P(92, 26), 5.5, HT - 2.0, False)]
    L["towers"] = towers
    # mur de séparation basse-cour / haute-cour, porte au milieu entre deux tours carrées
    L["inner"] = [(F.P(18, -71), F.P(18, -4.0)), (F.P(18, 4.0), F.P(18, 70.5))]
    L["inner_towers"] = [F.P(18, -7.5), F.P(18, 7.5)]
    # bâtiments (centre, longueur le long de u, largeur, hauteur des murs, yaw, toit)
    yaw = F.yaw
    d_logis = np.array(ENC[7]) - np.array(ENC[6])
    ylog = yaw + math.atan2(d_logis[1], d_logis[0])
    mid = (np.array(ENC[6]) + np.array(ENC[7])) / 2
    nin = np.array([-d_logis[1], d_logis[0]]) / np.linalg.norm(d_logis)
    L["logis"] = (F.P(*(mid + nin * 11.5)), 58.0, 15.0, 16.0, ylog)
    L["keep"] = (F.P(-46, 16), 26.0, 24.0, 46.0, yaw)
    L["chapel"] = (F.P(-8, 50), 24.0, 11.0, 11.0, yaw)
    L["communs"] = [(F.P(41, -52), 38.0, 10.0, 7.5, yaw), (F.P(50, 52), 32.0, 11.0, 8.0, yaw),
                    (F.P(-68, -8), 10.0, 18.0, 7.0, yaw)]
    L["well"] = F.P(46, 18)
    # levée de terre sur le fossé
    L["causeway"] = LineString([F.P(90, 0), F.P(90 + MOAT_OUT + 12, 0)])
    L["path"] = [F.P(122, 0), F.P(92, 0), F.P(18, 0), F.P(-30, 4)]
    blds = [L["logis"], L["keep"], L["chapel"]] + L["communs"]
    solids = [Point(*p).buffer(r + 2.4) for p, r, h, rf in towers] + [enc.exterior.buffer(TW / 2 + 0.6)]
    solids += [LineString([a, b]).buffer(TW / 2) for a, b in L["inner"]]
    solids += [_rect(c, l_, w_, y_).buffer(0.5) for c, l_, w_, h_, y_ in blds]
    L["solids"] = unary_union(solids)
    L["foot"] = enc.buffer(8.0)
    L["frame"] = F
    return L


def _rect(c, l_, w_, yaw):
    u = np.array([math.cos(yaw), math.sin(yaw)]); n = np.array([-u[1], u[0]])
    c = np.asarray(c)
    return Polygon([c + u * sa * l_ / 2 + n * sb * w_ / 2 for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))])


# ------------------------------------------------------------------ allée : chemin de moindre pente jusqu'au quartier
def route(ground, XS, YS, start, targets, forbid, costly, step=4.0, gmax=0.11):
    """Plus court chemin sur une grille (pas de step m, 16 voisins) où chaque arête coûte sa longueur, fortement majorée
    au-delà de gmax de pente (l'allée descend la butte en lacets). targets : lignes d'arrivée ; forbid : interdit ;
    costly : à éviter (maisons)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    from common import grid_sample
    pts_t = unary_union(targets)
    x0, y0, x1, y1 = unary_union([Point(start).buffer(60), pts_t.envelope]).bounds
    x0, y0, x1, y1 = x0 - 200, y0 - 200, x1 + 200, y1 + 200
    xs, ys = np.arange(x0, x1, step), np.arange(y0, y1, step)
    X, Y = np.meshgrid(xs, ys)
    ny, nx = X.shape
    Z = grid_sample(ground, X.ravel(), Y.ravel()).reshape(ny, nx)
    P = shapely.points(X.ravel(), Y.ravel())
    bad = shapely.contains(forbid, P).reshape(ny, nx)
    pen = np.where(shapely.contains(costly, P).reshape(ny, nx), 30.0, 1.0)
    idx = np.arange(nx * ny).reshape(ny, nx)
    A, B, Wt = [], [], []
    for dj, di in [(0, 1), (1, 0), (1, 1), (1, -1), (1, 2), (2, 1), (1, -2), (2, -1)]:
        j0, j1 = max(0, -dj), ny - max(0, dj)
        i0, i1 = max(0, -di), nx - max(0, di)
        a = idx[j0:j1, i0:i1]; b = idx[j0 + dj:j1 + dj, i0 + di:i1 + di]
        L_ = step * math.hypot(di, dj)
        g = np.abs(Z[j0 + dj:j1 + dj, i0 + di:i1 + di] - Z[j0:j1, i0:i1]) / L_
        w = L_ * (1.0 + 60.0 * np.clip(g - gmax, 0, None) + 400.0 * np.clip(g - 0.16, 0, None)) * 0.5 * (
            pen[j0:j1, i0:i1] + pen[j0 + dj:j1 + dj, i0 + di:i1 + di])
        ok = ~(bad[j0:j1, i0:i1] | bad[j0 + dj:j1 + dj, i0 + di:i1 + di])
        A.append(a[ok]); B.append(b[ok]); Wt.append(w[ok])
    A, B, Wt = np.concatenate(A), np.concatenate(B), np.concatenate(Wt)
    Gm = coo_matrix((np.concatenate([Wt, Wt]), (np.concatenate([A, B]), np.concatenate([B, A]))), shape=(nx * ny, nx * ny)).tocsr()
    si = int(np.clip(round((start[1] - y0) / step), 0, ny - 1)) * nx + int(np.clip(round((start[0] - x0) / step), 0, nx - 1))
    dist, pred = dijkstra(Gm, indices=si, return_predecessors=True)
    near = shapely.distance(pts_t, P) < step * 0.8
    cand = np.nonzero(near & np.isfinite(dist))[0]
    if not len(cand):
        return None
    k = int(cand[np.argmin(dist[cand])])
    path = []
    while k >= 0 and k != si:
        path.append((X.ravel()[k], Y.ravel()[k]))
        k = pred[k]
    path.append((X.ravel()[si], Y.ravel()[si]))
    path = np.array(path[::-1])
    # lissage (les virages restent des lacets souples) ; départ exact sur la levée
    from scipy.ndimage import gaussian_filter1d
    sm = np.column_stack([gaussian_filter1d(path[:, 0], 2.0, mode="nearest"), gaussian_filter1d(path[:, 1], 2.0, mode="nearest")])
    sm[0] = start
    return LineString(sm).simplify(0.8)


# ------------------------------------------------------------------ terrain : plate-forme, fossé sec, butte, levée de terre
def shape_ground(ground, Xg, Yg, L):
    """Renvoie le nouveau sol autour du château."""
    Z0 = L["Z0"]
    x0, y0, x1, y1 = L["enc"].buffer(160).bounds
    m = (Xg >= x0) & (Xg <= x1) & (Yg >= y0) & (Yg <= y1)
    X, Y = Xg[m], Yg[m]
    pts = shapely.points(X, Y)
    inside = shapely.contains(L["enc"], pts)
    d = shapely.distance(L["enc"].exterior, pts)
    d = np.where(inside, -d, d)
    g = ground[m].astype(np.float64)
    # butte : le château domine la forêt ; raccord doux sur 130 m
    mound = Z0 - 1.2 + (g - Z0 + 1.2) * np.clip((d - MOAT_OUT) / 130.0, 0, 1) ** 1.4
    z = np.where(d < MOAT_IN, Z0, mound)
    # fossé sec à fond plat et talus raides
    t = np.clip((d - MOAT_IN) / (MOAT_OUT - MOAT_IN), 0, 1)
    bowl = MOAT_D * np.clip(np.sin(math.pi * t) * 1.6, 0, 1)
    dc = shapely.distance(L["causeway"], pts)
    cw = np.clip((dc - 4.5) / 3.0, 0, 1)               # levée de terre : 9 m de large, pas de fossé
    moat = (d > MOAT_IN) & (d < MOAT_OUT)
    z = np.where(moat, z - bowl * cw, z)
    z = np.where((dc < 4.5) & (d > -2) & (d < MOAT_OUT + 12), Z0 - 0.15, z)
    out = ground.copy()
    out[m] = z.astype(ground.dtype)
    return out


# ------------------------------------------------------------------ maillages
def _crenels(mb, a, b, zt, out_n, th=0.8):
    """Parapet et merlons sur le bord extérieur d'un mur (a -> b), out_n : normale extérieure."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L_ = float(np.linalg.norm(b - a))
    if L_ < 0.5:
        return
    u = (b - a) / L_
    yaw = math.atan2(u[1], u[0])
    base = (a + b) / 2 + out_n * (TW / 2 - th / 2)
    box(mb, STONE, (base[0], base[1], zt + 0.5), (L_, th, 1.0), yaw=yaw, uv_scale=3.0)
    k = max(1, int(L_ / 2.6))
    for i in range(k):
        c = a + u * (L_ * (i + 0.5) / k) + out_n * (TW / 2 - th / 2)
        box(mb, STONE, (c[0], c[1], zt + 1.65), (1.45, th, 1.3), yaw=yaw, uv_scale=3.0)


def _wall(mb_at, a, b, zb_fun, zt, out_n, crenel=True, T=TW, slits=True):
    a, b = np.asarray(a, float), np.asarray(b, float)
    L_ = float(np.linalg.norm(b - a))
    k = max(1, int(math.ceil(L_ / 7.0)))
    u = (b - a) / L_
    yaw = math.atan2(u[1], u[0])
    for i in range(k):
        p, q = a + u * (L_ * i / k), a + u * (L_ * (i + 1) / k)
        c = (p + q) / 2
        zb = min(zb_fun(*p), zb_fun(*q), zb_fun(*c)) - 1.5
        mb = mb_at(*c)
        box(mb, WALL, (c[0], c[1], (zb + zt) / 2), (L_ / k + 0.02, T, zt - zb), yaw=yaw, uv_scale=3.0)
        # talus (glacis maçonné) au pied, côté fossé
        tb = c + out_n * (T / 2 + 0.6)
        box(mb, WALL, (tb[0], tb[1], (zb + zt - HW + 3.0) / 2), (L_ / k + 0.02, 1.2, max(0.5, zt - HW + 3.0 - zb)), yaw=yaw, uv_scale=3.0)
        if crenel:
            _crenels(mb, p, q, zt, out_n)
        if slits and i % 2 == 1:
            s_ = c + out_n * (T / 2 + 0.03)
            box(mb, STONE, (s_[0], s_[1], zt - 5.5), (0.22, 0.1, 1.9), yaw=yaw, col=DARK, uv_scale=3.0)


def _tower(mb, p, r, H, roof, Z0, zb):
    x, y = p
    rel = zb - Z0
    prof = [(r + 2.6, rel), (r + 2.6, rel + 0.2), (r + 0.4, 5.0), (r, 7.0), (r, H - 2.4), (r + 0.9, H - 1.5), (r + 0.9, H)]
    if roof:
        revolve(mb, STONE, prof + [(r + 0.9, H + 0.01), (0.0, H + 0.01)], (x, y, Z0), segs=28, u_tile=3.0, v_tile=3.0)
        revolve(mb, ROOF, [(r + 1.4, H - 0.3), (r * 0.08, H + 2.1 * r), (0.0, H + 2.1 * r + 0.05)], (x, y, Z0), segs=28,
                u_tile=2.0, v_tile=2.0)
        revolve(mb, "Fer", [(0.08, H + 2.1 * r), (0.05, H + 2.1 * r + 3.0), (0.0, H + 2.1 * r + 3.05)], (x, y, Z0), segs=6)
    else:
        revolve(mb, STONE, prof + [(r + 0.9, H + 1.1), (r + 0.1, H + 1.1), (r + 0.1, H + 0.01), (0.0, H + 0.01)], (x, y, Z0),
                segs=28, u_tile=3.0, v_tile=3.0)
        per = 2 * math.pi * (r + 0.5)
        k = max(8, int(per / 2.7))
        for i in range(k):
            t = 2 * math.pi * (i + 0.5) / k
            c = (x + (r + 0.5) * math.cos(t), y + (r + 0.5) * math.sin(t))
            box(mb, STONE, (c[0], c[1], Z0 + H + 1.7), (0.8, 1.35, 1.2), yaw=t, uv_scale=3.0)
    # consoles des mâchicoulis
    k = max(10, int(2 * math.pi * r / 1.6))
    for i in range(k):
        t = 2 * math.pi * i / k
        c = (x + (r + 0.45) * math.cos(t), y + (r + 0.45) * math.sin(t))
        box(mb, STONE, (c[0], c[1], Z0 + H - 2.2), (0.9, 0.35, 0.9), yaw=t, uv_scale=3.0)
    # archères
    for j, zz in enumerate(np.arange(8.0, H - 4.0, 5.0)):
        for i in range(4):
            t = math.pi / 4 * (2 * i + (j % 2))
            c = (x + (r + 0.02) * math.cos(t), y + (r + 0.02) * math.sin(t))
            box(mb, STONE, (c[0], c[1], Z0 + zz), (0.12, 0.24, 1.8), yaw=t, col=DARK, uv_scale=3.0)


def _gable_roof(mb, c, l_, w_, zt, yaw, pitch=0.5, mat=ROOF, over=0.5):
    u = np.array([math.cos(yaw), math.sin(yaw)]); n = np.array([-u[1], u[0]])
    h = w_ / 2 * math.tan(pitch)
    sl = (w_ / 2 + over) / math.cos(pitch)
    for s in (1, -1):
        cc = np.asarray(c) + n * s * (w_ / 4 + over / 2) * 1.0
        box(mb, mat, (cc[0], cc[1], zt + h / 2 - over * math.tan(pitch) / 2 + 0.15), (l_ + 2 * over, sl, 0.28), yaw=yaw,
            pitch=-s * pitch, uv_scale=2.0)
    # pignons
    for s in (1, -1):
        org = np.array([*(np.asarray(c) + u * s * l_ / 2), zt])
        e1 = np.array([*(n * s), 0.0])
        planar_polygon(mb, STONE, [(-w_ / 2, 0), (w_ / 2, 0), (0, h)], [], org, e1, np.array([0, 0, 1.0]),
                       lambda v2, P: np.stack([v2[:, 0] / 3.0, -v2[:, 1] / 3.0], -1))
    box(mb, STONE, (c[0], c[1], zt + h + 0.1), (l_ + 2 * over, 0.45, 0.3), yaw=yaw, uv_scale=3.0)   # faîtage


def _windows(mb, c, l_, w_, yaw, z0, floors, fh, step=5.0, big=False):
    u = np.array([math.cos(yaw), math.sin(yaw)]); n = np.array([-u[1], u[0]])
    k = max(1, int(l_ / step))
    for f in range(floors):
        zc = z0 + fh * f + fh * 0.55
        for i in range(k):
            a = -l_ / 2 + l_ * (i + 0.5) / k
            for s in (1, -1):
                p = np.asarray(c) + u * a + n * s * (w_ / 2 + 0.03)
                ww, hh = (1.3, 2.3) if big and f > 0 else (0.9, 1.6)
                box(mb, STONE, (p[0], p[1], zc), (ww + 0.4, 0.12, hh + 0.4), yaw=yaw, uv_scale=3.0)
                q = p + n * s * 0.04
                box(mb, "Verre", (q[0], q[1], zc), (ww, 0.08, hh), yaw=yaw, col=(40, 44, 46, 255))
                if big and f > 0:        # croisée de pierre
                    box(mb, STONE, (q[0] + n[0] * s * 0.03, q[1] + n[1] * s * 0.03, zc), (0.14, 0.1, hh), yaw=yaw, uv_scale=3.0)
                    box(mb, STONE, (q[0] + n[0] * s * 0.03, q[1] + n[1] * s * 0.03, zc + hh * 0.18), (ww, 0.1, 0.14), yaw=yaw, uv_scale=3.0)


def _house(mb, c, l_, w_, h_, yaw, Z0, zb, floors, big=False, mat=STONE):
    box(mb, mat, (c[0], c[1], (zb + Z0 + h_) / 2), (l_, w_, Z0 + h_ - zb), yaw=yaw, uv_scale=3.0)
    box(mb, STONE, (c[0], c[1], Z0 + h_ - 0.2), (l_ + 0.3, w_ + 0.3, 0.4), yaw=yaw, uv_scale=3.0)    # corniche
    _gable_roof(mb, c, l_, w_, Z0 + h_, yaw)
    _windows(mb, c, l_, w_, yaw, Z0, floors, h_ / floors, big=big)
    u = np.array([math.cos(yaw), math.sin(yaw)]); n = np.array([-u[1], u[0]])
    # porte sur la face intérieure (côté -n par convention : on met une porte de chaque côté)
    for s in (1, -1):
        p = np.asarray(c) + n * s * (w_ / 2 + 0.05)
        box(mb, "BoisBrut", (p[0], p[1], Z0 + 1.4), (1.8, 0.14, 2.8), yaw=yaw, col=(92, 70, 48, 255))
        box(mb, STONE, (p[0], p[1], Z0 + 3.0), (2.6, 0.3, 0.5), yaw=yaw, uv_scale=3.0)


def _keep(mb_at, c, l_, w_, H, yaw, Z0, zat):
    mb = mb_at(*c)
    u = np.array([math.cos(yaw), math.sin(yaw)]); n = np.array([-u[1], u[0]])
    zb = min(zat(*(np.asarray(c) + u * sa * l_ / 2 + n * sb * w_ / 2)) for sa in (-1, 1) for sb in (-1, 1)) - 1.0
    box(mb, STONE, (c[0], c[1], (zb + Z0 + 5) / 2), (l_ + 3.0, w_ + 3.0, Z0 + 5 - zb), yaw=yaw, uv_scale=3.0)     # talus
    box(mb, STONE, (c[0], c[1], Z0 + (H + 5.0) / 2), (l_, w_, H - 5.0), yaw=yaw, uv_scale=3.0)
    box(mb, STONE, (c[0], c[1], Z0 + H - 1.0), (l_ + 1.6, w_ + 1.6, 2.0), yaw=yaw, uv_scale=3.0)               # mâchicoulis
    for sa, sb, ll, ww in ((1, 0, 0.8, w_ + 1.6), (-1, 0, 0.8, w_ + 1.6), (0, 1, l_ + 1.6, 0.8), (0, -1, l_ + 1.6, 0.8)):
        p = np.asarray(c) + u * sa * (l_ / 2 + 0.4) + n * sb * (w_ / 2 + 0.4)
        box(mb, STONE, (p[0], p[1], Z0 + H + 0.5), (ll, ww, 1.0), yaw=yaw, uv_scale=3.0)
        edge = ww if sa else ll
        k = int(edge / 2.6)
        for i in range(k):
            t = -edge / 2 + edge * (i + 0.5) / k
            q = p + (n * t if sa else u * t)
            box(mb, STONE, (q[0], q[1], Z0 + H + 1.65), (0.8 if sa else 1.4, 1.4 if sa else 0.8, 1.3), yaw=yaw, uv_scale=3.0)
    # consoles sous le mâchicoulis
    for sa, sb, edge in ((1, 0, w_), (-1, 0, w_), (0, 1, l_), (0, -1, l_)):
        k = int(edge / 1.6)
        for i in range(k):
            t = -edge / 2 + edge * (i + 0.5) / k
            q = np.asarray(c) + u * sa * (l_ / 2 + 0.35) + n * sb * (w_ / 2 + 0.35) + (n * t if sa else u * t)
            box(mb, STONE, (q[0], q[1], Z0 + H - 2.6), (0.7, 0.7, 0.9), yaw=yaw, uv_scale=3.0)
    # échauguettes d'angle, à toit conique
    for sa in (-1, 1):
        for sb in (-1, 1):
            p = np.asarray(c) + u * sa * (l_ / 2 + 0.6) + n * sb * (w_ / 2 + 0.6)
            revolve(mb, STONE, [(0.0, H - 7.0), (1.2, H - 5.2), (2.0, H - 3.0), (2.0, H + 2.6), (2.0, H + 2.61), (0.0, H + 2.61)],
                    (p[0], p[1], Z0), segs=16, u_tile=3.0, v_tile=3.0)
            revolve(mb, ROOF, [(2.4, H + 2.4), (0.1, H + 7.0), (0.0, H + 7.05)], (p[0], p[1], Z0), segs=16, u_tile=2.0, v_tile=2.0)
    # tourelle d'escalier et fenêtres hautes
    p = np.asarray(c) - u * (l_ / 2 - 3.5) + n * (w_ / 2 - 3.5)
    revolve(mb, STONE, [(2.6, H - 1.0), (2.6, H + 6.0), (2.9, H + 6.01), (2.9, H + 7.0), (0.0, H + 7.01)], (p[0], p[1], Z0), segs=18,
            u_tile=3.0, v_tile=3.0)
    for s in (1, -1):
        for zz in (12.0, 20.0, 28.0, 36.0):
            for t in (-l_ / 4, l_ / 4):
                q = np.asarray(c) + n * s * (w_ / 2 + 0.03) + u * t
                box(mb, "Verre", (q[0], q[1], Z0 + zz), (1.0, 0.08, 2.4), yaw=yaw, col=(34, 36, 38, 255))
                box(mb, STONE, (q[0], q[1], Z0 + zz + 1.45), (1.6, 0.3, 0.4), yaw=yaw, uv_scale=3.0)
    # grande porte de la haute-cour (côté porte du château)
    q = np.asarray(c) + u * (l_ / 2 + 1.53)
    box(mb, "BoisBrut", (q[0], q[1], Z0 + 1.8), (0.14, 2.4, 3.6), yaw=yaw, col=(84, 62, 40, 255))
    box(mb, STONE, (q[0], q[1], Z0 + 4.0), (0.5, 3.4, 0.6), yaw=yaw, uv_scale=3.0)


def build(mb_at, L, zat, inst):
    Z0 = L["Z0"]
    enc = L["enc"]
    cx, cy = enc.centroid.x, enc.centroid.y
    pts = list(enc.exterior.coords)[:-1]
    gate = np.asarray(L["gate"])
    F = L["frame"]
    # courtines (ouverture de la porte entre les deux tours du châtelet)
    for k in range(len(pts)):
        a, b = np.asarray(pts[k]), np.asarray(pts[(k + 1) % len(pts)])
        mid = (a + b) / 2
        on = np.array([-(b - a)[1], (b - a)[0]]); on /= np.linalg.norm(on)
        if np.dot(on, mid - np.array([cx, cy])) < 0:
            on = -on
        if k == 0:              # face de la porte
            ua = (b - a) / np.linalg.norm(b - a)
            g0, g1 = gate - ua * 3.0, gate + ua * 3.0
            _wall(mb_at, a, g0, zat, Z0 + HW, on)
            _wall(mb_at, g1, b, zat, Z0 + HW, on)
            # linteau au-dessus du passage (7,5 m sous clé), bretèche et herse
            c = gate
            mb = mb_at(*c)
            box(mb, WALL, (c[0], c[1], Z0 + (7.5 + HW) / 2), (TW, 6.2, HW - 7.5), yaw=math.atan2(ua[1], ua[0]) + math.pi / 2,
                uv_scale=3.0)
            _crenels(mb, g0, g1, Z0 + HW, on)
            for i in range(9):
                q = gate + ua * (-2.6 + i * 0.65) + on * 0.6
                box(mb, "Fer", (q[0], q[1], Z0 + 5.4), (0.12, 0.12, 4.2), col=(40, 38, 36, 255))
            for zz in (4.0, 5.2, 6.4, 7.3):
                q = gate + on * 0.6
                box(mb, "Fer", (q[0], q[1], Z0 + zz), (6.0, 0.1, 0.1), yaw=math.atan2(ua[1], ua[0]), col=(40, 38, 36, 255))
            br = gate + on * (TW / 2 + 0.9)
            box(mb, STONE, (br[0], br[1], Z0 + HW - 2.5), (1.8, 4.0, 3.0), yaw=math.atan2(ua[1], ua[0]) + math.pi / 2, uv_scale=3.0)
            continue
        _wall(mb_at, a, b, zat, Z0 + HW, on)
    # tours
    for p, r, H, roof in L["towers"]:
        zb = min(zat(p[0] + (r + 2.6) * math.cos(t), p[1] + (r + 2.6) * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 10)) - 1.0
        _tower(mb_at(*p), p, r, H, roof, Z0, zb)
    # mur de la haute-cour et ses deux tours-portes carrées
    for a, b in L["inner"]:
        _wall(mb_at, a, b, zat, Z0 + 10.0, F.u, T=2.4, slits=False)
    for p in L["inner_towers"]:
        mb = mb_at(*p)
        box(mb, STONE, (p[0], p[1], Z0 + 9.0 - 0.75), (7.0, 7.0, 19.5), yaw=F.yaw, uv_scale=3.0)
        box(mb, STONE, (p[0], p[1], Z0 + 17.7), (7.8, 7.8, 1.2), yaw=F.yaw, uv_scale=3.0)
        _gable_roof(mb, p, 7.8, 7.8, Z0 + 18.3, F.yaw, pitch=0.6)
    # donjon, logis, chapelle, communs
    c, l_, w_, H, yaw = L["keep"]
    _keep(mb_at, c, l_, w_, H, yaw, Z0, zat)
    c, l_, w_, h_, yaw = L["logis"]
    _house(mb_at(*c), c, l_, w_, h_, yaw, Z0, Z0 - 1.5, 3, big=True)
    c, l_, w_, h_, yaw = L["chapel"]
    mb = mb_at(*c)
    _house(mb, c, l_, w_, h_, yaw, Z0, Z0 - 1.5, 1)
    u = np.array([math.cos(yaw), math.sin(yaw)])
    cm = np.asarray(c) - u * (l_ / 2 - 0.6)
    box(mb, STONE, (cm[0], cm[1], Z0 + h_ + 5.0), (1.2, 6.0, 7.0), yaw=yaw, uv_scale=3.0)     # clocher-mur
    revolve(mb, "Bronze", [(0.0, -0.9), (0.55, -0.85), (0.4, -0.2), (0.25, 0.3), (0.0, 0.35)], (cm[0], cm[1], Z0 + h_ + 5.6), segs=12)
    for (c, l_, w_, h_, yaw) in L["communs"]:
        _house(mb_at(*c), c, l_, w_, h_, yaw, Z0, Z0 - 1.5, 2, mat="PierreMoellons")
    # puits
    x, y = L["well"]
    mb = mb_at(x, y)
    revolve(mb, STONE, [(1.2, -0.3), (1.2, 0.9), (0.9, 0.9), (0.9, -0.1)], (x, y, Z0), segs=18, u_tile=3.0, v_tile=3.0)
    revolve(mb, "Eau", [(0.9, 0.0), (0.0, 0.0)], (x, y, Z0 - 1.2), segs=12)
    # chemin dallé de la porte au donjon
    pp = [np.asarray(p) for p in L["path"]]
    for p, q in zip(pp[:-1], pp[1:]):
        d = q - p
        ln_ = float(np.linalg.norm(d))
        c = (p + q) / 2
        box(mb_at(*c), "Calade", (c[0], c[1], Z0 - 0.08), (ln_ + 4.0, 4.0, 0.3), yaw=math.atan2(d[1], d[0]), uv_scale=2.0)
    # levée de terre : parapets bas de chaque côté
    a, b = np.asarray(L["causeway"].coords[0]), np.asarray(L["causeway"].coords[-1])
    d = (b - a) / np.linalg.norm(b - a); n = np.array([-d[1], d[0]])
    for s in (1, -1):
        c = (a + b) / 2 + n * s * 4.6
        box(mb_at(*c), STONE, (c[0], c[1], Z0 + 0.35), (float(np.linalg.norm(b - a)) - 2.0, 0.6, 1.1), yaw=math.atan2(d[1], d[0]),
            uv_scale=3.0)
    # escaliers vers le chemin de ronde, de part et d'autre de la porte (dans la basse-cour)
    for k in (1, 8):
        a, b = np.asarray(pts[k]), np.asarray(pts[(k + 1) % len(pts)])
        ud = (b - a) / np.linalg.norm(b - a)
        if k == 8:
            a, b, ud = b, a, -ud          # on part toujours du côté de la porte
        inw = np.array([-ud[1], ud[0]])
        if np.dot(inw, np.array([cx, cy]) - (a + b) / 2) < 0:
            inw = -inw
        _stairs_along(mb_at, a + ud * 9.0, a + ud * 35.0, Z0, Z0 + HW, inw)
    # lanternes à l'entrée
    for s in (1, -1):
        p = F.P(97.0, s * 5.0)
        inst["Lampadaire"].append((p[0], p[1], Z0, F.yaw, 1, 1, 1, 255, 255, 255))


def _stairs_along(mb_at, a, b, Z0, ztop, inward):
    """Escalier contre la face intérieure d'une courtine, parallèle à elle (de a vers b), qui monte au chemin de ronde."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = (b - a) / np.linalg.norm(b - a)
    yaw = math.atan2(u[1], u[0])
    H = ztop - Z0
    n = int(math.ceil(H / 0.19))
    L_ = float(np.linalg.norm(b - a))
    step = L_ / n
    width = 2.0
    for i in range(n):
        c = a + u * (i * step + step / 2) + inward * (TW / 2 + width / 2 - 0.05)
        top = Z0 + (i + 1) * H / n
        box(mb_at(*c), STONE, (c[0], c[1], (Z0 - 0.5 + top) / 2), (step + 0.01, width, top - Z0 + 0.5), yaw=yaw, uv_scale=3.0)
