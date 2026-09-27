"""Atlas « Graffitis » (RGBA, découpe alpha) : inscriptions à la bombe, marques de fouille, traces de sang, suie,
impacts de balles ; texture de carrosserie abîmée. Tout est dessiné par le code."""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, ".")
from signs_tex import F

N = 2048
OUT = "tex"
rng = np.random.default_rng(66)


def spray_text(text, font, size, color, w, h, drips=True, slant=0.0):
    """Texte peint à la bombe : bords diffus, surpulvérisation, coulures."""
    size = int(size * 0.7)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    lines = text.split("\n")
    f = ImageFont.truetype(F[font], size)
    widest = max(d.textlength(ln, font=f) for ln in lines)
    if widest > w * 0.88:
        size = int(size * w * 0.88 / widest)
        f = ImageFont.truetype(F[font], size)
    lh = int(size * 1.08)
    y = (h - lh * len(lines)) // 2
    for ln in lines:
        tw = d.textlength(ln, font=f)
        x = (w - tw) / 2
        # tracé irrégulier : lettre par lettre avec un léger décalage
        for ch in ln:
            dy = rng.normal(0, size * 0.03)
            d.text((x, y + dy), ch, font=f, fill=255)
            x += d.textlength(ch, font=f) * rng.uniform(0.96, 1.06)
        y += lh
    a = np.asarray(img, np.float32) / 255.0
    core = np.asarray(img.filter(ImageFilter.GaussianBlur(size * 0.02)), np.float32) / 255.0
    halo = np.asarray(img.filter(ImageFilter.GaussianBlur(size * 0.09)), np.float32) / 255.0
    alpha = np.clip(core * 1.1 + halo * 0.35, 0, 1)
    # grain de pulvérisation
    alpha *= np.clip(0.75 + 0.35 * rng.random(alpha.shape), 0, 1)
    if drips:
        ys, xs = np.nonzero(a > 0.5)
        for _ in range(int(len(text) * 1.5)):
            k = rng.integers(len(xs))
            x0, y0 = xs[k], ys[k]
            L = int(rng.uniform(0.2, 0.9) * size)
            wd = max(1, int(size * rng.uniform(0.015, 0.03)))
            for t in range(L):
                yy = y0 + t
                if yy >= h:
                    break
                fade = 1 - t / L
                alpha[yy, max(0, x0 - wd):x0 + wd] = np.maximum(alpha[yy, max(0, x0 - wd):x0 + wd], 0.8 * fade)
    if slant:
        im = Image.fromarray((alpha * 255).astype(np.uint8)).rotate(slant, resample=Image.BICUBIC)
        alpha = np.asarray(im, np.float32) / 255.0
    rgb = np.ones((h, w, 3), np.float32) * np.array(color, np.float32) / 255.0
    return rgb, alpha


