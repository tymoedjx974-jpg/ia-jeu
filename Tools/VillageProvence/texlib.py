"""Outils de génération de textures PBR raccordables (tileables)."""
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from PIL import Image

F32 = np.float32


def _freq(n):
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.rfftfreq(n)[None, :]
    return np.sqrt(fx * fx + fy * fy)


_FREQ = {}


def freq(n):
    if n not in _FREQ:
        _FREQ[n] = _freq(n)
    return _FREQ[n]


def noise(n, size_px, seed, beta=2.0, aniso=1.0):
    """Bruit fractal raccordable : détails de taille <= size_px (pixels), spectre 1/f^beta. aniso>1 étire en vertical."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n)).astype(F32)
    Fw = np.fft.rfft2(w)
    if aniso != 1.0:
        fy = np.fft.fftfreq(n)[:, None] * aniso
        fx = np.fft.rfftfreq(n)[None, :]
        f = np.sqrt(fx * fx + fy * fy)
    else:
        f = freq(n)
    fmin = 1.0 / size_px
    with np.errstate(divide="ignore", invalid="ignore"):
        amp = np.where(f > 0, (np.maximum(f, fmin) / fmin) ** (-beta / 2.0), 0.0)
        amp = amp * np.where(f < fmin, (f / fmin) ** 2, 1.0)
    out = np.fft.irfft2(Fw * amp, s=(n, n)).astype(F32)
    out -= out.mean()
    out /= out.std() + 1e-8
    return out


def band(n, size_px, seed, width=0.6, aniso=1.0):
    """Bruit à une seule échelle (log-gaussien autour de 1/size_px)."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n)).astype(F32)
    Fw = np.fft.rfft2(w)
    fy = np.fft.fftfreq(n)[:, None] * aniso
    fx = np.fft.rfftfreq(n)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f0 = 1.0 / size_px
    with np.errstate(divide="ignore"):
        lg = np.log(np.maximum(f, 1e-9) / f0)
    amp = np.exp(-(lg ** 2) / (2 * width ** 2))
    amp[0, 0] = 0
    out = np.fft.irfft2(Fw * amp, s=(n, n)).astype(F32)
    out -= out.mean()
    out /= out.std() + 1e-8
    return out


def blur(a, s):
    if a.ndim == 3:
        return np.stack([ndimage.gaussian_filter(a[..., i], s, mode="wrap") for i in range(a.shape[2])], -1)
    return ndimage.gaussian_filter(a, s, mode="wrap")


def blur_y(a, s):
    return ndimage.gaussian_filter1d(a, s, axis=0, mode="wrap")


def blur_x(a, s):
    return ndimage.gaussian_filter1d(a, s, axis=1, mode="wrap")


def warp(a, dx, dy, order=1):
    n0, n1 = a.shape[:2]
    yy, xx = np.mgrid[0:n0, 0:n1].astype(F32)
    if a.ndim == 3:
        return np.stack([ndimage.map_coordinates(a[..., i], [yy + dy, xx + dx], order=order, mode="grid-wrap") for i in range(a.shape[2])], -1)
    return ndimage.map_coordinates(a, [yy + dy, xx + dx], order=order, mode="grid-wrap")


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def edt_wrap(mask):
    """Distance (px) au pixel False le plus proche, avec raccord périodique."""
    n0, n1 = mask.shape
    big = np.tile(mask, (3, 3))
    d = ndimage.distance_transform_edt(big)
    return d[n0:2 * n0, n1:2 * n1].astype(F32)


def edges_of(label):
    e = (label != np.roll(label, 1, 0)) | (label != np.roll(label, 1, 1)) | (label != np.roll(label, -1, 0)) | (label != np.roll(label, -1, 1))
    return e


def voronoi(n, cells, seed, jitter=0.9, stretch=(1.0, 1.0), k=2):
    """Voronoi périodique sur grille jitterée. Renvoie F1, F2 (px), identifiant de cellule, points."""
    rng = np.random.default_rng(seed)
    gx, gy = (cells, cells) if np.isscalar(cells) else cells
    sx, sy = n / gx, n / gy
    ii, jj = np.meshgrid(np.arange(gx), np.arange(gy))
    px = ((ii + 0.5 + (rng.random((gy, gx)) - 0.5) * jitter) * sx) % n
    py = ((jj + 0.5 + (rng.random((gy, gx)) - 0.5) * jitter) * sy) % n
    ax, ay = stretch
    pts = np.stack([px.ravel() * ax, py.ravel() * ay], -1)
    tree = cKDTree(pts, boxsize=[n * ax, n * ay])
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) + 0.5
    q = np.stack([xx.ravel() * ax, yy.ravel() * ay], -1)
    d, idx = tree.query(q, k=k, workers=-1)
    F1 = d[:, 0].reshape(n, n).astype(F32)
    F2 = d[:, 1].reshape(n, n).astype(F32)
    ID = idx[:, 0].reshape(n, n)
    return F1, F2, ID, np.stack([px.ravel(), py.ravel()], -1)


