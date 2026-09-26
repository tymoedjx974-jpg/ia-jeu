"""Atlas des enseignes, plaques de rue, panneaux, horloge et drapeaux (texte généré)."""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = "/usr/share/fonts/truetype"
F = {
    "serifb": f"{FONT}/dejavu/DejaVuSerif-Bold.ttf",
    "serif": f"{FONT}/liberation/LiberationSerif-Bold.ttf",
    "serifi": f"{FONT}/liberation/LiberationSerif-BoldItalic.ttf",
    "sans": f"{FONT}/dejavu/DejaVuSans-Bold.ttf",
    "sansr": f"{FONT}/liberation/LiberationSans-Regular.ttf",
    "cond": f"{FONT}/liberation/LiberationSans-Bold.ttf",
}
VILLAGE = "ROUSSILLON"

SHOPS = {
    # clé : (texte, style)
    "boulangerie": ("BOULANGERIE", "board_cream"),
    "patisserie": ("PÂTISSERIE", "board_rose"),
    "coiffure": ("COIFFURE", "board_blue"),
    "beaute": ("INSTITUT DE BEAUTÉ", "board_rose"),
    "restaurant1": ("Restaurant Le Mistral", "board_green_gold"),
    "restaurant2": ("La Cigale", "board_bordeaux_gold"),
    "restaurant3": ("L'Olivier", "board_cream"),
    "restaurant4": ("La Tonnelle", "board_green_gold"),
    "restaurant5": ("Le Petit Four", "board_bordeaux_gold"),
    "restaurant6": ("La Calade", "board_blue"),
    "restaurant7": ("Les Ocres", "board_cream"),
    "restaurant8": ("Le Belvédère", "board_green_gold"),
    "pizzeria": ("PIZZERIA", "board_bordeaux_gold"),
    "cafe1": ("CAFÉ DE LA PLACE", "board_green_gold"),
    "cafe2": ("CAFÉ DU MIDI", "board_bordeaux_gold"),
    "bar": ("BAR - TABAC", "board_blue"),
    "epicerie": ("ÉPICERIE", "board_green_gold"),
    "pharmacie": ("PHARMACIE", "board_white_green"),
    "poste": ("POSTE", "board_yellow"),
    "galerie": ("GALERIE D'ART", "board_cream"),
    "atelier": ("ATELIER D'ARTISTE", "board_cream"),
    "hotel": ("HÔTEL DES OCRES", "board_bordeaux_gold"),
    "hotel2": ("HÔTEL", "board_green_gold"),
    "savons": ("SAVONS DE PROVENCE", "board_lavender"),
    "santons": ("SANTONS", "board_bordeaux_gold"),
    "cave": ("CAVE À VINS", "board_bordeaux_gold"),
    "glaces": ("GLACES", "board_rose"),
    "poterie": ("POTERIE", "board_cream"),
    "produits": ("PRODUITS DE PROVENCE", "board_lavender"),
    "tourisme": ("OFFICE DE TOURISME", "board_blue"),
    "mediatheque": ("MÉDIATHÈQUE", "board_cream"),
    "musee": ("MUSÉE", "board_cream"),
    "boutique": ("BOUTIQUE", "board_blue"),
    "boucherie": ("BOUCHERIE", "board_bordeaux_gold"),
    "vins": ("DOMAINE - DÉGUSTATION", "board_bordeaux_gold"),
    "chambres": ("CHAMBRES D'HÔTES", "board_green_gold"),
}
STREETS = ["Rue de l'Église", "Rue des Bourgades", "Rue de la Porte Heureuse", "Rue de la Fontaine", "Place de la Mairie",
           "Place du Four", "Place Pasquier", "Passage du Mistral", "Rue des Lauriers", "Rue du Puits", "Rue de l'Arcade",
           "Rue de la Bistourle", "Rue Richard Casteau", "Montée du Belvédère", "Avenue de la Burlière", "Avenue Dame Sirmonde",
           "Chemin de Loulette", "Impasse Élie Blanc", "Avenue Jean-Étienne Astier", "Chemin des Oliviers", "Route des Lavandes",
           "Sentier des Ocres"]
DIRECTIONS = [("Gordes", 9), ("Apt", 10), ("Goult", 6), ("St-Saturnin-lès-Apt", 8), ("Joucas", 5), ("Carpentras", 38), ("Avignon", 48), ("Lumières", 5)]

