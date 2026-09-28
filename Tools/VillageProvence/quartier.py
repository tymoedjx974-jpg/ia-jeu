"""Quartier des Ocres : un village perché sur une colline au nord-est de la coulée d'ocre.

La colline est modelée dans le terrain (bosse elliptique au contour irrégulier, sommet arrondi). Le quartier suit sa
forme comme une circulade provençale : rues en anneaux le long des courbes de niveau, montées en calade vers le sommet,
placette tout en haut, maisons mitoyennes serrées au centre et plus lâches en bordure. Style « core » (vieux village)."""
import math
import numpy as np
from scipy import ndimage
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union, nearest_points
from common import polys_of, lines_of, ombr, rasterize

STREET_NAMES = ["Rue des Ocres", "Rue du Colorado", "Rue des Sablières", "Rue de la Garance", "Traverse des Pigments",
                "Rue du Mistral", "Montée des Lavandes", "Rue des Tuiliers", "Montée du Castrum", "Rue des Ocriers",
                "Rue de la Font", "Montée des Cigales", "Rue du Four", "Rue des Potiers", "Montée de la Placette",
                "Rue du Belvédère", "Rue des Remparts"]
HILL_H = 30.0                  # hauteur de la colline au-dessus de son pied (m)
RINGS = (0.30, 0.52, 0.72, 0.90)


class Hill:
    """Colline elliptique : axes (ax, n), rayons Ra x Rb, contour ondulé rho(theta)."""

    def __init__(self, C, ax, n, Ra, Rb, rng):
        self.C, self.ax, self.n, self.Ra, self.Rb = np.asarray(C, float), np.asarray(ax, float), np.asarray(n, float), Ra, Rb
        self.ph = rng.uniform(0, 2 * math.pi, 4)

    def rho(self, th):
        # contour à éperons et vallons (pas une ellipse parfaite)
        return (1.0 + 0.09 * np.sin(2 * th + self.ph[0]) + 0.07 * np.sin(3 * th + self.ph[1])
                + 0.05 * np.sin(4 * th + self.ph[2]) + 0.03 * np.sin(7 * th + self.ph[3]))

    def d(self, x, y):
        """Distance normalisée au sommet (0 au sommet, 1 au pied) et angle."""
        dx, dy = x - self.C[0], y - self.C[1]
        u = (dx * self.ax[0] + dy * self.ax[1]) / self.Ra
        v = (dx * self.n[0] + dy * self.n[1]) / self.Rb
        th = np.arctan2(v, u)
        return np.hypot(u, v) / self.rho(th), th

    def P(self, d, th):
        r = d * self.rho(th)
        return self.C + self.ax * (self.Ra * r * math.cos(th)) + self.n * (self.Rb * r * math.sin(th))

    def ring(self, d, step=16.0, jit=0.0, rng=None):
        per = 2 * math.pi * d * (self.Ra + self.Rb) / 2
        k = max(12, int(per / step))
        ths = np.linspace(0, 2 * math.pi, k, endpoint=False)
        return [self.P(d + (rng.uniform(-jit, jit) if rng is not None else 0.0), t) for t in ths]

    def outline(self, d=1.0):
        return Polygon(self.ring(d, step=6.0)).buffer(0)


def make_hill(V, center, rng):
    """Place la colline au nord-est de la coulée d'ocre, son pied au bord de l'ocre."""
    oc = unary_union([g for g in V["cliffs"] + V["sand"] + V["rock"] if g.distance(center) < 700])
    c, ax, L, _ = ombr(oc.convex_hull)
    c, ax = np.asarray(c, float), np.asarray(ax, float)
    n = np.array([-ax[1], ax[0]])
    if n[0] + n[1] < 0:
        n = -n
    if ax[0] < 0:
        ax = -ax
    pts = np.array([p for g in polys_of(oc.buffer(1.0)) for p in g.exterior.coords]) - c
    s_, t_ = pts @ ax, pts @ n
    Ra, Rb = min(0.5 * (s_.max() - s_.min()) + 10.0, 250.0), 165.0
    sc = 0.5 * (s_.max() + s_.min()) - 30.0
    m = np.abs(s_ - sc) < Ra * 0.5
    edge = max(float(t_[m].max()) if m.any() else float(t_.max()), 0.0)
    C = c + ax * sc + n * (edge + Rb * 0.78)     # l'ocre ravine le flanc sud-ouest de la colline
    return Hill(C, ax, n, Ra, Rb, rng)


