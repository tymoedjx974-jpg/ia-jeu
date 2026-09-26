"""Étape 3 : chaussées drapées sur le terrain (enrobé, calades, dallages des places, graviers), marquages, escaliers, murs."""
import sys, pickle, math, time, collections
sys.path.insert(0, ".")
from common import *
from geomlib import MB, box, tube, nrm, WHITE
from materials import TILE
import triangle as trg

T0 = time.time()
G = np.load("terrain.npz")["ground"]
V = pickle.load(open("vec.pkl", "rb"))
CHUNK = 128.0


def terrain_normals(x, y):
    e = 1.0
    zx = grid_sample(G, x + e, y) - grid_sample(G, x - e, y)
    zy = grid_sample(G, x, y + e) - grid_sample(G, x, y - e)
    n = np.column_stack([-zx / (2 * e), -zy / (2 * e), np.ones_like(zx)])
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def mesh_polygon(mb_of, mat, poly, zoff, maxarea=2.5, col=WHITE, skirt=0.0):
    tile = TILE.get(mat, 2.0)
    n_tris = 0
    for pg in polys_of(poly):
        if pg.area < 0.4:
            continue
        pg = shapely.simplify(pg, 0.06)
        if pg.is_empty or pg.geom_type != "Polygon":
            continue
        verts, segs, holes = [], [], []

        def ring(coords):
            cs = np.asarray(coords)[:-1]
            n0 = len(verts)
            verts.extend(cs.tolist())
            k = len(cs)
            segs.extend([[n0 + i, n0 + (i + 1) % k] for i in range(k)])

        ring(pg.exterior.coords)
        for h in pg.interiors:
            if Polygon(h).area < 0.05:
                continue
            ring(h.coords)
            hp = Polygon(h).representative_point()
            holes.append([hp.x, hp.y])
        A = dict(vertices=np.array(verts, float), segments=np.array(segs, int))
        if holes:
            A["holes"] = np.array(holes)
        try:
            B = trg.triangulate(A, f"pq20a{maxarea}")
        except Exception:
            continue
        if "triangles" not in B or len(B["triangles"]) == 0:
            continue
        v = B["vertices"]
        t = B["triangles"].astype(np.int64)
        a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        area = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        t[area < 0] = t[area < 0][:, [0, 2, 1]]
        z = grid_sample(G, v[:, 0], v[:, 1], order=1) + zoff
        P = np.column_stack([v, z])
        N = terrain_normals(v[:, 0], v[:, 1])
        UV = np.column_stack([v[:, 0] / tile, -v[:, 1] / tile])
        # découpage par tuile pour l'export (centroïde des triangles)
        cx = (a[:, 0] + b[:, 0] + c[:, 0]) / 3
        cy = (a[:, 1] + b[:, 1] + c[:, 1]) / 3
        keys = np.floor(cx / CHUNK).astype(int) * 100000 + np.floor(cy / CHUNK).astype(int)
        for k in np.unique(keys):
            m = keys == k
            tt = t[m]
            used = np.unique(tt)
            remap = -np.ones(len(v), np.int64)
            remap[used] = np.arange(len(used))
            kx = int(np.floor(cx[m][0] / CHUNK))
            ky = int(np.floor(cy[m][0] / CHUNK))
            mb_of((kx, ky)).add(mat, P[used], N[used], UV[used], [col], remap[tt])
        n_tris += len(t)
        if skirt > 0:
            for ringc in [pg.exterior.coords] + [h.coords for h in pg.interiors]:
                cs = np.asarray(ringc)
                for i in range(len(cs) - 1):
                    p0, p1 = cs[i], cs[i + 1]
                    L = np.linalg.norm(p1 - p0)
                    if L < 0.05:
                        continue
                    z0 = float(grid_sample(G, [p0[0]], [p0[1]])[0]) + zoff
                    z1 = float(grid_sample(G, [p1[0]], [p1[1]])[0]) + zoff
                    kx, ky = int(np.floor((p0[0] + p1[0]) / 2 / CHUNK)), int(np.floor((p0[1] + p1[1]) / 2 / CHUNK))
                    mb_of((kx, ky)).quad(mat, (p1[0], p1[1], z1 - skirt), (p0[0], p0[1], z0 - skirt), (p0[0], p0[1], z0), (p1[0], p1[1], z1),
                                         [(L / tile, 0.1), (0, 0.1), (0, 0), (L / tile, 0)], col)
    return n_tris