def splat(w, h, seed, color=(92, 8, 6), drag=False, pool=False):
    """Trace de sang : tache principale, gouttes projetées, ou traînée."""
    r = np.random.default_rng(seed)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    cx, cy = w / 2, h / 2
    if drag:
        x = w * 0.1
        y = h / 2
        while x < w * 0.92:
            rad = h * r.uniform(0.12, 0.22) * (1 - 0.5 * x / w)
            d.ellipse((x - rad, y - rad * 0.6, x + rad, y + rad * 0.6), fill=int(255 * r.uniform(0.6, 0.9)))
            x += rad * 0.15
            y += r.normal(0, h * 0.01)
        for k in range(4):
            yy = h / 2 + (k - 1.5) * h * 0.08
            d.line((w * 0.15, yy, w * 0.9, yy + r.normal(0, 4)), fill=160, width=max(2, int(h * 0.02)))
    else:
        R = min(w, h) * (0.3 if pool else 0.2)
        pts = []
        for k in range(40):
            a = 2 * math.pi * k / 40
            rr = R * (1 + 0.35 * r.normal() * (0.3 if pool else 1))
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d.polygon(pts, fill=255)
        for k in range(0 if pool else 60):
            a = r.uniform(0, 2 * math.pi)
            dist = R * r.uniform(1.0, 2.3)
            rad = R * r.uniform(0.02, 0.1) * (2.3 - dist / R)
            x, y = cx + dist * math.cos(a), cy + dist * math.sin(a)
            d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=255)
            if r.random() < 0.3:
                d.line((cx + R * 0.8 * math.cos(a), cy + R * 0.8 * math.sin(a), x, y), fill=255, width=max(1, int(rad * 0.6)))
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(4.0 if drag else 1.2)), np.float32) / 255.0
    dens = 0.55 + 0.45 * np.asarray(Image.fromarray((r.random((h // 8 + 1, w // 8 + 1)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255.0
    rgb = np.ones((h, w, 3), np.float32) * np.array(color, np.float32) / 255.0 * dens[..., None]
    return rgb, np.clip(a * 1.1, 0, 1)


def soot(w, h, seed):
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # traînée de suie montante (au-dessus d'une fenêtre incendiée)
    cx = w / 2 + (yy / h - 1) * r.normal(0, w * 0.05)
    width = w * (0.15 + 0.3 * (1 - yy / h))
    a = np.exp(-((xx - cx) / width) ** 2) * np.clip(yy / h * 1.4, 0, 1) ** 0.6
    noise = np.asarray(Image.fromarray((r.random((h // 16 + 1, w // 16 + 1)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255.0
    a = np.clip(a * (0.6 + 0.6 * noise), 0, 0.95)
    return np.ones((h, w, 3), np.float32) * 0.04, a


def bullets(w, h, seed):
    r = np.random.default_rng(seed)
    img = Image.new("L", (w, h), 0)
    col = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    dc = ImageDraw.Draw(col)
    for k in range(14):
        x, y = r.normal(w / 2, w * 0.2), r.normal(h / 2, h * 0.2)
        rad = r.uniform(4, 9)
        d.ellipse((x - rad * 2.2, y - rad * 2.2, x + rad * 2.2, y + rad * 2.2), fill=150)
        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=255)
        dc.ellipse((x - rad, y - rad, x + rad, y + rad), fill=255)
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(1)), np.float32) / 255.0
    dark = np.asarray(col, np.float32) / 255.0
    rgb = np.ones((h, w, 3), np.float32) * 0.75
    rgb = rgb * (1 - dark[..., None]) + 0.08 * dark[..., None]
    return rgb, a


def build():
    atlas = np.zeros((N, N, 4), np.float32)
    rects = {}
    # (clé, largeur, hauteur, fonction)
    RED, BLACK, WHITE_, GREEN, ORANGE = (170, 16, 14), (22, 22, 24), (236, 236, 230), (40, 150, 60), (230, 120, 20)
    items = [
        ("zone_infectee", 1000, 260, lambda w, h: spray_text("ZONE INFECTÉE", "cond", 150, RED, w, h)),
        ("ne_pas_entrer", 900, 240, lambda w, h: spray_text("NE PAS ENTRER", "cond", 140, BLACK, w, h)),
        ("ils_sont_dedans", 900, 340, lambda w, h: spray_text("ILS SONT\nDEDANS", "sans", 130, RED, w, h, slant=3)),
        ("survivants_mairie", 1000, 360, lambda w, h: spray_text("SURVIVANTS\n→ MAIRIE", "cond", 140, GREEN, w, h)),
        ("aidez_nous", 1000, 250, lambda w, h: spray_text("AIDEZ-NOUS", "sans", 160, WHITE_, w, h)),
        ("sos", 700, 330, lambda w, h: spray_text("SOS", "sans", 300, WHITE_, w, h, drips=False)),
        ("morts_ici", 700, 230, lambda w, h: spray_text("MORTS ICI", "cond", 130, BLACK, w, h, slant=-4)),
        ("pas_de_bruit", 800, 230, lambda w, h: spray_text("PAS DE BRUIT", "cond", 120, ORANGE, w, h)),
        ("croix", 320, 320, lambda w, h: spray_text("✕", "sans", 280, ORANGE, w, h)),
        ("fleche", 400, 240, lambda w, h: spray_text("→", "sans", 260, GREEN, w, h, drips=False)),
        ("vide_3", 420, 300, lambda w, h: spray_text("VIDE\n3 M", "cond", 110, ORANGE, w, h)),
        ("sang_1", 420, 420, lambda w, h: splat(w, h, 1)),
        ("sang_2", 420, 420, lambda w, h: splat(w, h, 2)),
        ("sang_flaque", 420, 420, lambda w, h: splat(w, h, 3, color=(70, 6, 5), pool=True)),
        ("sang_trainee", 840, 260, lambda w, h: splat(w, h, 4, drag=True)),
        ("sang_main", 300, 300, lambda w, h: splat(w, h, 5)),
        ("suie", 420, 520, lambda w, h: soot(w, h, 6)),
        ("impacts", 420, 420, lambda w, h: bullets(w, h, 7)),
    ]
    x, y, rowh = 8, 8, 0
    S = 0.7
    items = [(k, int(w * S), int(h * S), (lambda f: (lambda w, h: f(w, h)))(fn)) for k, w, h, fn in items]
    for key, w, h, fn in items:
        if x + w > N - 8:
            x, y = 8, y + rowh + 12
            rowh = 0
        if y + h > N - 8:
            raise RuntimeError("atlas des graffitis plein")
        rgb, a = fn(w, h)
        if rgb.shape[:2] != (h, w):
            raise RuntimeError(key)
        atlas[y:y + h, x:x + w, :3] = rgb
        atlas[y:y + h, x:x + w, 3] = a
        rects[key] = [x / N, y / N, (x + w) / N, (y + h) / N, w / h]
        x += w + 12
        rowh = max(rowh, h)
    # couleur sous les zones transparentes : dilatée pour éviter les liserés au filtrage
    img = Image.fromarray((np.clip(atlas, 0, 1) * 255).astype(np.uint8), "RGBA")
    os.makedirs(OUT, exist_ok=True)
    img.save(f"{OUT}/Graffitis_BC.png")
    Image.fromarray(np.full((N // 4, N // 4, 3), (128, 128, 255), np.uint8)).save(f"{OUT}/Graffitis_N.png")
    Image.fromarray(np.dstack([np.full((N // 4, N // 4), 255, np.uint8), np.full((N // 4, N // 4), 200, np.uint8), np.zeros((N // 4, N // 4), np.uint8)])).save(f"{OUT}/Graffitis_ORM.png")
    json.dump(rects, open(f"{OUT}/Graffitis.json", "w"), indent=1)
    prev = Image.new("RGB", img.size, (150, 140, 120))
    prev.paste(img, mask=img.split()[3])
    prev.thumbnail((1024, 1024))
    prev.save("texprev/Graffitis.jpg", quality=88)
    print("graffitis :", len(rects), "motifs")


if __name__ == "__main__":
    os.makedirs("texprev", exist_ok=True)
    build()
