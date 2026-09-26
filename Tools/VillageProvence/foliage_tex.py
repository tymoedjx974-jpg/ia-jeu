"""Atlas de feuillage (RGBA, découpe alpha) dessinés procéduralement : 4 variantes par espèce (quadrants)."""
import sys, os, math
sys.path.insert(0, ".")
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from texlib import normal_from_height, to_u8, hex2rgb

OUT = "tex"
SS = 2  # sur-échantillonnage pour l'anticrénelage


def jitter_col(rng, c, amt=0.12):
    c = np.array(c, float)
    f = rng.uniform(1 - amt, 1 + amt)
    hue = rng.normal(0, amt * 0.4, 3)
    return tuple(int(np.clip(v * f * (1 + h), 0, 255)) for v, h in zip(c, hue))


def rot(pts, a):
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def leaf_shape(kind, L, W):
    """Contour d'une feuille le long de +x (base en 0, pointe en L)."""
    pts_top, pts_bot = [], []
    N = 18
    for i in range(N + 1):
        t = i / N
        if kind == "lance":
            w = W * math.sin(math.pi * t) ** 0.8 * (1 - 0.3 * t)
        elif kind == "oval":
            w = W * math.sin(math.pi * t) ** 0.6
        elif kind == "needle":
            w = W
        else:
            w = W * math.sin(math.pi * t) ** 0.7
        pts_top.append((t * L, w / 2))
        pts_bot.append((t * L, -w / 2))
    return pts_top + pts_bot[::-1]


def palmate(L, lobes=5, serr=0.0, rng=None):
    """Feuille palmée (platane, vigne) centrée sur la base, orientée +x."""
    pts = []
    N = 160
    for i in range(N):
        a = -math.pi * 0.95 + 1.9 * math.pi * i / N
        # rayon avec lobes
        ph = (a * lobes / (2 * math.pi) + 0.5) % 1.0
        lobe = (1 - abs(ph - 0.5) * 2) ** 1.6
        r = L * (0.42 + 0.58 * lobe) * (0.78 + 0.22 * math.cos(a * 0.5))
        if serr:
            r *= 1 + serr * (0.5 - (i % 3 == 0))
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def draw_leaf(dc, dh, x, y, ang, shape_pts, col, vein_col, hval=200):
    p = [(x + px, y + py) for px, py in rot(shape_pts, ang)]
    dc.polygon(p, fill=col)
    dh.polygon(p, fill=hval)
    return p


