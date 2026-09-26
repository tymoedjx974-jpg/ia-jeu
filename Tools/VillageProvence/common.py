import math, random
import numpy as np
import shapely
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw

# Zone jouable (mètres, repère local centré sur la place du village ; x = est, y = nord)
ZONE = dict(xmin=-2200.0, xmax=1800.0, ymin=-1800.0, ymax=2200.0, res=2.0, z0=300.0)
RES = ZONE["res"]
NX = int(round((ZONE["xmax"] - ZONE["xmin"]) / RES)) + 1
NY = int(round((ZONE["ymax"] - ZONE["ymin"]) / RES)) + 1
XS = ZONE["xmin"] + np.arange(NX) * RES
YS = ZONE["ymin"] + np.arange(NY) * RES
ZBOX = box(ZONE["xmin"], ZONE["ymin"], ZONE["xmax"], ZONE["ymax"])

# Couches du sol (poids de mélange du matériau de terrain)
LAYERS = ["dry", "earth", "ochre", "rock", "forest", "grass", "dirt", "straw"]
L = {n: i for i, n in enumerate(LAYERS)}


def polys_of(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    if g.geom_type in ("MultiPolygon", "GeometryCollection"):
        out = []
        for p in g.geoms:
            out += polys_of(p)
        return out
    return []


def lines_of(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    if g.geom_type in ("MultiLineString", "GeometryCollection"):
        out = []
        for p in g.geoms:
            out += lines_of(p)
        return out
    return []


def _pix(coords):
    return [((x - ZONE["xmin"]) / RES + 0.5, (y - ZONE["ymin"]) / RES + 0.5) for x, y in coords]


def rasterize(geoms, value=255, line_width_m=None):
    """Rasterise des polygones (ou lignes épaissies) sur la grille du terrain -> uint8 (NY, NX), ligne j = y croissant."""
    img = Image.new("L", (NX, NY), 0)
    d = ImageDraw.Draw(img)
    for g in geoms:
        if g is None or g.is_empty:
            continue
        if g.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection") and line_width_m is None:
            for p in polys_of(g):
                if len(p.exterior.coords) >= 3:
                    d.polygon(_pix(p.exterior.coords), fill=value)
                for h in p.interiors:
                    if len(h.coords) >= 3:
                        d.polygon(_pix(h.coords), fill=0)
        else:
            w = max(1, int(round((line_width_m or RES) / RES)))
            for ln in lines_of(g) if g.geom_type != "Polygon" else [g.exterior]:
                cs = _pix(ln.coords)
                if len(cs) >= 2:
                    d.line(cs, fill=value, width=w, joint="curve")
    return np.asarray(img, dtype=np.uint8)


def fbm(shape, cell_px, octaves=4, seed=0, gain=0.5):
    """Bruit fractal lisse (somme d'octaves de bruit gaussien interpolé)."""
    from scipy.ndimage import zoom
    rng = np.random.default_rng(seed)
    out = np.zeros(shape, np.float32)
    amp, total = 1.0, 0.0
    cell = float(cell_px)
    for o in range(octaves):
        gy = max(2, int(math.ceil(shape[0] / cell)) + 3)
        gx = max(2, int(math.ceil(shape[1] / cell)) + 3)
        g = rng.standard_normal((gy, gx)).astype(np.float32)
        z = zoom(g, cell, order=3)[: shape[0], : shape[1]]
        if z.shape != shape:
            z = np.pad(z, ((0, shape[0] - z.shape[0]), (0, shape[1] - z.shape[1])), mode="edge")
        out += amp * z
        total += amp
        amp *= gain
        cell /= 2.0
        if cell < 1.0:
            break
    return out / total


def grid_sample(arr, x, y, order=1):
    """Échantillonne une grille du terrain en coordonnées monde."""
    from scipy.ndimage import map_coordinates
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    i = (x - ZONE["xmin"]) / RES
    j = (y - ZONE["ymin"]) / RES
    return map_coordinates(arr, [j, i], order=order, mode="nearest")


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def srgb_to_lin(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def ombr(poly):
    """Rectangle orienté minimal : (centre, axe long unitaire, longueur, largeur)."""
    r = poly.minimum_rotated_rectangle
    if r.geom_type != "Polygon":
        c = poly.centroid
        return np.array([c.x, c.y]), np.array([1.0, 0.0]), 1.0, 1.0
    cs = np.array(r.exterior.coords)[:4]
    e1 = cs[1] - cs[0]
    e2 = cs[2] - cs[1]
    l1, l2 = np.linalg.norm(e1), np.linalg.norm(e2)
    c = cs.mean(axis=0)
    if l1 >= l2:
        return c, e1 / max(l1, 1e-9), l1, l2
    return c, e2 / max(l2, 1e-9), l2, l1
