"""La rivière des Ocres : elle naît en haut du ravin d'ocre, le descend en y creusant un canyon, passe entre le vieux
village et le quartier perché, puis gagne la plaine au nord. Un grand pont de pierre à arches relie les deux villages ;
les autres routes qui la croisent ont un pont plus modeste."""
import math, heapq
import numpy as np
import shapely
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, nearest_points, substring
from common import ZONE, RES, polys_of, lines_of, grid_sample, rasterize

AMP = 1.0                      # amplitude des méandres (réduite si deux bras se rapprochent trop)
W_SRC, W_MAX = 20.0, 30.0      # largeur de l'eau en amont et en aval (m)
DEPTH = 6.0                    # profondeur d'eau au milieu du lit
DROP = 10.0                    # l'eau coule au moins 10 m sous les rives
BANK = 3.0                     # parois des gorges : 3 m de dénivelé par mètre (~72°)


def _chaikin(pts, it=3):
    P = np.asarray(pts, float)
    for _ in range(it):
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q += [0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b]
        Q.append(P[-1])
        P = np.array(Q)
    return P


def _dijkstra(cost, start, goal_mask):
    """Plus court chemin (8 voisins) sur une grille de coûts, du point start jusqu'à la première cellule de goal_mask."""
    ny, nx = cost.shape
    dist = np.full(cost.shape, np.inf)
    prev = -np.ones(cost.shape, np.int64)
    sj, si = start
    dist[sj, si] = 0.0
    h = [(0.0, sj, si)]
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while h:
        d, j, i = heapq.heappop(h)
        if d > dist[j, i]:
            continue
        if goal_mask[j, i]:
            path = [(j, i)]
            k = prev[j, i]
            while k >= 0:
                path.append(divmod(int(k), nx))
                k = prev[path[-1]]
            return path[::-1]
        for dj, di in nb:
            jj, ii = j + dj, i + di
            if 0 <= jj < ny and 0 <= ii < nx:
                nd = d + 0.5 * (cost[j, i] + cost[jj, ii]) * (1.4142 if dj and di else 1.0)
                if nd < dist[jj, ii]:
                    dist[jj, ii] = nd
                    prev[jj, ii] = j * nx + i
                    heapq.heappush(h, (nd, jj, ii))
    return None


