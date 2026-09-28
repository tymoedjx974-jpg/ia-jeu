"""Surface de la rivière et ponts de pierre (voûtes, piles à avant-becs, parapets, tablier dallé)."""
import math
import numpy as np
from shapely.geometry import Polygon, box as sbox
from shapely.ops import unary_union
from common import polys_of
from geomlib import planar_polygon, box, nrm, WHITE

STONE = "PierreTaille"


def water(mb_at, prof, step=2):
    """Plan d'eau en ruban le long du lit (niveau décroissant vers l'aval)."""
    xy, lv, w = prof["xy"].astype(np.float64), prof["level"].astype(np.float64), prof["width"].astype(np.float64)
    d = np.gradient(xy, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    n = np.column_stack([-d[:, 1], d[:, 0]])
    hw = w / 2 + 3.0              # le plan d'eau passe sous le pied des falaises : pas de jour entre l'eau et la paroi
    Lp = xy + n * hw[:, None]
    Rp = xy - n * hw[:, None]
    z = lv + 0.12
    for i in range(0, len(xy) - step, step):
        j = i + step
        a = (Rp[i][0], Rp[i][1], z[i]); b = (Rp[j][0], Rp[j][1], z[j])
        c = (Lp[j][0], Lp[j][1], z[j]); dd = (Lp[i][0], Lp[i][1], z[i])
        mid = xy[i]
        mb_at(mid[0], mid[1]).quad("Eau", a, b, c, dd, [(a[0] / 6, a[1] / 6), (b[0] / 6, b[1] / 6), (c[0] / 6, c[1] / 6), (dd[0] / 6, dd[1] / 6)],
                                   n=(0, 0, 1.0))


def _both(mb, mat, a, b, c, d, uvs):
    mb.quad(mat, a, b, c, d, uvs)
    mb.quad(mat, d, c, b, a, uvs[::-1])


def _face(mb, mat, poly2d, A, u, v, off, outward):
    """Polygone (t, z) plaqué sur la face du pont à la distance off de l'axe ; outward = +1 (côté +v) ou -1."""
    for pg in polys_of(poly2d):
        outer = np.array(pg.exterior.coords)[:-1]
        holes = [np.array(h.coords)[:-1] for h in pg.interiors]
        org = np.array([A[0], A[1], 0.0]) + np.array([v[0], v[1], 0.0]) * outward * off
        if outward > 0:
            e1 = -np.array([u[0], u[1], 0.0])
            outer = outer * np.array([-1, 1])
            holes = [h * np.array([-1, 1]) for h in holes]
        else:
            e1 = np.array([u[0], u[1], 0.0])
        planar_polygon(mb, mat, outer, holes, org, e1, np.array([0, 0, 1.0]),
                       lambda v2, P: np.stack([v2[:, 0] / 3.0, -v2[:, 1] / 3.0], -1))


def _strip(mb, mat, ring, A, u, v, h0, h1, closed):
    """Intrados : bande qui suit le contour d'une ouverture, d'une face (h0) à l'autre (h1)."""
    pts = list(ring) + ([ring[0]] if closed else [])
    acc = 0.0
    for p, q in zip(pts[:-1], pts[1:]):
        P0, Q0 = A + u * p[0], A + u * q[0]
        ln_ = math.hypot(q[0] - p[0], q[1] - p[1])
        a = (*(P0 + v * h0), p[1]); b = (*(Q0 + v * h0), q[1]); c = (*(Q0 - v * h1), q[1]); d = (*(P0 - v * h1), p[1])
        uv = [(acc / 3, 0), ((acc + ln_) / 3, 0), ((acc + ln_) / 3, (h0 + h1) / 3), (acc / 3, (h0 + h1) / 3)]
        _both(mb, mat, a, b, c, d, uv)
        acc += ln_


def _arch(t0, t1, zbase, spring, n=24):
    """Ouverture en plein cintre : piédroits de zbase à spring, puis demi-cercle."""
    r = (t1 - t0) / 2
    m = (t0 + t1) / 2
    arc = [(m + r * math.cos(a), spring + r * math.sin(a)) for a in np.linspace(0, math.pi, n)]
    return [(t1, zbase)] + arc + [(t0, zbase)], (m, spring, r)


def bridge(mb, br, zat, water_level=None):
    """Grand viaduc de pierre à étages d'arcades (à la manière du pont du Gard) ou pont à arches plus simple.
    Murs en moellons, claveaux, corniches, avant-becs et couronnement des parapets en pierre de taille."""
    RUB, ASH = "PierreGard", "PierreGard"          # grand appareil de calcaire doré, comme le pont du Gard
    ln = br["line"]
    A = np.array(ln.coords[0], float)
    B = np.array(ln.coords[-1], float)
    L = float(np.linalg.norm(B - A))
    if L < 4:
        return []
    u = (B - A) / L
    v = np.array([-u[1], u[0]])
    yaw = math.atan2(u[1], u[0])
    road_w = br["width"] + 2.4                   # chaussée + trottoirs
    par_t, par_h = 0.55, 1.1
    Wd = road_w + 2 * par_t
    zA = br.get("z0") if br.get("z0") is not None else zat(*A)
    zB = br.get("z1") if br.get("z1") is not None else zat(*B)
    camber = 0.012 * L

    def deck(t):
        return zA + (zB - zA) * t / L + camber * 4 * (t / L) * (1 - t / L)

    ts = np.linspace(0, L, max(12, int(L / 1.0)) + 1)
    g = np.array([zat(*(A + u * t)) for t in ts])
    gat = lambda t: float(np.interp(t, ts, g))
    wl = water_level if water_level is not None else float(g.min())
    bottom = float(g.min()) - 4.0
    zd = min(zA, zB)
    H = zd - wl
    fr = [0.47, 0.36, 0.17] if H > 55 else ([0.62, 0.38] if H > 22 else [1.0])
    ztop = [wl + H * float(np.sum(fr[:k + 1])) for k in range(len(fr))]
    ntier = len(fr)
    S_target = 26.0 if H > 55 else (20.0 if H > 22 else 16.0)
    nsp = max(3, int(round(L / S_target)))
    S = L / nsp
    lamps = []
    half = [Wd / 2 + 0.6 * (ntier - 1 - k) + (0.4 if k < ntier - 1 else 0.0) for k in range(ntier)]
    for k in range(ntier):
        zlo = bottom if k == 0 else ztop[k - 1]
        last = k == ntier - 1
        hw = half[k]
        # bande du mur (le dernier étage suit le tablier et porte le parapet)
        if last:
            top = [(t, deck(t) + par_h) for t in ts]
            band = Polygon([(0, zlo)] + top + [(L, zlo)]).buffer(0)
        else:
            band = Polygon([(0, zlo), (0, ztop[k]), (L, ztop[k]), (L, zlo)])
        # ouvertures
        opens, rings = [], []
        if last and ntier > 1:
            sub = 4                                      # petite arcade : quatre arches par grande travée
            spans = [(j * S / sub, (j + 1) * S / sub) for j in range(nsp * sub)]
            pw = 1.2
        else:
            spans = [(j * S, (j + 1) * S) for j in range(nsp)]
            pw = (0.24 if k == 0 else 0.2) * S
        for (a_, b_) in spans:
            t0, t1 = a_ + pw / 2, b_ - pw / 2
            if t0 < 1.0 or t1 > L - 1.0:
                t0, t1 = max(t0, 1.5), min(t1, L - 1.5)
            if t1 - t0 < 1.5:
                continue
            r = (t1 - t0) / 2
            # au-dessus de la petite arcade, un bandeau plein (le canal couvert du pont du Gard) ; sous les corniches, 1 à 1,4 m
            ceil_ = (min(deck(t0), deck(t1)) - 2.2) if last else ztop[k] - (1.4 if k == 0 else 1.1)
            spring = ceil_ - r
            zb = bottom - 1 if k == 0 else zlo + (0.0 if last else 0.0)
            if k > 0:
                # pas d'ouverture dans la roche : l'arche doit être au-dessus du sol aux deux piédroits
                if max(gat(t0), gat(t1)) > zlo - 0.5 or spring - zlo < 0.8:
                    continue
            elif spring < max(wl + 1.0, 0.0 + bottom) or spring - r < wl - 50:
                pass
            ring, geo = _arch(t0, t1, zb, spring)
            opens.append(Polygon(ring))
            rings.append((ring, geo, k == 0))
        wall = band.difference(unary_union(opens)) if opens else band
        for side in (1, -1):
            _face(mb, RUB, wall, A, u, v, hw, side)
        for ring, (m, sp, r), open_bottom in rings:
            _strip(mb, ASH, ring if not open_bottom else ring, A, u, v, hw, hw, closed=not open_bottom)
            # claveaux : anneau de pierre de taille légèrement en saillie autour de l'arc
            rw = min(1.2, 0.12 * r + 0.35)
            th = np.linspace(0, math.pi, 25)
            outer = [(m + (r + rw) * math.cos(a), sp + (r + rw) * math.sin(a)) for a in th]
            inner = [(m + r * math.cos(a), sp + r * math.sin(a)) for a in th[::-1]]
            vou = Polygon(outer + inner).buffer(0)
            for side in (1, -1):
                _face(mb, ASH, vou, A, u, v, hw + 0.035, side)
            # imposte : bandeau saillant à la naissance de l'arc, sur les deux piédroits
            if r > 2.5:
                for tt in (m - r, m + r):
                    for side in (1, -1):
                        for dt in (-1, 1):
                            C = A + u * (tt + dt * 0.55) + v * side * (hw + 0.09)
                            box(mb, ASH, (C[0], C[1], sp - 0.2), (1.1, 0.18, 0.4), yaw=yaw, uv_scale=3.0)
        # boutisses : pierres saillantes laissées sur les piles (supports d'échafaudage), comme au pont du Gard
        if not last:
            zc_ = ztop[k]
            for j in range(1, nsp):
                tp = j * S
                if max(gat(tp - 2), gat(tp + 2)) > zc_ - 6:
                    continue
                for zb_ in np.arange(zc_ - 3.0, max(zlo, wl + 4.0), -5.5)[:6]:
                    for side in (1, -1):
                        for dt in (-0.25 * pw, 0.25 * pw):
                            C = A + u * (tp + dt) + v * side * (hw + 0.2)
                            box(mb, ASH, (C[0], C[1], zb_), (0.6, 0.4, 0.45), yaw=yaw, uv_scale=3.0)
        # corniche / retrait en haut de l'étage : bandeau de pierre de taille
        if not last:
            zc = ztop[k]
            h_in = half[k + 1]
            for t0, t1 in zip(ts[:-1:4], ts[4::4]):
                P0, P1 = A + u * t0, A + u * t1
                for side in (1, -1):
                    o_ = v * side * (hw + 0.3)
                    i_ = v * side * h_in
                    a = (*(P0 + i_), zc); b = (*(P1 + i_), zc); c = (*(P1 + o_), zc); d = (*(P0 + o_), zc)
                    _both(mb, ASH, a, b, c, d, [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, 0.3), (t0 / 3, 0.3)])
                    # tranche du bandeau
                    a2 = (*(P0 + o_), zc - 0.45); b2 = (*(P1 + o_), zc - 0.45)
                    _both(mb, ASH, a2, b2, c, d, [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, 0.15), (t0 / 3, 0.15)])
                    _both(mb, ASH, (*(P0 + v * side * hw), zc - 0.45), (*(P1 + v * side * hw), zc - 0.45), b2, a2,
                          [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, 0.1), (t0 / 3, 0.1)])
        # avant-becs des piles du premier étage, dans l'eau
        if k == 0:
            for j in range(1, nsp):
                tp = j * S
                Pp = A + u * tp
                zt = wl + min(6.0, 0.25 * H)
                w_ = pw * 0.72
                for side in (1, -1):
                    C = Pp + v * side * hw
                    box(mb, ASH, (C[0], C[1], (bottom + zt) / 2), (w_, w_, zt - bottom), yaw=yaw + math.pi / 4, uv_scale=3.0)
                    box(mb, ASH, (C[0], C[1], zt + 0.35), (w_ * 0.8, w_ * 0.8, 0.7), yaw=yaw + math.pi / 4, uv_scale=3.0)
    # bouts des étages (dans la roche le plus souvent)
    # tablier dallé, faces intérieures et couronnement des parapets
    hw_r = road_w / 2
    for t0, t1 in zip(ts[:-1], ts[1:]):
        P0, P1 = A + u * t0, A + u * t1
        z0, z1 = deck(t0), deck(t1)
        mb.quad("Dallage", (*(P0 - v * hw_r), z0), (*(P1 - v * hw_r), z1), (*(P1 + v * hw_r), z1), (*(P0 + v * hw_r), z0),
                [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, road_w / 3), (t0 / 3, road_w / 3)], n=(0, 0, 1.0))
        for side in (1, -1):
            ins = v * side * hw_r
            out = v * side * (Wd / 2 + 0.12)
            a = (*(P0 + ins), z0); b = (*(P1 + ins), z1); c = (*(P1 + ins), z1 + par_h); d = (*(P0 + ins), z0 + par_h)
            if side > 0:
                mb.quad(ASH, a, b, c, d, [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, par_h / 3), (t0 / 3, par_h / 3)])
            else:
                mb.quad(ASH, b, a, d, c, [(t1 / 3, 0), (t0 / 3, 0), (t0 / 3, par_h / 3), (t1 / 3, par_h / 3)])
            # couronnement en saillie
            mb.quad(ASH, (*(P0 + ins * 0.98), z0 + par_h + 0.12), (*(P1 + ins * 0.98), z1 + par_h + 0.12),
                    (*(P1 + out), z1 + par_h + 0.12), (*(P0 + out), z0 + par_h + 0.12),
                    [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, 0.25), (t0 / 3, 0.25)], n=(0, 0, 1.0))
            _both(mb, ASH, (*(P0 + out), z0 + par_h), (*(P1 + out), z1 + par_h), (*(P1 + out), z1 + par_h + 0.12),
                  (*(P0 + out), z0 + par_h + 0.12), [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, 0.04), (t0 / 3, 0.04)])
    # bordures de trottoir
    for side in (1, -1):
        for t0, t1 in zip(ts[:-1:3], ts[3::3]):
            P0, P1 = A + u * t0, A + u * t1
            c_ = (P0 + P1) / 2 + v * side * (br["width"] / 2 + 0.1)
            box(mb, ASH, (c_[0], c_[1], deck((t0 + t1) / 2) + 0.07), (t1 - t0, 0.25, 0.16), yaw=yaw, uv_scale=3.0)
    # piliers d'entrée avec lanterne, et réverbères le long des parapets
    for t in (0.0, L):
        P = A + u * t
        for side in (1, -1):
            c_ = P + v * side * (hw_r + par_t / 2)
            z_ = deck(t)
            box(mb, ASH, (c_[0], c_[1], z_ + 1.3), (1.1, 1.1, 2.6), yaw=yaw, uv_scale=3.0)
            box(mb, ASH, (c_[0], c_[1], z_ + 2.7), (1.35, 1.35, 0.25), yaw=yaw, uv_scale=3.0)
            lamps.append((float(c_[0]), float(c_[1]), float(z_ + 2.82), float(yaw)))
    for t in np.arange(S / 2, L - 3.0, S):
        P = A + u * t
        for side in (1, -1):
            q = P + v * side * (hw_r + par_t / 2)
            lamps.append((float(q[0]), float(q[1]), float(deck(t) + par_h + 0.12), float(yaw + (math.pi / 2) * side)))
    return lamps