def shape_ground(ground, Xg, Yg, hill, ochre_keep, village):
    """Remplace le relief sous la colline par une bosse lisse (sommet arrondi), raccordée au terrain alentour.
    L'ocre et le vieux village ne bougent pas."""
    d, th = hill.d(Xg, Yg)
    foot = (d > 1.1) & (d < 1.4)
    base = float(np.median(ground[foot])) if foot.any() else float(ground[d < 1].mean())
    # flanc plus raide côté ocre (sud-ouest), plus doux vers le nord-est
    de = d * (1.0 - 0.14 * np.sin(th))
    dd = np.clip((de - 0.1) / 1.0, 0, 1)
    target = base + HILL_H * (0.5 + 0.5 * np.cos(math.pi * dd)) ** 1.15
    # on garde les petites ondulations du terrain d'origine, et un peu de bosselage naturel
    detail = ground - ndimage.gaussian_filter(ground, 12.0)
    lump = ndimage.gaussian_filter(np.random.default_rng(7).normal(0, 1, ground.shape).astype(np.float32), 9.0)
    lump *= 2.2 / (lump.std() + 1e-6)
    target = target + 0.45 * detail + lump * np.clip(dd * 1.6, 0.2, 1.0)
    w = np.clip((1.45 - d) / 0.5, 0, 1)
    w = w * w * (3 - 2 * w)
    keep = rasterize([ochre_keep, village.buffer(12.0)]).astype(np.float32) / 255.0
    keep = ndimage.gaussian_filter(keep, 6.0)
    w = w * (1.0 - np.clip(keep * 1.4, 0, 1))
    return (ground * (1 - w) + target * w).astype(ground.dtype), base