def along(line, step):
    n = max(2, int(line.length / step) + 1)
    s = np.linspace(0, line.length, n)
    pts = shapely.line_interpolate_point(line, s)
    return s, np.column_stack([shapely.get_x(pts), shapely.get_y(pts)])


def markings(mb_of, road):
    """Lignes blanches : axe discontinu (3 m / 10 m) et rives continues sur les routes départementales."""
    ln = road["line"]
    if ln.length < 20:
        return
    w = road["width"]
    s, xy = along(ln, 1.0)
    d = np.gradient(xy, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm2 = np.column_stack([-d[:, 1], d[:, 0]])
    z = grid_sample(G, xy[:, 0], xy[:, 1]) + 0.075
    lw = 0.12

    def strip(i0, i1, off):
        for i in range(i0, i1):
            a = xy[i] + nrm2[i] * off
            b = xy[i + 1] + nrm2[i + 1] * off
            na, nb = nrm2[i] * lw / 2, nrm2[i + 1] * lw / 2
            kx, ky = int(np.floor(a[0] / CHUNK)), int(np.floor(a[1] / CHUNK))
            mb_of((kx, ky)).quad("Marquage", (a[0] - na[0], a[1] - na[1], z[i]), (b[0] - nb[0], b[1] - nb[1], z[i + 1]),
                                 (b[0] + nb[0], b[1] + nb[1], z[i + 1]), (a[0] + na[0], a[1] + na[1], z[i]), [(0, 0), (1, 0), (1, 1), (0, 1)], WHITE, n=(0, 0, 1))

    n = len(s)
    k = 0
    while k < n - 4:
        strip(k, min(n - 1, k + 3), 0.0)
        k += 13
    if road["cls"] in ("primary", "secondary"):
        strip(0, n - 1, w / 2 - 0.3)
        strip(0, n - 1, -(w / 2 - 0.3))


def steps(mb_of, road):
    ln = road["line"]
    w = road["width"]
    s, xy = along(ln, 0.34)
    z = grid_sample(G, xy[:, 0], xy[:, 1])
    if len(s) < 3:
        return
    for i in range(len(s) - 1):
        a, b = xy[i], xy[i + 1]
        c = (a + b) / 2
        d = b - a
        yaw = math.atan2(d[1], d[0])
        top = max(z[i], z[i + 1]) + 0.08
        bottom = min(z[i], z[i + 1]) - 0.5
        kx, ky = int(np.floor(c[0] / CHUNK)), int(np.floor(c[1] / CHUNK))
        box(mb_of((kx, ky)), "Dallage", (c[0], c[1], (top + bottom) / 2), (np.linalg.norm(d) + 0.03, w, top - bottom), yaw=yaw, uv_scale=3.0)


def stone_wall(mb_of, line, height, thick=0.5, mat="PierreMoellons", cap=True, base_follow=True):
    """Muret de pierre sèche le long d'une ligne (suit le terrain)."""
    if line.length < 1.0:
        return
    s, xy = along(line, 2.0)
    d = np.gradient(xy, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nn = np.column_stack([-d[:, 1], d[:, 0]]) * thick / 2
    g = grid_sample(G, xy[:, 0], xy[:, 1])
    tile = TILE[mat]
    for i in range(len(s) - 1):
        kx, ky = int(np.floor(xy[i][0] / CHUNK)), int(np.floor(xy[i][1] / CHUNK))
        mb = mb_of((kx, ky))
        for sgn in (1, -1):
            a = xy[i] + nn[i] * sgn
            b = xy[i + 1] + nn[i + 1] * sgn
            za0, zb0 = g[i] - 0.4, g[i + 1] - 0.4
            za1, zb1 = g[i] + height, g[i + 1] + height
            u0, u1 = s[i] / tile, s[i + 1] / tile
            if sgn > 0:
                mb.quad(mat, (b[0], b[1], zb0), (a[0], a[1], za0), (a[0], a[1], za1), (b[0], b[1], zb1), [(u1, 0.2), (u0, 0.2), (u0, -height / tile), (u1, -height / tile)])
            else:
                mb.quad(mat, (a[0], a[1], za0), (b[0], b[1], zb0), (b[0], b[1], zb1), (a[0], a[1], za1), [(u0, 0.2), (u1, 0.2), (u1, -height / tile), (u0, -height / tile)])
        if cap:
            a1 = xy[i] + nn[i]
            a2 = xy[i] - nn[i]
            b1 = xy[i + 1] + nn[i + 1]
            b2 = xy[i + 1] - nn[i + 1]
            mb.quad(mat, (a2[0], a2[1], g[i] + height), (b2[0], b2[1], g[i + 1] + height), (b1[0], b1[1], g[i + 1] + height), (a1[0], a1[1], g[i] + height),
                    [(0, 0), (1, 0), (1, 0.15), (0, 0.15)])


def terrace_wall(mb_of, run, thick=0.5):
    """Mur de soutènement en pierre le long du bord d'une place (parapet côté vide)."""
    pts = np.array([(x, y) for x, y, _, _ in run])
    zin = np.array([z for _, _, z, _ in run])
    zout = np.array([z for _, _, _, z in run])
    top = np.maximum(zin + 0.85 * (zin > zout), zout + 0.1)
    # couronnement régulier : lissé le long du mur, jamais sous le sol de la place
    k = np.exp(-0.5 * (np.arange(-6, 7) / 2.5) ** 2)
    pad = np.pad(top, 6, mode="edge")
    top = np.maximum(np.convolve(pad, k / k.sum(), mode="valid"), zin + 0.3)
    bot = np.minimum(zin, zout) - 0.6
    tile = TILE["PierreMoellons"]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        d = b - a
        L = np.linalg.norm(d)
        if L < 0.05:
            continue
        nn = np.array([-d[1], d[0]]) / L * thick / 2
        kx, ky = int(np.floor(a[0] / CHUNK)), int(np.floor(a[1] / CHUNK))
        mb = mb_of((kx, ky))
        for sgn in (1, -1):
            p0, p1 = a + nn * sgn, b + nn * sgn
            if sgn > 0:
                mb.quad("PierreMoellons", (p1[0], p1[1], bot[i + 1]), (p0[0], p0[1], bot[i]), (p0[0], p0[1], top[i]), (p1[0], p1[1], top[i + 1]), [(L / tile, 0), (0, 0), (0, -1), (L / tile, -1)])
            else:
                mb.quad("PierreMoellons", (p0[0], p0[1], bot[i]), (p1[0], p1[1], bot[i + 1]), (p1[0], p1[1], top[i + 1]), (p0[0], p0[1], top[i]), [(0, 0), (L / tile, 0), (L / tile, -1), (0, -1)])
        c0, c1, c2, c3 = a - nn * 1.1, b - nn * 1.1, b + nn * 1.1, a + nn * 1.1
        mb.quad("PierreTaille", (c0[0], c0[1], top[i]), (c1[0], c1[1], top[i + 1]), (c2[0], c2[1], top[i + 1]), (c3[0], c3[1], top[i]), [(0, 0), (L / 3, 0), (L / 3, 0.2), (0, 0.2)])
        # extrémités fermées
        for j, sd in ((i, -1), (i + 1, 1)):
            if (sd < 0 and j != 0) or (sd > 0 and j != len(pts) - 1):
                continue
            e = pts[j]
            l, r = e - nn * sd, e + nn * sd
            mb.quad("PierreMoellons", (l[0], l[1], bot[j]), (r[0], r[1], bot[j]), (r[0], r[1], top[j]), (l[0], l[1], top[j]), [(0, 0), (thick / tile, 0), (thick / tile, -1), (0, -1)])


def build():
    chunks = collections.defaultdict(MB)
    mb_of = lambda k: chunks[k]
    bl_union = unary_union([b["poly"] for b in V["buildings"]]).buffer(0.05)
    polys = collections.defaultdict(list)
    core_zone = V["core"].buffer(12)
    for r in V["roads"]:
        s = r["surface"]
        if r["cls"] in ("residential", "unclassified", "service", "living_street", "pedestrian", "footway", "path") and s != "steps":
            inside = r["line"].intersection(core_zone).length / max(r["line"].length, 1e-6)
            if inside > 0.5:
                s = "stone"
                r["width"] = max(r["width"], 2.2) if r["cls"] in ("footway", "path") else r["width"]
        if s in ("dirt", "path", "steps"):
            continue
        g = r["line"].buffer(r["width"] / 2, quad_segs=4)
        polys[{"asphalt": "Asphalte", "stone": "Calade", "gravel": "Gravier"}[s]].append(g)
    A = unary_union(polys["Asphalte"] + [p for p in V["parking"] if p.area > 150])
    Pl = unary_union(V["plaza"]).difference(A)
    Cal = unary_union(polys["Calade"]).difference(A).difference(Pl)
    Gr = unary_union(polys["Gravier"]).difference(A).difference(Cal).difference(Pl)
    zone = ZBOX.buffer(-2)
    out = {}
    for mat, geom, zoff, skirt in (("Asphalte", A, 0.05, 0.25), ("Calade", Cal, 0.07, 0.2), ("Dallage", Pl, 0.07, 0.2), ("Gravier", Gr, 0.04, 0.1)):
        geom = geom.difference(bl_union).intersection(zone)
        n = mesh_polygon(mb_of, mat, geom, zoff, maxarea=3.0 if mat == "Asphalte" else 2.0, skirt=skirt)
        out[mat] = n
        print(mat, "triangles", n, "%.0fs" % (time.time() - T0), flush=True)
    for r in V["roads"]:
        if r["surface"] == "asphalt" and r["cls"] in ("primary", "secondary", "tertiary"):
            markings(mb_of, r)
        if r["surface"] == "steps":
            steps(mb_of, r)
    # murs de soutènement des places en terrasse (hors façades)
    nwall = 0
    for (p, gxp, gyp, c0) in V.get("plaza_planes", []):
        # contour adouci : les petites indentations du tracé ne donnent pas de murs en dents de scie
        ps = p.buffer(1.5, join_style=2).buffer(-1.5, join_style=2).simplify(0.4)
        ring = (ps if ps.geom_type == "Polygon" and not ps.is_empty else p).exterior
        n = max(2, int(ring.length / 1.0))
        run = []
        for k in range(n + 1):
            q = ring.interpolate(k * ring.length / n)
            a = ring.interpolate(max(0, k * ring.length / n - 0.5))
            b = ring.interpolate(min(ring.length, k * ring.length / n + 0.5))
            dv = np.array([b.x - a.x, b.y - a.y])
            dv /= np.linalg.norm(dv) + 1e-9
            out = np.array([dv[1], -dv[0]])
            if p.contains(Point(q.x + out[0] * 0.5, q.y + out[1] * 0.5)):
                out = -out
            z_in = gxp * q.x + gyp * q.y + c0
            z_out = float(grid_sample(G, [q.x + out[0] * 3.0], [q.y + out[1] * 3.0])[0])
            near_bld = bl_union.distance(q) < 1.5
            if abs(z_in - z_out) > 0.7 and not near_bld:
                run.append((q.x, q.y, z_in, z_out))
            elif run:
                if len(run) > 2:
                    terrace_wall(mb_of, run)
                    nwall += 1
                run = []
        if len(run) > 2:
            terrace_wall(mb_of, run)
            nwall += 1
    print("murs de terrasse:", nwall)
    for ln in V["walls"]:
        stone_wall(mb_of, ln, 1.1)
    for ln in V["retaining"]:
        stone_wall(mb_of, ln, 1.6, thick=0.6)
    print("routes terminées %.0fs" % (time.time() - T0))
    return chunks


if __name__ == "__main__":
    ch = build()
    with open("roads_out.pkl", "wb") as f:
        pickle.dump({k: v.arrays() for k, v in ch.items()}, f)
    print("tuiles:", len(ch), "triangles:", sum(v.tri_count() for v in ch.values()))