class Atlas:
    def __init__(self, size=1024):
        self.size = size
        S = size * SS
        self.col = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        self.hgt = Image.new("L", (S, S), 0)
        self.dc = ImageDraw.Draw(self.col)
        self.dh = ImageDraw.Draw(self.hgt)

    def quad(self, q):
        h = self.size * SS // 2
        return (q % 2) * h, (q // 2) * h, h

    def save(self, name, bleed_col):
        S = self.size
        col = self.col.resize((S, S), Image.LANCZOS)
        hgt = self.hgt.resize((S, S), Image.LANCZOS)
        a = np.asarray(col, np.float32) / 255.0
        rgb, alpha = a[..., :3], a[..., 3]
        # couleur débordante sous l'alpha (évite les franges sombres au mip-mapping)
        bleed = np.asarray(col.filter(ImageFilter.GaussianBlur(6)), np.float32) / 255.0
        bw = bleed[..., 3:4]
        fill = np.where(bw > 0.01, bleed[..., :3] / np.maximum(bw, 1e-3), np.array(bleed_col, np.float32) / 255.0)
        rgb = np.where(alpha[..., None] > 0.02, rgb / np.maximum(alpha[..., None], 1e-3), fill)
        h = np.asarray(hgt.filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255.0
        nrm = normal_from_height(h * 0.004, 0.001)
        os.makedirs(OUT, exist_ok=True)
        Image.fromarray(np.concatenate([to_u8(rgb), to_u8(alpha)[..., None]], -1)).save(f"{OUT}/{name}_BC.png")
        nd = nrm.copy()
        nd[..., 1] *= -1
        Image.fromarray(to_u8(nd * 0.5 + 0.5)).save(f"{OUT}/{name}_N.png")
        prev = Image.new("RGB", (S, S), (60, 90, 140))
        prev.paste(col.convert("RGB"), (0, 0), col)
        prev.save(f"texprev/{name}.jpg", quality=88)


def twig_cluster(at, q, rng, kind, leaf_len, leaf_w, n_leaves, cols, under_col=None, stem_col=(90, 80, 60), spread=0.9, opposite=True, stem_w=3):
    ox, oy, h = at.quad(q)
    cx = ox + h * 0.5
    base = (cx, oy + h * 0.97)
    L = h * 0.92
    # tige principale courbe vers le haut + rameaux
    stems = []
    ang0 = -math.pi / 2 + rng.normal(0, 0.12)
    pts = [base]
    x, y, a = base[0], base[1], ang0
    for i in range(24):
        a += rng.normal(0, 0.05)
        x += math.cos(a) * L / 24
        y += math.sin(a) * L / 24
        pts.append((x, y))
    stems.append(pts)
    for k in range(rng.integers(2, 5)):
        i0 = rng.integers(5, 16)
        sx, sy = pts[i0]
        a = ang0 + rng.choice([-1, 1]) * rng.uniform(0.5, 1.0)
        p2 = [(sx, sy)]
        ln = L * rng.uniform(0.35, 0.55)
        for i in range(12):
            a += rng.normal(0, 0.05)
            sx += math.cos(a) * ln / 12
            sy += math.sin(a) * ln / 12
            p2.append((sx, sy))
        stems.append(p2)
    for st in stems:
        at.dc.line(st, fill=stem_col + (255,), width=stem_w * SS)
        at.dh.line(st, fill=120, width=stem_w * SS)
    # feuilles le long des tiges
    for st in stems:
        m = len(st)
        per = max(2, int(n_leaves * m / 60))
        for i in range(per):
            t = rng.uniform(0.15, 1.0)
            idx = min(m - 2, int(t * (m - 1)))
            x0, y0 = st[idx]
            x1, y1 = st[idx + 1]
            a_st = math.atan2(y1 - y0, x1 - x0)
            sides = (-1, 1) if opposite else (rng.choice([-1, 1]),)
            for sd in sides:
                a = a_st + sd * rng.uniform(0.5, 1.1) * spread
                ll = leaf_len * rng.uniform(0.75, 1.2) * SS
                ww = leaf_w * rng.uniform(0.8, 1.2) * SS
                if kind == "palm":
                    shp = palmate(ll * 0.5, lobes=5)
                    ang = a
                    px_, py_ = x0 + math.cos(a) * ll * 0.45, y0 + math.sin(a) * ll * 0.45
                else:
                    shp = leaf_shape(kind, ll, ww)
                    ang = a
                    px_, py_ = x0, y0
                show_under = under_col is not None and rng.random() < 0.35
                c = jitter_col(rng, under_col if show_under else cols[rng.integers(len(cols))])
                draw_leaf(at.dc, at.dh, px_, py_, ang, shp, c + (255,), None, hval=int(rng.uniform(150, 255)))
                # nervure centrale
                vx = [(px_, py_), (px_ + math.cos(ang) * ll * 0.8, py_ + math.sin(ang) * ll * 0.8)] if kind != "palm" else None
                if vx and ll > 20 * SS:
                    vc = tuple(min(255, int(v * 1.25)) for v in c) + (255,)
                    at.dc.line(vx, fill=vc, width=max(1, SS))


def needles(at, q, rng, cols, n_fasc=60, needle_len=0.22, spread=2.2):
    ox, oy, h = at.quad(q)
    base = (ox + h * 0.5, oy + h * 0.95)
    # branche
    pts = [base]
    x, y, a = base[0], base[1], -math.pi / 2 + rng.normal(0, 0.1)
    for i in range(20):
        a += rng.normal(0, 0.06)
        x += math.cos(a) * h * 0.85 / 20
        y += math.sin(a) * h * 0.85 / 20
        pts.append((x, y))
    at.dc.line(pts, fill=(95, 70, 50, 255), width=5 * SS)
    for k in range(n_fasc):
        t = rng.uniform(0.2, 1.0)
        idx = min(len(pts) - 1, int(t * (len(pts) - 1)))
        x0, y0 = pts[idx]
        x0 += rng.normal(0, h * 0.04)
        y0 += rng.normal(0, h * 0.04)
        c0 = cols[rng.integers(len(cols))]
        for j in range(rng.integers(10, 22)):
            a = rng.uniform(-math.pi, math.pi) if spread > 3 else -math.pi / 2 + rng.normal(0, spread / 2)
            ln = h * needle_len * rng.uniform(0.6, 1.1)
            c = jitter_col(rng, c0, 0.1) + (255,)
            x1, y1 = x0 + math.cos(a) * ln, y0 + math.sin(a) * ln
            at.dc.line([(x0, y0), (x1, y1)], fill=c, width=max(1, int(1.6 * SS)))
            at.dh.line([(x0, y0), (x1, y1)], fill=int(rng.uniform(140, 255)), width=max(1, int(1.6 * SS)))


def scales(at, q, rng, cols, blobs=900, r=(3, 7)):
    """Cyprès / garrigue : amas denses de petites écailles dans une silhouette."""
    ox, oy, h = at.quad(q)
    cx, cy = ox + h / 2, oy + h / 2
    for i in range(blobs):
        ang = rng.uniform(0, 2 * math.pi)
        rad = h * 0.44 * math.sqrt(rng.random())
        x, y = cx + math.cos(ang) * rad, cy + math.sin(ang) * rad * 1.05
        rr = rng.uniform(*r) * SS
        c = jitter_col(rng, cols[rng.integers(len(cols))], 0.15) + (255,)
        # petite gerbe de 3 écailles
        for k in range(3):
            a = rng.uniform(0, 2 * math.pi)
            px_, py_ = x + math.cos(a) * rr, y + math.sin(a) * rr
            at.dc.ellipse([px_ - rr, py_ - rr * 0.6, px_ + rr, py_ + rr * 0.6], fill=c)
            at.dh.ellipse([px_ - rr, py_ - rr * 0.6, px_ + rr, py_ + rr * 0.6], fill=int(rng.uniform(120, 255)))


def spikes(at, q, rng, stem_cols, flower_cols, n=26, flower_frac=0.3):
    """Lavande : tiges fines + épis violets."""
    ox, oy, h = at.quad(q)
    for i in range(n):
        bx = ox + h * rng.uniform(0.25, 0.75)
        by = oy + h * 0.99
        a = -math.pi / 2 + rng.normal(0, 0.22)
        L = h * rng.uniform(0.6, 0.95)
        tx, ty = bx + math.cos(a) * L, by + math.sin(a) * L
        c = jitter_col(rng, stem_cols[rng.integers(len(stem_cols))]) + (255,)
        at.dc.line([(bx, by), (tx, ty)], fill=c, width=2 * SS)
        at.dh.line([(bx, by), (tx, ty)], fill=150, width=2 * SS)
        fc = flower_cols[rng.integers(len(flower_cols))]
        nf = rng.integers(10, 18)
        for k in range(nf):
            t = 1 - flower_frac * k / nf
            px_, py_ = bx + math.cos(a) * L * t, by + math.sin(a) * L * t
            rr = rng.uniform(3.0, 4.8) * SS * (0.7 + 0.3 * (k / nf))
            col = jitter_col(rng, fc, 0.1) + (255,)
            at.dc.ellipse([px_ - rr, py_ - rr, px_ + rr, py_ + rr], fill=col)
            at.dh.ellipse([px_ - rr, py_ - rr, px_ + rr, py_ + rr], fill=255)
        # quelques feuilles étroites en bas
    for i in range(40):
        bx = ox + h * rng.uniform(0.3, 0.7)
        by = oy + h * 0.99
        a = -math.pi / 2 + rng.normal(0, 0.5)
        L = h * rng.uniform(0.12, 0.3)
        c = jitter_col(rng, (110, 125, 95)) + (255,)
        at.dc.line([(bx, by), (bx + math.cos(a) * L, by + math.sin(a) * L)], fill=c, width=3 * SS)


def grass(at, q, rng, cols, n=120, height=(0.5, 0.95), heads=None):
    ox, oy, h = at.quad(q)
    for i in range(n):
        bx = ox + h * rng.uniform(0.08, 0.92)
        by = oy + h * 0.995
        a = -math.pi / 2 + rng.normal(0, 0.25)
        L = h * rng.uniform(*height)
        bend = rng.normal(0, 0.25)
        pts = []
        for k in range(9):
            t = k / 8
            aa = a + bend * t * t
            pts.append((bx + math.cos(aa) * L * t, by + math.sin(aa) * L * t))
        c = jitter_col(rng, cols[rng.integers(len(cols))]) + (255,)
        w = rng.integers(2, 4) * SS
        for k in range(8):
            ww = max(1, int(w * (1 - k / 9)))
            at.dc.line([pts[k], pts[k + 1]], fill=c, width=ww)
            at.dh.line([pts[k], pts[k + 1]], fill=int(200 - 10 * k), width=ww)
        if heads and rng.random() < 0.35:
            x, y = pts[-1]
            hc = jitter_col(rng, heads) + (255,)
            at.dc.ellipse([x - 3 * SS, y - 9 * SS, x + 3 * SS, y + 2 * SS], fill=hc)


def flowers(at, q, rng, leaf_cols, flower_cols, n_clusters=14, petal_r=(4, 7), leaf_kind="round"):
    ox, oy, h = at.quad(q)
    cx, cy = ox + h / 2, oy + h / 2
    for i in range(70):
        a = rng.uniform(0, 2 * math.pi)
        rad = h * 0.4 * math.sqrt(rng.random())
        x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad
        rr = h * rng.uniform(0.05, 0.09)
        c = jitter_col(rng, leaf_cols[rng.integers(len(leaf_cols))]) + (255,)
        if leaf_kind == "round":
            at.dc.ellipse([x - rr, y - rr * 0.9, x + rr, y + rr * 0.9], fill=c)
        else:
            shp = leaf_shape("lance", rr * 2.2, rr * 0.6)
            at.dc.polygon([(x + px_, y + py_) for px_, py_ in rot(shp, rng.uniform(0, 6.28))], fill=c)
        at.dh.ellipse([x - rr, y - rr, x + rr, y + rr], fill=int(rng.uniform(100, 200)))
    for i in range(n_clusters):
        a = rng.uniform(0, 2 * math.pi)
        rad = h * 0.36 * math.sqrt(rng.random())
        x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad
        fc = flower_cols[rng.integers(len(flower_cols))]
        for k in range(rng.integers(8, 16)):
            px_, py_ = x + rng.normal(0, h * 0.03), y + rng.normal(0, h * 0.03)
            rr = rng.uniform(*petal_r) * SS
            col = jitter_col(rng, fc, 0.1) + (255,)
            at.dc.ellipse([px_ - rr, py_ - rr, px_ + rr, py_ + rr], fill=col)
            at.dh.ellipse([px_ - rr, py_ - rr, px_ + rr, py_ + rr], fill=255)


def build():
    os.makedirs("texprev", exist_ok=True)
    rng = np.random.default_rng(7)
    # Olivier : feuilles lancéolées gris-vert, revers argenté
    at = Atlas(1024)
    for q in range(4):
        twig_cluster(at, q, rng, "lance", 70, 12, 44, [(88, 102, 70), (98, 110, 78), (80, 95, 66), (105, 115, 85)], under_col=(165, 172, 150), stem_col=(110, 100, 80), spread=0.8)
    at.save("FeuillesOlivier", (95, 105, 75))
    # Platane : grandes feuilles palmées
    at = Atlas(1024)
    for q in range(4):
        twig_cluster(at, q, rng, "palm", 150, 0, 12, [(92, 125, 58), (104, 136, 62), (84, 115, 52), (118, 140, 70)], under_col=(140, 160, 100), stem_col=(120, 110, 70), spread=1.0, opposite=False, stem_w=4)
    at.save("FeuillesPlatane", (95, 125, 60))
    # Chêne vert : petites feuilles ovales sombres
    at = Atlas(1024)
    for q in range(4):
        twig_cluster(at, q, rng, "oval", 42, 20, 70, [(58, 74, 44), (66, 82, 48), (52, 68, 40), (74, 88, 56)], under_col=(120, 125, 100), stem_col=(90, 80, 60), spread=0.9)
    at.save("FeuillesChene", (60, 75, 45))
    # Arbre fruitier (cerisier) : feuilles ovales vertes
    at = Atlas(1024)
    for q in range(4):
        twig_cluster(at, q, rng, "oval", 80, 34, 30, [(80, 120, 50), (92, 130, 56), (72, 108, 46), (100, 136, 60)], under_col=(130, 160, 90), stem_col=(100, 70, 55), spread=0.8, opposite=False)
    at.save("FeuillesFruitier", (85, 120, 55))
    # Vigne : feuilles palmées
    at = Atlas(1024)
    for q in range(4):
        twig_cluster(at, q, rng, "palm", 125, 0, 14, [(98, 132, 58), (110, 142, 60), (90, 122, 50), (128, 148, 64), (150, 150, 70)], under_col=(150, 170, 110), stem_col=(110, 90, 60), spread=1.1, opposite=False, stem_w=4)
    at.save("FeuillesVigne", (100, 130, 60))
    # Pin : aiguilles
    at = Atlas(1024)
    for q in range(4):
        needles(at, q, rng, [(104, 124, 66), (92, 112, 58), (116, 132, 74), (84, 100, 52)], n_fasc=70, needle_len=0.2)
    at.save("AiguillesPin", (95, 115, 60))
    # Cyprès : écailles sombres
    at = Atlas(1024)
    for q in range(4):
        scales(at, q, rng, [(46, 62, 38), (54, 70, 42), (40, 54, 34), (62, 78, 48)], blobs=1100, r=(4, 8))
    at.save("FeuillesCypres", (48, 64, 40))
    # Garrigue (chêne kermès, genévrier, romarin)
    at = Atlas(1024)
    for q in range(4):
        scales(at, q, rng, [(84, 96, 64), (96, 104, 72), (72, 86, 58), (110, 112, 80)], blobs=900, r=(3, 6))
    at.save("FeuillesGarrigue", (85, 95, 65))
    # Lavande
    at = Atlas(1024)
    for q in range(4):
        spikes(at, q, rng, [(120, 135, 105), (110, 125, 100), (135, 145, 115)], [(112, 84, 172), (128, 100, 188), (100, 74, 160), (142, 114, 198)], n=48, flower_frac=0.38)
    at.save("Lavande", (120, 110, 150))
    # Herbes sèches (été provençal)
    at = Atlas(1024)
    for q in range(4):
        grass(at, q, rng, [(196, 176, 112), (176, 160, 100), (150, 142, 90), (210, 196, 140), (130, 130, 80)], n=130, heads=(210, 190, 130))
    at.save("HerbeSeche", (180, 160, 100))
    # Herbe verte (jardins arrosés)
    at = Atlas(1024)
    for q in range(4):
        grass(at, q, rng, [(92, 122, 52), (104, 134, 58), (80, 110, 46), (120, 140, 70)], n=150, height=(0.35, 0.75))
    at.save("HerbeVerte", (90, 120, 50))
    # Fleurs : géraniums (0-1), bougainvillier (2), laurier-rose (3)
    at = Atlas(1024)
    flowers(at, 0, rng, [(70, 110, 50), (80, 120, 55)], [(200, 30, 50), (215, 45, 60)], n_clusters=16)
    flowers(at, 1, rng, [(70, 110, 50), (80, 120, 55)], [(230, 90, 140), (240, 120, 160)], n_clusters=16)
    flowers(at, 2, rng, [(60, 100, 45), (70, 110, 50)], [(200, 30, 130), (215, 50, 150), (180, 20, 110)], n_clusters=26, petal_r=(5, 9))
    flowers(at, 3, rng, [(60, 90, 50), (70, 100, 55)], [(235, 140, 160), (245, 170, 185), (250, 240, 240)], n_clusters=18, leaf_kind="lance")
    at.save("Fleurs", (80, 110, 55))
    # Glycine (grappes mauves)
    at = Atlas(1024)
    for q in range(4):
        ox, oy, h = at.quad(q)
        for i in range(9):
            x0 = ox + h * rng.uniform(0.15, 0.85)
            y0 = oy + h * rng.uniform(0.05, 0.3)
            L = h * rng.uniform(0.35, 0.6)
            for k in range(28):
                t = k / 28
                px_, py_ = x0 + rng.normal(0, 3 * SS), y0 + L * t
                rr = (1 - t * 0.6) * rng.uniform(5, 8) * SS
                c = jitter_col(rng, (165, 140, 210), 0.12) + (255,)
                at.dc.ellipse([px_ - rr, py_ - rr * 0.8, px_ + rr, py_ + rr * 0.8], fill=c)
                at.dh.ellipse([px_ - rr, py_ - rr, px_ + rr, py_ + rr], fill=230)
        for i in range(25):
            x, y = ox + h * rng.uniform(0.05, 0.95), oy + h * rng.uniform(0.0, 0.35)
            shp = leaf_shape("oval", h * 0.1, h * 0.04)
            at.dc.polygon([(x + a, y + b) for a, b in rot(shp, rng.uniform(0, 6.28))], fill=jitter_col(rng, (95, 125, 55)) + (255,))
    at.save("Glycine", (150, 130, 190))


if __name__ == "__main__":
    build()