def trace(V, ground, village, quarter_hill, blds, rng):
    """Tracé de la rivière, d'un bord à l'autre de la carte : du sud jusqu'au ravin d'ocre, qu'elle entaille en gorges,
    entre les deux villages, puis vers la plaine au nord. Les deux villages sont sur des rives opposées."""
    center = Point(-10.0, 0.0)
    ochre = [g for g in V["sand"] + V["rock"] if g.distance(center) < 700] + [l.buffer(10) for l in V["cliffs"] if l.distance(center) < 700]
    oc = unary_union(ochre)
    # axe du ravin : centres des taches d'ocre, triés du haut (source) vers le bas
    pts = []
    for g in polys_of(oc):
        c = g.centroid
        pts.append((c.x, c.y, float(grid_sample(ground, [c.x], [c.y])[0])))
    pts.sort(key=lambda p: -p[2])
    src = np.array(pts[0][:2])
    # points du ravin ordonnés par distance à la source
    rav = sorted([np.array(p[:2]) for p in pts], key=lambda p: np.linalg.norm(p - src))
    hill_out = quarter_hill.outline(1.0)
    a, b = nearest_points(village, hill_out.difference(oc.buffer(40)))
    gap = np.array([(a.x + b.x) / 2, (a.y + b.y) / 2])
    # de la sortie du ravin vers la plaine au nord : chemin de moindre coût (fonds de vallon, loin des maisons)
    step = 8.0
    nx = int((ZONE["xmax"] - ZONE["xmin"]) / step)
    ny = int((ZONE["ymax"] - ZONE["ymin"]) / step)
    xs = ZONE["xmin"] + (np.arange(nx) + 0.5) * step
    ys = ZONE["ymin"] + (np.arange(ny) + 0.5) * step
    X, Y = np.meshgrid(xs, ys)
    Z = grid_sample(ground, X.ravel(), Y.ravel()).reshape(X.shape)
    zg = float(grid_sample(ground, [gap[0]], [gap[1]])[0])
    cost = 1.0 + 0.08 * np.clip(Z - Z.min(), 0, None) + 4.0 * np.clip(Z - zg, 0, None)
    near_b = unary_union([bb["poly"].buffer(45.0) for bb in blds if bb["poly"].distance(Point(*gap)) < 1500])
    nb_mask = shapely.contains_xy(near_b, X, Y)
    cost[nb_mask] += 60.0
    cost[shapely.contains_xy(hill_out.buffer(20), X, Y)] += 200.0
    # un peu de « bruit » géologique : le cours d'eau hésite, au lieu de filer en ligne droite
    noise = ndimage.gaussian_filter(np.random.default_rng(11).normal(0, 1, cost.shape), 6.0)
    cost *= 1.0 + 1.6 * np.clip(noise / (noise.std() + 1e-9), -1.5, 1.5) ** 2
    goal = np.zeros_like(cost, bool)
    goal[-1, :] = True                          # bord nord
    sj, si = int((gap[1] - ZONE["ymin"]) / step), int((gap[0] - ZONE["xmin"]) / step)
    path = _dijkstra(cost, (sj, si), goal)
    down = [np.array([xs[i], ys[j]]) for j, i in path[1:]]
    # amont : du haut du ravin d'ocre jusqu'au bord sud (ou est) de la carte, par les terrains les plus bas
    cu = 1.0 + 0.1 * np.clip(Z - Z.min(), 0, None)
    cu[nb_mask] += 80.0
    cu[shapely.contains_xy(hill_out.buffer(40), X, Y)] += 400.0
    cu[shapely.contains_xy(village.buffer(60), X, Y)] += 400.0
    cu *= 1.0 + 1.6 * np.clip(noise / (noise.std() + 1e-9), -1.5, 1.5) ** 2
    gu = np.zeros_like(cu, bool)
    gu[0, :] = True                              # bord sud
    gu[: int((src[1] - ZONE["ymin"]) / step), -1] = True   # bord est, au sud du ravin
    sj2, si2 = int((src[1] - ZONE["ymin"]) / step), int((src[0] - ZONE["xmin"]) / step)
    up = [np.array([xs[i], ys[j]]) for j, i in _dijkstra(cu, (sj2, si2), gu)[1:]][::-1]
    ul = LineString(up + [src]).simplify(12.0)
    uu = []
    ph2 = rng.uniform(0, 2 * math.pi)
    for t in np.arange(0.0, ul.length, 20.0):
        p0 = np.array(ul.interpolate(t).coords[0])
        p1 = np.array(ul.interpolate(min(ul.length, t + 5.0)).coords[0])
        tg = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-9)
        amp = AMP * 45.0 * np.clip((ul.length - t - 250.0) / 600.0, 0, 1)
        off = amp * math.sin(2 * math.pi * t / 310.0 + ph2)
        uu.append(p0 + np.array([-tg[1], tg[0]]) * off)
    # en aval du passage : méandres de plus en plus amples à mesure que la vallée s'ouvre
    dl = LineString([gap] + down).simplify(12.0)
    dd = []
    ph = rng.uniform(0, 2 * math.pi)
    for t in np.arange(0.0, dl.length, 20.0):
        p0 = np.array(dl.interpolate(t).coords[0])
        p1 = np.array(dl.interpolate(min(dl.length, t + 5.0)).coords[0])
        tg = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-9)
        amp = AMP * 55.0 * np.clip((t - 250.0) / 600.0, 0, 1)
        off = amp * math.sin(2 * math.pi * t / 330.0 + ph) + 0.35 * amp * math.sin(2 * math.pi * t / 131.0 + 2 * ph)
        dd.append(p0 + np.array([-tg[1], tg[0]]) * off)
    # points du ravin situés avant le passage seulement (sinon le lit ferait un aller-retour)
    dg = np.linalg.norm(gap - src)
    rav_ok = [p for p in rav[1:] if np.linalg.norm(p - src) < dg - 40.0]
    ctrl = [uu[0]] + uu[2:-2:2] + [src] + rav_ok + dd[::2] + [dd[-1]]
    P = _chaikin(ctrl, 4)
    # virages adoucis : rayon de courbure réaliste pour une rivière de 20 à 30 m (pas de coude en épingle)
    l0 = LineString(P)
    ss = np.arange(0.0, l0.length, 8.0)
    Q = np.array([l0.interpolate(t).coords[0] for t in ss])
    for _ in range(3):
        Qs = ndimage.gaussian_filter1d(Q, 5.0, axis=0, mode="nearest")
        Qs[:3], Qs[-3:] = Q[:3], Q[-3:]
        Q = Qs
    # les deux bouts sortent franchement de la carte (pas de gorge en cul-de-sac au bord)
    e0 = Q[0] + (Q[0] - Q[6]) / np.linalg.norm(Q[0] - Q[6]) * 90.0
    e1 = Q[-1] + (Q[-1] - Q[-7]) / np.linalg.norm(Q[-1] - Q[-7]) * 90.0
    line = LineString(np.vstack([e0, Q, e1])).simplify(0.8)
    return line, dict(src=src, gap=gap)


