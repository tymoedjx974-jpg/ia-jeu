"""Transforme une photo (mur, toit, sol, bois, écorce...) en texture PBR raccordable pour le village.

    python photo_texture.py photo.jpg PierreMoellons --taille 2.0

- recadre au carré (ou --zone x0 y0 x1 y1 en pixels), redimensionne (2048 par défaut) ;
- retire l'éclairage de la photo (ombres douces, dégradés) pour garder la couleur propre de la matière ;
- rend la texture raccordable sans couture (fondu entre quatre décalages de la photo) ;
- calcule le relief à partir de la photo, puis la normale (DirectX), l'occlusion et la rugosité ;
- écrit tex/<Nom>_BC.png, _N.png, _ORM.png : export_ue.py les emporte dans le plugin à la place des textures générées.
--taille : largeur réelle couverte par la photo, en mètres (mise à jour de materials.TILE à la main si elle change).
--teinte : le canal de masque vaut 1 (la couleur des façades ou des volets s'applique), sinon 0.
Utilise uniquement des photos que tu as le droit d'utiliser (les tiennes, ou sous licence libre CC0).
"""
import argparse, os
import numpy as np
from PIL import Image
from scipy import ndimage
from texlib import normal_from_height, ao_from_height, to_u8

F32 = np.float32


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def delight(rgb, strength=0.85):
    """Divise par l'éclairage basse fréquence (luminance très floutée) : les ombres portées douces disparaissent."""
    lin = srgb_to_lin(rgb)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722], F32)
    n = rgb.shape[0]
    light = ndimage.gaussian_filter(lum, n / 10, mode="wrap")
    light = light / light.mean()
    corr = light ** strength
    return lin_to_srgb(lin / corr[..., None])


def make_tileable(img):
    """Fondu entre la photo et trois copies décalées d'une demi-taille : aucune couture aux bords."""
    n = img.shape[0]
    t = np.arange(n, dtype=F32) / n
    # la photo reste intacte au centre ; le fondu n'occupe que les bandes proches des bords
    e = np.clip(np.minimum(t, 1 - t) / 0.18, 0, 1)
    s = e * e * (3 - 2 * e)
    sx, sy = s[None, :], s[:, None]
    A = img
    X = np.roll(img, n // 2, axis=1)
    Y = np.roll(img, n // 2, axis=0)
    XY = np.roll(X, n // 2, axis=0)
    w = [(sx * sy), ((1 - sx) * sy), (sx * (1 - sy)), ((1 - sx) * (1 - sy))]
    out = sum(im * wi[..., None] for im, wi in zip((A, X, Y, XY), w)) / sum(w)[..., None]
    # le fondu adoucit le contraste : on le rétablit localement
    mean = ndimage.uniform_filter(img, size=(n // 16, n // 16, 1), mode="wrap")
    mo = ndimage.uniform_filter(out, size=(n // 16, n // 16, 1), mode="wrap")
    so = np.sqrt(ndimage.uniform_filter((out - mo) ** 2, size=(n // 16, n // 16, 1), mode="wrap")) + 1e-4
    si = np.sqrt(ndimage.uniform_filter((img - mean) ** 2, size=(n // 16, n // 16, 1), mode="wrap")).mean(axis=(0, 1)) + 1e-4
    return np.clip(mo + (out - mo) * np.clip(si / so, 1.0, 1.8), 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("nom", help="nom de la texture (par ex. PierreMoellons pour remplacer les murs en moellons)")
    ap.add_argument("--taille", type=float, default=2.0, help="largeur réelle de la zone photographiée (m)")
    ap.add_argument("--resolution", type=int, default=2048)
    ap.add_argument("--zone", type=int, nargs=4, default=None, help="x0 y0 x1 y1 à recadrer (pixels)")
    ap.add_argument("--relief", type=float, default=0.012, help="profondeur du relief (m) : 0,02 pour des moellons, 0,003 pour un enduit")
    ap.add_argument("--rugosite", type=float, nargs=2, default=(0.55, 0.95), help="rugosité des parties claires et sombres")
    ap.add_argument("--teinte", action="store_true", help="la couleur par instance s'applique (enduit, bois peint)")
    ap.add_argument("--eclairage", type=float, default=0.85, help="0 = garder l'éclairage de la photo, 1 = le retirer entièrement")
    a = ap.parse_args()

    im = Image.open(a.photo).convert("RGB")
    if a.zone:
        im = im.crop(tuple(a.zone))
    w, h = im.size
    c = min(w, h)
    im = im.crop(((w - c) // 2, (h - c) // 2, (w - c) // 2 + c, (h - c) // 2 + c)).resize((a.resolution, a.resolution), Image.LANCZOS)
    rgb = np.asarray(im, F32) / 255.0
    rgb = delight(rgb, a.eclairage)
    rgb = make_tileable(rgb)
    n = a.resolution
    px = a.taille / n
    # relief : luminance passe-haut (les creux sont plus sombres dans une photo de matière)
    lum = rgb @ np.array([0.299, 0.587, 0.114], F32)
    hp = lum - ndimage.gaussian_filter(lum, n / 24, mode="wrap")
    fine = lum - ndimage.gaussian_filter(lum, 2, mode="wrap")
    height = (hp / (np.abs(hp).max() + 1e-6)) * a.relief + fine * a.relief * 0.15
    nrm = normal_from_height(height.astype(F32), px, 1.0)
    ao = ao_from_height(height.astype(F32), px, depth_m=a.relief * 0.8)
    rough = np.clip(a.rugosite[1] + (a.rugosite[0] - a.rugosite[1]) * (lum - lum.min()) / (np.ptp(lum) + 1e-6), 0, 1)
    mask = np.ones_like(lum) if a.teinte else np.zeros_like(lum)
    os.makedirs("tex", exist_ok=True)
    Image.fromarray(to_u8(rgb)).save(f"tex/{a.nom}_BC.png")
    nd = nrm.copy()
    nd[..., 1] *= -1
    Image.fromarray(to_u8(nd * 0.5 + 0.5)).save(f"tex/{a.nom}_N.png")
    Image.fromarray(to_u8(np.stack([ao, rough, mask], -1))).save(f"tex/{a.nom}_ORM.png")
    os.makedirs("texprev", exist_ok=True)
    prev = Image.fromarray(to_u8(np.tile(rgb, (2, 2, 1))))
    prev.thumbnail((1024, 1024))
    prev.save(f"texprev/{a.nom}.jpg", quality=88)
    print(f"texture {a.nom} écrite ({n} px, {a.taille} m) ; aperçu raccordé 2 x 2 : texprev/{a.nom}.jpg")


if __name__ == "__main__":
    main()