def new_quarter(V, roads, ochre_keep, village, slope_at, rng, hill):
    """Rues, placette et maisons du quartier perché. Renvoie (zone, bâtiments, rues, placettes, routes retirées)."""
    zone = hill.outline(1.0).difference(ochre_keep.buffer(6.0)).difference(village)
    zone = max(polys_of(zone), key=lambda g: g.area)

    # ---------------- rues : anneaux (courbes de niveau) et montées vers le sommet
    streets = []
    for j, dr in enumerate(RINGS):
        ln = hill.ring(dr, step=14.0 + 6 * dr, jit=0.012, rng=rng)
        main = j == len(RINGS) - 1
        streets.append(dict(line=LineString(ln + [ln[0]]), cls="residential" if main else "living_street",
                            surface="asphalt" if main else "stone", width=4.6 if main else (3.6 if j else 3.2),
                            prio=30 if main else 28))
    na = 6
    th0 = rng.uniform(0, 2 * math.pi)
    for k in range(na):
        th = th0 + k * 2 * math.pi / na + rng.uniform(-0.25, 0.25)
        pts = []
        for dr in np.arange(0.16, 1.04, 0.06):
            th += rng.uniform(-0.04, 0.04)                 # les montées serpentent un peu
            pts.append(hill.P(dr, th))
        streets.append(dict(line=LineString(pts), cls="living_street", surface="stone", width=3.0, prio=27))
    parts = []
    for sd in streets:
        g = sd["line"].intersection(zone.buffer(10.0))
        for l in (lines_of(g) if not g.is_empty else []):
            if l.length > 15:
                parts.append(dict(sd, line=l))
    # raccords : l'anneau extérieur rejoint le réseau (routes goudronnées et rues du vieux village)
    ex = [r for r in roads if r["surface"] in ("asphalt", "stone") and r["cls"] not in ("service", "footway", "path")
          and not zone.contains(r["line"])]
    links, ends = [], []
    for o in [p for p in parts if p["cls"] == "residential"]:
        for e in (Point(o["line"].coords[0]), Point(o["line"].coords[-1]), o["line"].interpolate(0.5, normalized=True)):
            best = min(((r["line"].distance(e), r) for r in ex), key=lambda t: t[0], default=None)
            if not best or not 2.0 < best[0] < 120:
                continue
            a, b_ = nearest_points(e, best[1]["line"])
            if all(b_.distance(q) > 40 for q in ends):
                ends.append(b_)
                links.append(dict(line=LineString([a, b_]), cls="residential", surface="asphalt", width=4.6, prio=30))
    parts += links
    names = list(STREET_NAMES)
    rng.shuffle(names)
    out_roads = [dict(cls=p["cls"], surface=p["surface"], width=p["width"], prio=p["prio"], name=names[k % len(names)],
                      line=p["line"]) for k, p in enumerate(parts)]
    # chemins et dessertes existants qui traversent la colline : remplacés par les rues du quartier
    drop = [r for r in roads if r["cls"] in ("service", "track", "path", "footway", "residential", "unclassified", "living_street")
            and r["line"].intersection(zone).length > 0.5 * r["line"].length]

    # ---------------- placette au sommet
    placette = hill.outline(0.09).intersection(zone)

    # ---------------- maisons : alignées sur les rues, mitoyennes, serrées au centre, plus lâches en bordure
    drop_ids = {id(r) for r in drop}
    all_streets = unary_union([r["line"].buffer(r["width"] / 2 + 0.5) for r in out_roads] +
                              [r["line"].buffer(r["width"] / 2 + 0.5) for r in roads
                               if id(r) not in drop_ids and r["line"].distance(zone) < 30])
    blocked = unary_union([all_streets, placette.buffer(1.5), ochre_keep])
    placed = []
    for sd in sorted(out_roads, key=lambda r: -r["prio"]):
        cs = list(sd["line"].coords)
        off = sd["width"] / 2 + 0.7
        for (x0, y0), (x1, y1) in zip(cs[:-1], cs[1:]):
            A, B = np.array([x0, y0]), np.array([x1, y1])
            seg = np.linalg.norm(B - A)
            if seg < 7:
                continue
            u_ = (B - A) / seg
            v_ = np.array([-u_[1], u_[0]])
            dmid, _ = hill.d(*(0.5 * (A + B)))
            gap_p = 0.04 + 0.22 * float(np.clip((dmid - 0.6) / 0.4, 0, 1))   # jardins et oliviers en bordure
            for side in (1, -1):
                pos = rng.uniform(0.3, 2.0)
                while pos < seg - 4:
                    w = rng.uniform(5.0, 9.5)
                    dep = rng.uniform(9.0, 14.0)
                    if rng.random() < gap_p:
                        pos += rng.uniform(3.0, 8.0)
                        continue
                    p0 = A + u_ * pos + v_ * side * off
                    p1 = A + u_ * min(pos + w, seg) + v_ * side * off
                    q = Polygon([p0, p1, p1 + v_ * side * dep, p0 + v_ * side * dep])
                    pos += w
                    if not q.is_valid or q.area < 28:
                        continue
                    if not zone.contains(q) or q.intersects(blocked) or slope_at(q.centroid.x, q.centroid.y) > 27:
                        continue
                    if any(q.buffer(-0.05).intersects(o) for o in placed if o.distance(q) < 1):
                        continue
                    placed.append(q)
    blds = [dict(poly=q, cls=None, subtype=None, name="", height=None, floors=None, id="quartier-ocres-%04d" % k)
            for k, q in enumerate(placed)]
    return zone, blds, out_roads, ([placette] if placette.area > 100 else []), drop