def rand_per_id(ID, seed, count=None):
    rng = np.random.default_rng(seed)
    m = int(ID.max()) + 1 if count is None else count
    return rng.random(m).astype(F32)[ID]


def normal_from_height(h_m, px_m, strength=1.0):
    """Normale tangente (convention OpenGL, Y vers le haut de l'image) depuis une hauteur en mètres."""
    dx = (np.roll(h_m, -1, 1) - np.roll(h_m, 1, 1)) * 0.5 / px_m
    dy = (np.roll(h_m, -1, 0) - np.roll(h_m, 1, 0)) * 0.5 / px_m
    nrm = np.stack([-dx * strength, dy * strength, np.ones_like(h_m)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    return nrm.astype(F32)


def ao_from_height(h_m, px_m, radius_m=(0.01, 0.04, 0.12), depth_m=0.01, power=1.0):
    ao = np.ones_like(h_m)
    for r in radius_m:
        s = max(0.5, r / px_m)
        cav = blur(h_m, s) - h_m
        ao *= np.clip(1.0 - np.maximum(cav, 0) / (depth_m * (r / radius_m[0]) ** 0.5), 0.0, 1.0) ** (power / len(radius_m))
    return np.clip(ao, 0.15, 1.0).astype(F32)


def hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


def palette_pick(ID, cols, seed, weights=None):
    cols = np.asarray(cols, F32)
    rng = np.random.default_rng(seed)
    m = int(ID.max()) + 1
    p = None if weights is None else np.asarray(weights, float) / np.sum(weights)
    choice = rng.choice(len(cols), size=m, p=p)
    return cols[choice][ID]


def lerp(a, b, t):
    if np.ndim(t) == 2 and np.ndim(a) == 3 or (np.ndim(t) == 2 and np.ndim(b) == 3):
        t = t[..., None]
    return a + (b - a) * t


def to_u8(a):
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def save_set(name, outdir, albedo, height_m, px_m, rough, ao=None, mask=None, normal_strength=1.0, alpha=None, extra_normal=None):
    """Écrit <name>_BC.png (sRGB), <name>_N.png (normale DirectX pour Unreal), <name>_ORM.png (AO, rugosité, masque de teinte)."""
    import os
    os.makedirs(outdir, exist_ok=True)
    nrm = normal_from_height(height_m, px_m, normal_strength) if extra_normal is None else extra_normal
    if ao is None:
        ao = ao_from_height(height_m, px_m)
    if mask is None:
        mask = np.zeros_like(rough)
    bc = to_u8(albedo)
    if alpha is not None:
        bc = np.concatenate([bc, to_u8(alpha)[..., None]], -1)
    Image.fromarray(bc).save(f"{outdir}/{name}_BC.png", optimize=False, compress_level=4)
    nd = nrm.copy()
    nd[..., 1] *= -1.0  # DirectX (Unreal) : vert inversé
    Image.fromarray(to_u8(nd * 0.5 + 0.5)).save(f"{outdir}/{name}_N.png", compress_level=4)
    orm = np.stack([ao, rough, mask], -1)
    Image.fromarray(to_u8(orm)).save(f"{outdir}/{name}_ORM.png", compress_level=4)
    return nrm, ao


def preview(albedo, nrm, ao, tiles=2, light=(-0.5, 0.6, 0.62)):
    L = np.asarray(light, F32)
    L /= np.linalg.norm(L)
    lin = np.clip(albedo, 0, 1) ** 2.2
    sh = np.clip((nrm * L).sum(-1), 0, 1) * 0.85 + 0.2
    img = (lin * (sh * ao)[..., None]) ** (1 / 2.2)
    img = np.tile(img, (tiles, tiles, 1))
    return Image.fromarray(to_u8(img))