STYLES = {
    "board_cream": ((232, 222, 196), (60, 50, 40), "serif", (120, 90, 60)),
    "board_rose": ((226, 170, 170), (255, 250, 245), "serifi", (160, 90, 100)),
    "board_blue": ((64, 102, 140), (250, 245, 230), "serif", (230, 220, 190)),
    "board_green_gold": ((42, 76, 56), (222, 186, 96), "serif", (200, 170, 90)),
    "board_bordeaux_gold": ((96, 30, 36), (226, 192, 108), "serifi", (210, 170, 90)),
    "board_white_green": ((245, 245, 240), (20, 130, 70), "sans", (20, 130, 70)),
    "board_yellow": ((245, 205, 40), (30, 50, 110), "sans", (30, 50, 110)),
    "board_lavender": ((130, 110, 170), (250, 245, 235), "serifi", (240, 230, 250)),
}


def fit_font(draw, text, font_path, box_w, box_h):
    size = int(box_h)
    while size > 6:
        f = ImageFont.truetype(font_path, size)
        l, t, r, b = draw.textbbox((0, 0), text, font=f)
        if r - l <= box_w and b - t <= box_h:
            return f, (r - l, b - t, l, t)
        size -= 2
    f = ImageFont.truetype(font_path, 6)
    l, t, r, b = draw.textbbox((0, 0), text, font=f)
    return f, (r - l, b - t, l, t)


def centered(draw, rect, text, font_path, color, fill_ratio=0.62, width_ratio=0.88):
    x0, y0, x1, y1 = rect
    f, (w, h, l, t) = fit_font(draw, text, font_path, (x1 - x0) * width_ratio, (y1 - y0) * fill_ratio)
    draw.text(((x0 + x1) / 2 - w / 2 - l, (y0 + y1) / 2 - h / 2 - t), text, font=f, fill=color)


class Packer:
    def __init__(self, size):
        self.size, self.x, self.y, self.row_h = size, 0, 0, 0
        self.img = Image.new("RGBA", (size, size), (128, 128, 128, 255))
        self.d = ImageDraw.Draw(self.img)
        self.rects = {}

    def alloc(self, name, w, h):
        if self.x + w > self.size:
            self.x, self.y, self.row_h = 0, self.y + self.row_h + 4, 0
        assert self.y + h <= self.size, "atlas plein"
        r = (self.x, self.y, self.x + w, self.y + h)
        self.x += w + 4
        self.row_h = max(self.row_h, h)
        S = self.size
        # UV (0,0) en haut à gauche, comme dans Unreal
        self.rects[name] = [r[0] / S, r[1] / S, r[2] / S, r[3] / S]
        return r


def board(p, name, text, style):
    bg, fg, font, border = STYLES[style]
    w, h = 800, 160
    r = p.alloc(name, w, h)
    x0, y0, x1, y1 = r
    p.d.rectangle(r, fill=bg)
    p.d.rectangle((x0 + 10, y0 + 10, x1 - 10, y1 - 10), outline=border, width=6)
    centered(p.d, (x0 + 20, y0 + 16, x1 - 20, y1 - 16), text, F[font], fg)


