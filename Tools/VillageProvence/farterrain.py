"""Relief lointain (Copernicus 30 m) : Luberon, monts de Vaucluse, mont Ventoux ; trou sous la zone détaillée."""
import sys, pickle, math
sys.path.insert(0,'.')
from common import *
from dem import sample_xy
from texlib import noise, band, hex2rgb, to_u8
from scipy import ndimage
R = 36000.0      # demi-largeur (m) : inclut le mont Ventoux au nord
STEP = 150.0
xs = np.arange(-R, R + 1, STEP); ys = np.arange(-R, R + 1, STEP)
X, Y = np.meshgrid(xs, ys)
Z = sample_xy(X, Y, order=1).astype(np.float32) - ZONE["z0"]
Z = ndimage.gaussian_filter(Z, 0.6)
inside = (X > ZONE["xmin"] + 60) & (X < ZONE["xmax"] - 60) & (Y > ZONE["ymin"] + 60) & (Y < ZONE["ymax"] - 60)
near = (X > ZONE["xmin"] - 200) & (X < ZONE["xmax"] + 200) & (Y > ZONE["ymin"] - 200) & (Y < ZONE["ymax"] + 200)
Z[near] -= 4.0
ny, nx = Z.shape
# gorges de la rivière des Ocres : elles se prolongent au-delà de la zone détaillée (pas de mur au bord de la carte)
river_mask = np.zeros_like(Z, bool)
try:
    _V = pickle.load(open("vec.pkl", "rb"))
    _rv = _V.get("river")
except Exception:
    _rv = None
if _rv is not None:
    import shapely
    from shapely.geometry import LineString as _LS
    xy, lv = _rv["xy"].astype(np.float64), _rv["level"].astype(np.float64)
    ext = 9000.0
    d0 = xy[0] - xy[min(40, len(xy) - 1)]
    d0 /= np.linalg.norm(d0)
    d1 = xy[-1] - xy[max(-41, -len(xy))]
    d1 /= np.linalg.norm(d1)
    pts = np.vstack([xy[0] + d0 * ext, xy, xy[-1] + d1 * ext])
    lvl = np.concatenate([[lv[0] + 0.002 * ext], lv, [lv[-1] - 0.002 * ext]])
    line = _LS(pts)
    s_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    P_ = shapely.points(X.ravel(), Y.ravel())
    dist = shapely.distance(line, P_).reshape(X.shape)
    sat = shapely.line_locate_point(line, P_).reshape(X.shape)
    lz = np.interp(sat, s_, lvl)
    valley = lz + np.clip(dist - 70.0, 0, None) * 0.9
    m = dist < 900
    Z[m] = np.minimum(Z[m], valley[m])
    river_mask = dist < 110
    print("horizon : gorges prolongées de %.0f km de part et d'autre" % (ext / 1000))
# couleur : forêts sur les pentes, cultures en plaine, sommet calcaire du Ventoux
gy, gx = np.gradient(Z, STEP)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
n = 1024
tex_n = noise(n, n / 40, 5)
from scipy.ndimage import zoom
alt = Z + ZONE["z0"]
forest = np.clip((slope - 4) / 8, 0, 1) * np.clip((1650 - alt) / 250, 0, 1)
fields = 1 - forest
col = np.zeros((ny, nx, 3), np.float32)
patch = zoom(noise(256, 30, 7), (ny / 256, nx / 256), order=1)[:ny, :nx]
patch2 = zoom(noise(256, 8, 8), (ny / 256, nx / 256), order=0)[:ny, :nx]
fcol = np.stack([0.24 + 0.03 * patch, 0.27 + 0.03 * patch, 0.16 + 0.02 * patch], -1)
c_fields = np.where((patch2 > 0.5)[..., None], np.array([0.62, 0.52, 0.33]), np.where((patch2 < -0.6)[..., None], np.array([0.42, 0.33, 0.45]), np.array([0.42, 0.4, 0.26])))
col = fcol * forest[..., None] + c_fields * fields[..., None]
summit = np.clip((alt - 1450) / 250, 0, 1)
col = col * (1 - summit[..., None]) + np.array([0.82, 0.8, 0.76]) * summit[..., None]
col = np.clip(col * (0.9 + 0.1 * patch[..., None]), 0, 1)
col[river_mask] = np.array([0.08, 0.16, 0.18])          # l'eau au fond des gorges
P = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]).astype(np.float32)
N = np.column_stack([-gx.ravel(), -gy.ravel(), np.ones(nx * ny)])
N /= np.linalg.norm(N, axis=1, keepdims=True)
UV = np.column_stack([(X.ravel() + R) / (2 * R), (R - Y.ravel()) / (2 * R)]).astype(np.float32)
idx = np.arange(nx * ny).reshape(ny, nx)
keep = ~(inside[:-1, :-1] & inside[1:, 1:] & inside[:-1, 1:] & inside[1:, :-1])
a, b, c, d = idx[:-1, :-1][keep], idx[:-1, 1:][keep], idx[1:, 1:][keep], idx[1:, :-1][keep]
I = np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, d])]).astype(np.int32)
C = np.full((nx * ny, 4), 255, np.uint8)
from PIL import Image
img = Image.fromarray(to_u8(col[::-1] ** (1 / 2.2) * 1.0)).resize((2048, 2048), Image.BICUBIC)
img.save("tex/Horizon_BC.png")
Image.new("RGB", (8, 8), (128, 128, 255)).save("tex/Horizon_N.png")
Image.new("RGB", (8, 8), (255, 235, 0)).save("tex/Horizon_ORM.png")
with open("far_out.pkl", "wb") as f:
    pickle.dump({"Horizon": dict(P=P, N=N.astype(np.float32), UV=UV, C=C, I=I)}, f)
print("horizon:", len(P), "sommets", len(I), "triangles; altitude max %.0f m" % alt.max())