def _too_close(line, gap_m=190.0, arc_m=500.0):
    """Vrai si la rivière repasse près d'elle-même (méandre trop serré : deux bras à des niveaux différents)."""
    ss = np.arange(0.0, line.length, 10.0)
    P = np.array([line.interpolate(t).coords[0] for t in ss])
    D = np.hypot(P[:, None, 0] - P[None, :, 0], P[:, None, 1] - P[None, :, 1])
    arc = np.abs(ss[:, None] - ss[None, :])
    hairpin = (D < gap_m) & (arc > 1.8 * D + 100.0)      # épingle à cheveux : on fait un long détour pour revenir tout près
    return bool(hairpin.any())


def trace_ok(*args, **kw):
    """Tracé dont les méandres restent assez amples pour que deux bras ne se touchent pas."""
    global AMP
    for AMP in (1.0, 0.6, 0.35, 0.15, 0.0):
        rng_state = args[-1].bit_generator.state
        line, info = trace(*args, **kw)
        if not _too_close(line):
            break
        args[-1].bit_generator.state = rng_state
    info["amp"] = AMP
    return line, info


def carve(ground, Xg, Yg, line, rng):
    """Creuse le lit et les berges ; renvoie (sol, profil de la rivière)."""
    L = line.length
    ss = np.arange(0.0, L, 4.0)
    cen = np.array([line.interpolate(s).coords[0] for s in ss])
    # niveau de l'eau : sous le sol le long du tracé, toujours descendant vers l'aval
    gz = grid_sample(ground, cen[:, 0], cen[:, 1])
    gz = ndimage.minimum_filter1d(gz, 5)
    lvl = np.minimum.accumulate(gz - DROP)
    lvl = lvl - np.linspace(0, 0.002 * L, len(lvl))          # pente minimale : l'eau coule
    # rapides adoucis : pente lissée sur ~100 m (l'eau reste sous les rives et descend toujours)
    lvl = np.minimum.accumulate(ndimage.uniform_filter1d(lvl, 25, mode="nearest"))
    width = W_SRC + (W_MAX - W_SRC) * np.clip(ss / L, 0, 1) + 3.0 * np.sin(ss / 97.0 + rng.uniform(0, 6))
    prof = dict(s=ss, level=lvl.astype(np.float32), width=width.astype(np.float32), xy=cen.astype(np.float32))
    # cellules proches du tracé
    corridor = line.buffer(W_MAX / 2 + 180.0)          # assez large pour les gorges les plus profondes
    x0, y0, x1, y1 = corridor.bounds
    jx = (Xg[0] >= x0) & (Xg[0] <= x1)
    jy = (Yg[:, 0] >= y0) & (Yg[:, 0] <= y1)
    sub = np.ix_(jy, jx)
    Xs, Ys = Xg[sub], Yg[sub]
    pts = shapely.points(Xs.ravel(), Ys.ravel())
    r = shapely.distance(line, pts).reshape(Xs.shape)
    s_at = shapely.line_locate_point(line, pts).reshape(Xs.shape)
    lv = np.interp(s_at, ss, lvl)
    hw = np.interp(s_at, ss, width) / 2
    bed = lv - DEPTH * np.clip(1 - (r / hw) ** 6, 0, 1) - 0.3
    # parois des gorges : falaises irrégulières (ressauts, surplombs adoucis), un peu moins raides en haut
    rough = ndimage.gaussian_filter(np.random.default_rng(5).normal(0, 1, r.shape), 2.0)
    rough *= 1.2 / (rough.std() + 1e-6)
    rr = np.clip(r - hw + rough, 0, None)
    # parois en gradins : ressauts presque verticaux (~8 m) séparés par des vires de 1 à 2,5 m où s'accroche la végétation
    STEP = 8.0
    lw = 1.5 + 0.8 * np.clip(ndimage.gaussian_filter(np.random.default_rng(6).normal(0, 1, r.shape), 4.0) * 4.0, -1, 1)
    rise_w = STEP / 5.0
    P_ = rise_w + lw
    q = rr / P_
    k = np.floor(q)
    fr = (q - k) * P_
    zz = STEP * k + np.where(fr < lw, 0.25 * fr, 0.25 * lw + (fr - lw) * (STEP - 0.25 * lw) / rise_w)
    bank = lv + 0.35 + zz
    new = np.where(r < hw, bed, bank)
    g = ground[sub]
    carved = np.minimum(g, new)
    ground = ground.copy()
    ground[sub] = carved
    # bord des gorges (distance au milieu du lit, de chaque côté) : là où le terrain n'est plus entaillé
    dig = np.zeros_like(ground)
    dig[sub] = g - carved
    d = np.gradient(cen, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    n = np.column_stack([-d[:, 1], d[:, 0]])
    offs = np.arange(0.0, 195.0, 1.5)
    for key, sg in (("rim_l", 1.0), ("rim_r", -1.0)):
        rim = np.zeros(len(cen))
        for i in range(len(cen)):
            P = cen[i] + n[i] * sg * offs[:, None]
            dv = grid_sample(dig, P[:, 0], P[:, 1])
            k = np.nonzero((offs > width[i] / 2) & (dv < 0.3))[0]
            rim[i] = offs[k[0]] if len(k) else offs[-1]
        prof[key] = ndimage.maximum_filter1d(rim, 3).astype(np.float32)
    return ground, prof


def river_rim(prof, extra=0.0):
    """Emprise des gorges (jusqu'au bord des falaises), élargie de extra."""
    xy = prof["xy"]
    d = np.gradient(xy, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    n = np.column_stack([-d[:, 1], d[:, 0]])
    left = xy + n * (prof["rim_l"][:, None] + extra)
    right = xy - n * (prof["rim_r"][:, None] + extra)
    return Polygon(np.vstack([left, right[::-1]])).buffer(0).buffer(2.0).buffer(-2.0)


def river_polygon(prof, extra=0.0):
    xy, w = prof["xy"], prof["width"]
    d = np.gradient(xy, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    n = np.column_stack([-d[:, 1], d[:, 0]])
    left = xy + n * (w[:, None] / 2 + extra)
    right = xy - n * (w[:, None] / 2 + extra)
    return Polygon(np.vstack([left, right[::-1]])).buffer(0)


def bridges(roads, prof, ground_before, ground_after, grand_line=None):
    """Coupe les routes qui franchissent la rivière et renvoie les ponts (tronçons au-dessus du lit et des berges)."""
    dig = ground_before - ground_after
    wet = river_polygon(prof, 1.0)
    out_roads, out_br = [], []
    for r in roads:
        ln = r["line"]
        if not ln.intersects(wet):
            out_roads.append(r)
            continue
        # tronçon creusé autour de chaque franchissement
        L = ln.length
        ts = np.arange(0.0, L + 0.01, 1.0)
        P = np.array([ln.interpolate(t).coords[0] for t in ts])
        dd = grid_sample(dig, P[:, 0], P[:, 1])
        low = dd > 0.4
        low |= shapely.contains_xy(wet, P[:, 0], P[:, 1])
        k = 0
        cut = []
        while k < len(ts):
            if low[k]:
                k0 = k
                while k < len(ts) and low[k]:
                    k += 1
                a_, b_ = max(0.0, ts[k0] - 3.0), min(L, ts[k - 1] + 3.0)
                if shapely.intersects(substring(ln, a_, b_), wet):
                    cut.append((a_, b_))
            k += 1
        if not cut:
            out_roads.append(r)
            continue
        t_prev = 0.0
        for a_, b_ in cut:
            if a_ - t_prev > 2.0:
                out_roads.append(dict(r, line=substring(ln, t_prev, a_)))
            span = substring(ln, a_, b_)
            grand = grand_line is not None and span.distance(grand_line) < 1.0 and r.get("grand")
            # vrai franchissement (assez perpendiculaire, pas trop long) -> pont ; sinon la route longe l'eau : on la coupe
            m = span.interpolate(0.5, normalized=True)
            k_ = int(np.argmin(np.hypot(prof["xy"][:, 0] - m.x, prof["xy"][:, 1] - m.y)))
            k2 = min(k_ + 1, len(prof["xy"]) - 1)
            tr = prof["xy"][k2] - prof["xy"][max(k_ - 1, 0)]
            sp = np.array(span.coords[-1]) - np.array(span.coords[0])
            cosang = abs(float(tr @ sp)) / (np.linalg.norm(tr) * np.linalg.norm(sp) + 1e-9)
            straight = Point(span.coords[0]).distance(Point(span.coords[-1])) > 0.9 * span.length
            if grand or (cosang < 0.6 and straight and span.length < 110 and r["cls"] not in ("path", "footway", "track")):
                out_br.append(dict(line=span, width=r["width"], name=r.get("name") or "", grand=bool(grand), cls=r["cls"]))
            t_prev = b_
        if L - t_prev > 2.0:
            out_roads.append(dict(r, line=substring(ln, t_prev, L)))
    return out_roads, out_br


def grand_bridge(roads, blds_old, q_roads, ground, prof, gap, summit, width=6.5):
    """Grand pont presque horizontal : il part d'une rue du vieux village et se pose à flanc de colline, à la même
    altitude, puis une Grand-Rue monte jusqu'au premier anneau du quartier. Renvoie (pont, routes d'accès)."""
    wet = river_rim(prof, 0.0)
    zg = lambda x, y: float(grid_sample(ground, [x], [y])[0])
    old_rd = [r["line"] for r in roads if r["surface"] in ("asphalt", "stone") and r["cls"] not in ("footway", "path")]
    old_rd = [l for l in old_rd if l.distance(Point(*gap)) < 260]
    bl = unary_union([b["poly"].buffer(1.5) for b in blds_old if b["poly"].distance(Point(*gap)) < 400])
    rings = unary_union([r["line"] for r in q_roads if len(r["line"].coords) > 2])
    C = np.asarray(summit, float)
    best = None
    for l in old_rd:
        for t in np.arange(0.0, l.length, 3.0):
            a = np.array(l.interpolate(t).coords[0])
            za = zg(*a)
            d = C - a
            D = float(np.linalg.norm(d))
            if D < 30:
                continue
            u = d / D
            ts = np.arange(0.0, min(D, 320.0), 1.0)
            P = a + u[None] * ts[:, None]
            inw = shapely.contains_xy(wet, P[:, 0], P[:, 1])
            if not inw.any():
                continue
            k_in = int(np.argmax(inw))
            k_out = k_in + int(np.argmax(~inw[k_in:])) if (~inw[k_in:]).any() else len(ts) - 1
            gz = grid_sample(ground, P[:, 0], P[:, 1])
            land = np.nonzero((np.arange(len(ts)) > k_out) & (gz >= za - 0.3))[0]
            if not len(land):
                continue
            kL = int(land[0])
            dep = np.nonzero(gz[:k_in] >= za - 1.0)[0]
            k0 = int(dep[-1]) if len(dep) else 0
            span = ts[kL] - ts[k0]
            if not 50.0 <= span <= 240.0:
                continue
            seg = LineString([a, P[kL]])
            if seg.intersects(bl.difference(Point(*a).buffer(3))):
                continue
            # la Grand-Rue continue vers le sommet jusqu'au premier anneau
            up = LineString([P[kL], C])
            hit = up.intersection(rings)
            hp = [Point(hit)] if hit.geom_type == "Point" else [g for g in getattr(hit, "geoms", []) if g.geom_type == "Point"]
            if not hp:
                continue
            e = min(hp, key=lambda q: q.distance(Point(*P[kL])))
            # un vrai grand pont : haut au-dessus de l'eau, pas trop long, départ proche de la rue
            kk = int(np.argmin(np.hypot(prof["xy"][:, 0] - P[k_in][0], prof["xy"][:, 1] - P[k_in][1])))
            haut = za - float(prof["level"][kk])
            sc = -2.0 * haut + 0.25 * span + 0.3 * ts[k0] + 0.1 * e.distance(Point(*P[kL]))
            if best is None or sc < best[0]:
                best = (sc, a, P[k0], P[kL], np.array(e.coords[0]), za)
    if best is None:
        return None, []
    _, a, p0, pL, pe, za = best
    br = dict(line=LineString([p0, pL]), width=width, name="Pont des Ocres", grand=True, cls="secondary", z0=za, z1=za)
    acc = []
    if np.linalg.norm(p0 - a) > 1.0:
        acc.append(dict(cls="secondary", surface="asphalt", width=width, prio=45, name="Pont des Ocres", line=LineString([a, p0])))
    acc.append(dict(cls="residential", surface="stone", width=width - 1.5, prio=40, name="Grand-Rue", line=LineString([pL, pe])))
    return br, acc


def ramps(ground, Xg, Yg, br, roads, prof, slope=0.08):
    """Tablier presque plat : la route est entaillée dans la berge haute ou posée sur un remblai du côté bas."""
    ln = br["line"]
    A, B = np.array(ln.coords[0]), np.array(ln.coords[-1])
    zA = float(grid_sample(ground, [A[0]], [A[1]])[0])
    zB = float(grid_sample(ground, [B[0]], [B[1]])[0])
    m = ln.interpolate(0.5, normalized=True)
    k = int(np.argmin(np.hypot(prof["xy"][:, 0] - m.x, prof["xy"][:, 1] - m.y)))
    deck = max(min(zA, zB), float(prof["level"][k]) + 3.0)
    if abs(zA - zB) / max(ln.length, 1) < 0.06:
        deck = None
    br["z0"], br["z1"] = (zA, zB) if deck is None else (deck, deck)
    if deck is None:
        return ground
    for E, zE in ((A, zA), (B, zB)):
        if abs(zE - deck) < 0.3:
            continue
        # tronçon de route qui part de cette culée
        cand = [r["line"] for r in roads if Point(r["line"].coords[0]).distance(Point(*E)) < 0.8 or Point(r["line"].coords[-1]).distance(Point(*E)) < 0.8]
        if cand:
            rl = cand[0]
            if Point(rl.coords[-1]).distance(Point(*E)) < 0.8:
                rl = LineString(list(rl.coords)[::-1])
        else:
            d = (E - (B if E is A else A))
            d /= np.linalg.norm(d)
            rl = LineString([E, E + d * 150])
        run = min(rl.length, abs(zE - deck) / slope + 10.0)
        seg = substring(rl, 0, run)
        corr = seg.buffer(br["width"] / 2 + 2.0 + abs(zE - deck))
        x0, y0, x1, y1 = corr.bounds
        jx = (Xg[0] >= x0) & (Xg[0] <= x1)
        jy = (Yg[:, 0] >= y0) & (Yg[:, 0] <= y1)
        sub = np.ix_(jy, jx)
        pts = shapely.points(Xg[sub].ravel(), Yg[sub].ravel())
        r = shapely.distance(seg, pts).reshape(Xg[sub].shape)
        t = shapely.line_locate_point(seg, pts).reshape(Xg[sub].shape)
        hw = br["width"] / 2 + 1.0
        g = ground[sub]
        tgt = deck + np.sign(zE - deck) * slope * t
        side = np.clip(r - hw, 0, None)
        if zE > deck:          # déblai : la route descend dans la berge, talus à 45°
            lim = tgt + side
            new = np.where(t < run - 0.5, np.minimum(g, lim), g)
        else:                  # remblai
            lim = tgt - side
            new = np.where(t < run - 0.5, np.maximum(g, lim), g)
        ground = ground.copy()
        ground[sub] = new
    return ground


def cut_roads(roads, rim):
    """Les routes s'arrêtent au bord des gorges (on ne garde que les tronçons hors des gorges)."""
    zone = rim.buffer(2.0)
    out = []
    for r in roads:
        ln = r["line"]
        if not ln.intersects(zone):
            out.append(r)
            continue
        for part in lines_of(ln.difference(zone)):
            if part.length > 4.0:
                out.append(dict(r, line=part))
    return out