def build(out="tex"):
    os.makedirs(out, exist_ok=True)
    p = Packer(4096)
    for k, (txt, st) in SHOPS.items():
        board(p, "shop_" + k, txt, st)
    # Mairie (lettres gravées sur plaque de pierre)
    r = p.alloc("mairie", 1000, 190)
    p.d.rectangle(r, fill=(214, 202, 176))
    p.d.rectangle((r[0] + 8, r[1] + 8, r[2] - 8, r[3] - 8), outline=(170, 155, 125), width=5)
    centered(p.d, (r[0] + 20, r[1] + 20, r[2] - 20, r[3] - 20), "MAIRIE", F["serifb"], (70, 62, 50), 0.7)
    r = p.alloc("devise", 1600, 110)
    p.d.rectangle(r, fill=(214, 202, 176))
    centered(p.d, r, "LIBERTÉ · ÉGALITÉ · FRATERNITÉ", F["serifb"], (80, 70, 55), 0.6, 0.94)
    r = p.alloc("ecole", 900, 170)
    p.d.rectangle(r, fill=(214, 202, 176))
    centered(p.d, r, "ÉCOLE PUBLIQUE", F["serifb"], (80, 70, 55), 0.6)
    r = p.alloc("eglise", 1000, 170)
    p.d.rectangle(r, fill=(210, 198, 172))
    centered(p.d, r, "ÉGLISE SAINT-MICHEL", F["serifb"], (80, 70, 55), 0.55)
    # Plaques de rue émaillées bleues
    for i, s in enumerate(STREETS):
        r = p.alloc(f"rue_{i}", 640, 190)
        p.d.rounded_rectangle(r, radius=28, fill=(28, 58, 128))
        p.d.rounded_rectangle((r[0] + 14, r[1] + 14, r[2] - 14, r[3] - 14), radius=20, outline=(245, 245, 245), width=8)
        words = s.split(" ")
        if len(s) > 16 and len(words) > 2:
            cut = len(words) // 2 if words[0].lower() not in ("rue", "place", "chemin", "avenue", "route", "passage", "montée", "impasse", "sentier") else 1
            l1, l2 = " ".join(words[:cut]), " ".join(words[cut:])
            centered(p.d, (r[0] + 26, r[1] + 24, r[2] - 26, r[1] + 88), l1, F["sans"], (245, 245, 245), 0.7)
            centered(p.d, (r[0] + 26, r[1] + 82, r[2] - 26, r[3] - 24), l2, F["sans"], (245, 245, 245), 0.75)
        else:
            centered(p.d, (r[0] + 30, r[1] + 30, r[2] - 30, r[3] - 30), s, F["sans"], (245, 245, 245), 0.55)
    # Panneau d'entrée d'agglomération
    r = p.alloc("entree", 800, 280)
    p.d.rectangle(r, fill=(250, 250, 250))
    p.d.rectangle((r[0] + 16, r[1] + 16, r[2] - 16, r[3] - 16), outline=(200, 30, 40), width=28)
    centered(p.d, (r[0] + 60, r[1] + 60, r[2] - 60, r[3] - 60), VILLAGE, F["cond"], (20, 20, 20), 0.6)
    r = p.alloc("sortie", 800, 280)
    p.d.rectangle(r, fill=(250, 250, 250))
    p.d.rectangle((r[0] + 16, r[1] + 16, r[2] - 16, r[3] - 16), outline=(200, 30, 40), width=28)
    centered(p.d, (r[0] + 60, r[1] + 60, r[2] - 60, r[3] - 60), VILLAGE, F["cond"], (20, 20, 20), 0.6)
    p.d.line((r[0] + 40, r[3] - 40, r[2] - 40, r[1] + 40), fill=(200, 30, 40), width=34)
    # Panneaux directionnels (flèches blanches)
    for i, (town, km) in enumerate(DIRECTIONS):
        r = p.alloc(f"dir_{i}", 1000, 170)
        x0, y0, x1, y1 = r
        p.d.rectangle(r, fill=(0, 0, 0, 0))
        p.d.polygon([(x0, y0), (x1 - 110, y0), (x1, (y0 + y1) / 2), (x1 - 110, y1), (x0, y1)], fill=(248, 248, 248))
        p.d.polygon([(x0 + 10, y0 + 10), (x1 - 116, y0 + 10), (x1 - 12, (y0 + y1) / 2), (x1 - 116, y1 - 10), (x0 + 10, y1 - 10)], outline=(30, 30, 30), width=6)
        centered(p.d, (x0 + 26, y0 + 16, x1 - 270, y1 - 16), town, F["cond"], (25, 25, 25), 0.6)
        centered(p.d, (x1 - 270, y0 + 16, x1 - 110, y1 - 16), f"{km}", F["cond"], (25, 25, 25), 0.6)
    # Horloge
    r = p.alloc("horloge", 600, 600)
    x0, y0, x1, y1 = r
    cx, cy, R = (x0 + x1) / 2, (y0 + y1) / 2, 290
    p.d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(30, 30, 30))
    p.d.ellipse((cx - R + 18, cy - R + 18, cx + R - 18, cy + R - 18), fill=(242, 238, 225))
    romans = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    fnt = ImageFont.truetype(F["serifb"], 50)
    for i, rn in enumerate(romans):
        a = i / 12 * 2 * math.pi
        tx, ty = cx + math.sin(a) * (R - 70), cy - math.cos(a) * (R - 70)
        l, t, rr, b = p.d.textbbox((0, 0), rn, font=fnt)
        p.d.text((tx - (rr - l) / 2 - l, ty - (b - t) / 2 - t), rn, font=fnt, fill=(25, 25, 25))
    for i in range(60):
        a = i / 60 * 2 * math.pi
        r1 = R - 30 if i % 5 else R - 44
        p.d.line((cx + math.sin(a) * r1, cy - math.cos(a) * r1, cx + math.sin(a) * (R - 22), cy - math.cos(a) * (R - 22)), fill=(25, 25, 25), width=4 if i % 5 == 0 else 2)
    for a, L, w in ((math.radians(300), R * 0.5, 16), (math.radians(60), R * 0.72, 10)):
        p.d.line((cx, cy, cx + math.sin(a) * L, cy - math.cos(a) * L), fill=(20, 20, 20), width=w)
    p.d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(20, 20, 20))
    # Croix de pharmacie
    r = p.alloc("croix", 300, 300)
    x0, y0, x1, y1 = r
    p.d.rectangle(r, fill=(0, 0, 0, 0))
    c = (40, 190, 90)
    t = 100
    p.d.rectangle((x0 + t, y0, x1 - t, y1), fill=c)
    p.d.rectangle((x0, y0 + t, x1, y1 - t), fill=c)
    # Carotte de tabac
    r = p.alloc("tabac", 240, 480)
    x0, y0, x1, y1 = r
    p.d.rectangle(r, fill=(0, 0, 0, 0))
    p.d.polygon([((x0 + x1) / 2, y0), (x1, (y0 + y1) / 2), ((x0 + x1) / 2, y1), (x0, (y0 + y1) / 2)], fill=(200, 30, 36))
    fnt = ImageFont.truetype(F["sans"], 56)
    for i, ch in enumerate("TABAC"):
        l, t_, rr, b = p.d.textbbox((0, 0), ch, font=fnt)
        p.d.text(((x0 + x1) / 2 - (rr - l) / 2 - l, y0 + 90 + i * 60), ch, font=fnt, fill=(250, 250, 250))
    # Ardoise de menu
    r = p.alloc("ardoise", 400, 560)
    x0, y0, x1, y1 = r
    p.d.rectangle(r, fill=(120, 90, 60))
    p.d.rectangle((x0 + 26, y0 + 26, x1 - 26, y1 - 26), fill=(40, 42, 40))
    fnt = ImageFont.truetype(F["serifi"], 56)
    lines = ["Menu du jour", "", "Tapenade", "Daube provençale", "Tian de légumes", "Tarte aux abricots", "", "18 €"]
    for i, ln in enumerate(lines):
        centered(p.d, (x0 + 34, y0 + 40 + i * 60, x1 - 34, y0 + 96 + i * 60), ln, F["serifi"], (235, 235, 225), 0.8) if ln else None
    # Drapeaux
    r = p.alloc("drapeau_fr", 480, 320)
    x0, y0, x1, y1 = r
    p.d.rectangle((x0, y0, x0 + 160, y1), fill=(0, 35, 149))
    p.d.rectangle((x0 + 160, y0, x0 + 320, y1), fill=(255, 255, 255))
    p.d.rectangle((x0 + 320, y0, x1, y1), fill=(237, 41, 57))
    r = p.alloc("drapeau_eu", 480, 320)
    x0, y0, x1, y1 = r
    p.d.rectangle(r, fill=(0, 51, 153))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for i in range(12):
        a = i / 12 * 2 * math.pi
        sx, sy = cx + math.sin(a) * 106, cy - math.cos(a) * 106
        pts = []
        for k in range(10):
            rr = 18 if k % 2 == 0 else 7
            aa = k / 10 * 2 * math.pi
            pts.append((sx + math.sin(aa) * rr, sy - math.cos(aa) * rr))
        p.d.polygon(pts, fill=(255, 204, 0))
    # Monument aux morts (inscription)
    r = p.alloc("monument", 700, 230)
    p.d.rectangle(r, fill=(205, 196, 176))
    centered(p.d, (r[0] + 20, r[1] + 16, r[2] - 20, r[1] + 115), "À NOS MORTS", F["serifb"], (60, 55, 45), 0.7)
    centered(p.d, (r[0] + 20, r[1] + 115, r[2] - 20, r[3] - 16), "1914 - 1918   1939 - 1945", F["serifb"], (60, 55, 45), 0.55)
    img = p.img
    img.save(f"{out}/Enseignes_BC.png")
    Image.new("RGB", img.size, (128, 128, 255)).save(f"{out}/Enseignes_N.png")
    Image.new("RGB", img.size, (255, 150, 0)).save(f"{out}/Enseignes_ORM.png")
    with open(f"{out}/Enseignes.json", "w", encoding="utf-8") as f:
        json.dump(p.rects, f, ensure_ascii=False, indent=0)
    img.convert("RGB").resize((1024, 1024)).save("texprev/Enseignes.jpg", quality=88)
    print(len(p.rects), "entrées")


if __name__ == "__main__":
    build()
