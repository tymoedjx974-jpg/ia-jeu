"""Export vers le plugin Unreal VillageProvence : textures, maillages binaires (.pvm), terrain, instances, manifeste JSON.

Repère Unreal : X = est, Y = sud (Y local inversé), Z = haut, en centimètres. L'ordre des indices est conservé :
la symétrie Y transforme l'ordre direct (repère droit) en ordre horaire, convention des faces avant d'Unreal.
"""
import sys, os, json, math, pickle, struct, zlib, time, shutil, collections
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from common import ZONE, RES, NX, NY
from materials import WIND, MATS, TILE, TERRAIN_LAYERS

T0 = time.time()
OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/ia-jeu/Plugins/VillageProvence/Data"
os.makedirs(OUT, exist_ok=True)
for sub in ("Textures", "Meshes", "Terrain", "Sons"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
CELL = 256.0  # regroupement des maillages de bâti / voirie
ICELL = 1024.0  # regroupement des instances par acteur


def to_ue_points(P):
    P = np.asarray(P, np.float64)
    return np.column_stack([P[:, 0] * 100.0, -P[:, 1] * 100.0, P[:, 2] * 100.0])


def to_ue_normals(N):
    N = np.asarray(N, np.float64)
    return np.column_stack([N[:, 0], -N[:, 1], N[:, 2]])


def write_pvm(path, lods, pivot_local=(0.0, 0.0, 0.0)):
    """lods : liste de dictionnaires {matériau: {P,N,UV,C,I}} (repère local, mètres)."""
    piv = to_ue_points(np.array([pivot_local]))[0]
    buf = bytearray()
    buf += struct.pack("<I", len(lods))
    tris = 0
    for arrays in lods:
        mats = sorted(k for k, v in arrays.items() if len(v["I"]))
        buf += struct.pack("<I", len(mats))
        for m in mats:
            d = arrays[m]
            P = to_ue_points(d["P"]) - piv
            N = to_ue_normals(d["N"])
            UV = np.asarray(d["UV"], np.float32).reshape(len(P), -1)
            nuv = UV.shape[1] // 2
            # recentre les UV (entiers) : la texture se répète, cela ne change rien mais garde la précision
            for k in range(nuv):
                if m not in ("Enseignes", "Graffitis") and not m.startswith("Feuilles") and m not in ("AiguillesPin", "Lavande", "HerbeSeche", "HerbeVerte", "Fleurs", "Glycine", "Horizon", "Genoise"):
                    off = np.floor(UV[:, 2 * k:2 * k + 2].mean(axis=0))
                    UV[:, 2 * k:2 * k + 2] -= off
            C = np.asarray(d["C"], np.uint8).reshape(-1, 4)
            I = np.asarray(d["I"], np.uint32).reshape(-1, 3)
            name = m.encode("utf-8")
            buf += struct.pack("<H", len(name)) + name
            buf += struct.pack("<IIB", len(P), len(I), nuv)
            buf += P.astype("<f4").tobytes()
            buf += np.clip(np.round(N * 32767), -32767, 32767).astype("<i2").tobytes()
            buf += UV.astype("<f4").tobytes()
            buf += C.tobytes()
            buf += I.astype("<u4").tobytes()
            tris += len(I)
    comp = zlib.compress(bytes(buf), 6)
    with open(path, "wb") as f:
        f.write(b"PVM2" + struct.pack("<II", len(buf), len(comp)) + comp)
    return tris, len(comp)


def merge_arrays(dst, src):
    for m, d in src.items():
        if not len(d["I"]):
            continue
        if m not in dst:
            dst[m] = dict(P=[], N=[], UV=[], C=[], I=[], n=0)
        e = dst[m]
        e["P"].append(d["P"]); e["N"].append(d["N"]); e["UV"].append(d["UV"]); e["C"].append(d["C"])
        e["I"].append(d["I"] + e["n"])
        e["n"] += len(d["P"])


def finish(acc):
    return {m: dict(P=np.concatenate(e["P"]), N=np.concatenate(e["N"]), UV=np.concatenate(e["UV"]), C=np.concatenate(e["C"]), I=np.concatenate(e["I"])) for m, e in acc.items()}


manifest = dict(version=2, units="cm", origin_lonlat=[5.2929, 43.9024], z0_m=ZONE["z0"], meshes=[], actors=[], textures=[], materials=[],
                instance_groups=[], terrain={}, ambiance={}, sounds=[], credits=[])
mesh_stats = collections.Counter()

# ------------------------------------------------------------------ 1. maillages de bâti, voirie, mobilier, monuments, horizon
B = pickle.load(open("buildings_out.pkl", "rb"))
R = pickle.load(open("roads_out.pkl", "rb"))
M = pickle.load(open("mobilier_out.pkl", "rb"))
G = np.load("terrain.npz")["ground"]

groups = collections.defaultdict(dict)
for src, cat in ((B["chunks"], "Bati"), (R, "Voirie"), (M["chunks"], "Mobilier")):
    for k, arr in src.items():
        if not arr:
            continue
        cx, cy = (k[0] + 0.5) * 128.0, (k[1] + 0.5) * 128.0
        ck = (int(math.floor(cx / CELL)), int(math.floor(cy / CELL)))
        merge_arrays(groups[(cat, ck)], arr)
for (cat, ck), acc in sorted(groups.items()):
    arr = finish(acc)
    allP = np.concatenate([d["P"] for d in arr.values()])
    piv = ((ck[0] + 0.5) * CELL, (ck[1] + 0.5) * CELL, float(allP[:, 2].min()))
    name = f"{cat}_{ck[0] + 20}_{ck[1] + 20}"
    tris, size = write_pvm(os.path.join(OUT, "Meshes", name + ".pvm"), [arr], piv)
    mesh_stats[cat] += tris
    manifest["meshes"].append(dict(name=name, file=f"Meshes/{name}.pvm", nanite=True, collision="complex", folder=cat))
    manifest["actors"].append(dict(mesh=name, loc=to_ue_points([piv])[0].round(1).tolist(), yaw=0.0, folder=f"VillageProvence/{cat}", always_loaded=True))
for key, (arr, c) in B["specials"].items():
    allP = np.concatenate([d["P"] for d in arr.values()])
    piv = (c[0], c[1], float(allP[:, 2].min()))
    name = key.split("_")[0]
    tris, size = write_pvm(os.path.join(OUT, "Meshes", name + ".pvm"), [arr], piv)
    mesh_stats["Monuments"] += tris
    manifest["meshes"].append(dict(name=name, file=f"Meshes/{name}.pvm", nanite=True, collision="complex", folder="Monuments"))
    manifest["actors"].append(dict(mesh=name, loc=to_ue_points([piv])[0].round(1).tolist(), yaw=0.0, folder="VillageProvence/Monuments", always_loaded=True))
far = pickle.load(open("far_out.pkl", "rb"))
tris, size = write_pvm(os.path.join(OUT, "Meshes", "Horizon.pvm"), [far], (0.0, 0.0, 0.0))
mesh_stats["Horizon"] += tris
manifest["meshes"].append(dict(name="Horizon", file="Meshes/Horizon.pvm", nanite=True, collision="none", folder="Terrain"))
manifest["actors"].append(dict(mesh="Horizon", loc=[0, 0, 0], yaw=0.0, folder="VillageProvence/Terrain", always_loaded=True))
print("bâti / voirie / mobilier :", dict(mesh_stats), "%.0fs" % (time.time() - T0), flush=True)

# ------------------------------------------------------------------ 2. éléments instanciés (modules d'architecture, végétation)
from modules import MODULE_BUILDERS
from modules_zombie import ZOMBIE_BUILDERS, ZOMBIE_COLLIDE
from mobilier_int import SIZE as FURN_SIZE
from trees import catalog

COLLIDE = {"Lampadaire": ("capsule", 0.12, 3.6), "Borne": ("capsule", 0.15, 0.7), "Banc": ("box", 1.7, 0.5, 0.9), "Banc_Pierre": ("box", 1.8, 0.45, 0.5),
           "Table_Cafe": ("capsule", 0.33, 0.75), "Parasol": ("capsule", 0.08, 2.5), "Balle_Foin": ("box", 1.3, 1.5, 1.5)}
# balcons praticables (parkour) : dalle + garde-corps
for _b in ("PorteFenetre_Balcon", "PorteFenetreV_Balcon"):
    COLLIDE[_b] = ("boxes", [0, -0.16, -0.05, 1.4, 0.52, 0.1, 0, -0.39, 0.5, 1.34, 0.06, 1.0])
# mobilier d'intérieur : boîte d'encombrement (rien pour les tapis et les suspensions)
for _k, (_w, _d, _h) in FURN_SIZE.items():
    if _h > 0.05:
        COLLIDE[_k] = ("box", _w, _d, _h)
COLLIDE.update(ZOMBIE_COLLIDE)
# vantaux mobiles des portes des maisons visitables
from modules import LEAVES, leaf_collision
for _k in LEAVES:
    COLLIDE[_k] = leaf_collision(_k)
TAGS = {k: ["TM_Echelle"] for k in ZOMBIE_BUILDERS if k.startswith("Z_Echelle")}
ALL_MODULES = dict(MODULE_BUILDERS)
ALL_MODULES.update(ZOMBIE_BUILDERS)


def collision_entry(col):
    """Collision au format du plugin ; les boîtes décentrées passent en repère Unreal (Y inversé)."""
    if not col:
        return "none", []
    if col[0] == "boxes":
        d = list(col[1])
        for k in range(0, len(d), 6):
            d[k + 1] = -d[k + 1]
        return "boxes", d
    return col[0], list(col[1:])


for name, fn in ALL_MODULES.items():
    arr = fn().arrays()
    tris, _ = write_pvm(os.path.join(OUT, "Meshes", f"Mod_{name}.pvm"), [arr])
    ctype, cdims = collision_entry(COLLIDE.get(name))
    folder = "Interieurs" if name.startswith("Int_") else ("Zombies" if name.startswith("Z_") else "Modules")
    manifest["meshes"].append(dict(name=f"Mod_{name}", file=f"Meshes/Mod_{name}.pvm", nanite=True, collision=ctype,
                                   collision_dims=cdims, folder=folder, tintable=True, tags=TAGS.get(name, [])))
C = catalog()
VEG_CULL = {"Rocher_Eboulis": 15000, "Herbe": 9000, "Lavande_": 25000, "Buisson_Romarin": 18000, "Buisson_Garrigue": 30000, "Vigne_Rang": 40000, "Lavande_Rang": 50000, "Balle": 60000}
for name, fn in C.items():
    lods = []
    for lod in range(3):
        mb, h, r = fn(lod)
        lods.append(mb.arrays())
    tris, _ = write_pvm(os.path.join(OUT, "Meshes", f"Veg_{name}.pvm"), lods)
    trunk = None
    if name.startswith("Arbre_"):
        trunk = ("capsule", 0.35 if "Platane" in name or "Pin" in name else 0.25, min(h, 6.0))
    elif name.startswith("Balle"):
        trunk = COLLIDE["Balle_Foin"]
    elif name.startswith("Rocher_Bloc") or name.startswith("Rocher_Dalle"):
        trunk = ("complex",)
    cull = next((v for k, v in VEG_CULL.items() if name.startswith(k)), 0)
    manifest["meshes"].append(dict(name=f"Veg_{name}", file=f"Meshes/Veg_{name}.pvm", nanite=False, collision=trunk[0] if trunk else "none",
                                   collision_dims=list(trunk[1:]) if trunk else [], folder="Vegetation", lods=3, lod_screen_sizes=[1.0, 0.25, 0.06],
                                   cull_distance=cull, wind=not name.startswith("Rocher")))
print("modules + végétation exportés %.0fs" % (time.time() - T0), flush=True)

# ------------------------------------------------------------------ 3. instances
N = pickle.load(open("nature_out.pkl", "rb"))
Z = pickle.load(open("envahi_out.pkl", "rb"))
all_inst = {}
for src, prefix in ((B["inst"], "Mod_"), (M["inst"], "Mod_"), (Z["inst"], "Mod_"), (N, "Veg_")):
    for k, a in src.items():
        if len(a):
            all_inst.setdefault(prefix + k, []).append(np.asarray(a, np.float32))
buf = bytearray()
ngroups = 0
count = 0
for asset, lst in sorted(all_inst.items()):
    a = np.concatenate(lst)
    col = np.round(a[:, 7:10]).astype(np.int32)
    cells = np.floor(a[:, 0] / ICELL).astype(np.int32) * 1000 + np.floor(a[:, 1] / ICELL).astype(np.int32)
    key = cells.astype(np.int64) * (1 << 24) + col[:, 0] * 65536 + col[:, 1] * 256 + col[:, 2]
    for kv in np.unique(key):
        m = key == kv
        g = a[m]
        cell = int(cells[m][0])
        cxi = int(np.floor(g[0, 0] / ICELL))
        cyi = int(np.floor(g[0, 1] / ICELL))
        rgb = [int(v) for v in col[m][0]]
        P = to_ue_points(g[:, 0:3])
        yaw = -np.degrees(g[:, 3])
        pos = np.round(P).astype("<i4")
        yq = np.round((yaw % 360.0) / 360.0 * 65535).astype("<u2")
        sc = np.round(np.clip(g[:, 4:7], 0.0, 60.0) * 1000).astype("<u2")
        nm = asset.encode("utf-8")
        buf += struct.pack("<H", len(nm)) + nm + struct.pack("<BBBhhI", *rgb, cxi, cyi, len(g))
        buf += pos.tobytes() + yq.tobytes() + sc.tobytes()
        manifest["instance_groups"].append(dict(mesh=asset, color=rgb, cell=[cxi, cyi], count=int(len(g))))
        ngroups += 1
        count += len(g)
comp = zlib.compress(bytes(buf), 6)
with open(os.path.join(OUT, "Instances.pvi"), "wb") as f:
    f.write(b"PVI2" + struct.pack("<III", len(buf), len(comp), ngroups) + comp)
print("instances :", count, "en", ngroups, "groupes, %.1f Mo" % (len(comp) / 1e6), flush=True)

# ------------------------------------------------------------------ 4. terrain (hauteurs 16 bits + 8 couches)
T = np.load("terrain.npz")
g = T["ground"].astype(np.float64)
sp = T["splat"]
zmin, zmax = float(g.min()) - 1.0, float(g.max()) + 1.0
q = np.round((g - zmin) / (zmax - zmin) * 65535).astype("<u2")
hb = zlib.compress(q.tobytes(), 6)
with open(os.path.join(OUT, "Terrain", "Hauteurs.pvh"), "wb") as f:
    f.write(b"PVH1" + struct.pack("<IIffffII", NX, NY, ZONE["xmin"], ZONE["ymin"], RES, 0.0, len(q.tobytes()), len(hb)) + struct.pack("<ff", zmin, zmax) + hb)
sb = zlib.compress(np.ascontiguousarray(sp).tobytes(), 6)
with open(os.path.join(OUT, "Terrain", "Couches.pvs"), "wb") as f:
    f.write(b"PVS1" + struct.pack("<IIII", NX, NY, sp.shape[2], len(sb)) + sb)
manifest["terrain"] = dict(heights="Terrain/Hauteurs.pvh", layers="Terrain/Couches.pvs", tile_quads=125, uv_tile_m=TILE["Terrain"],
                           layer_names=TERRAIN_LAYERS, material="Terrain", skirt_m=12.0)
print("terrain : %.1f + %.1f Mo" % (len(hb) / 1e6, len(sb) / 1e6), flush=True)

# ------------------------------------------------------------------ 5. textures
used_tex = set()
for m, spec in MATS.items():
    if spec.get("tex"):
        used_tex.add(spec["tex"])
used_tex |= set(TERRAIN_LAYERS)
from texlib import noise, to_u8
mac = noise(1024, 180, 31) * 0.6 + noise(1024, 40, 32) * 0.4
mac = (mac - mac.min()) / (mac.max() - mac.min())
Image.fromarray(to_u8(mac)).save("tex/Macro_BC.png")
used_tex.add("Macro")
tex_bytes = 0
for t in sorted(used_tex):
    for suf, srgb, kind in (("BC", True, "color"), ("N", False, "normal"), ("ORM", False, "masks")):
        src = f"tex/{t}_{suf}.png"
        if not os.path.exists(src):
            continue
        im = Image.open(src)
        has_alpha = im.mode == "RGBA" and np.asarray(im)[..., 3].min() < 250
        if t in ("Enseignes", "Graffitis") and suf != "BC":
            continue
        hero = t in ("PierreMoellons", "TuilesCanal", "Enduit", "Calade", "PierreTaille", "Dallage")
        maxs = {"BC": 2048 if (hero or t in TERRAIN_LAYERS) else 1024, "N": 2048 if hero else 1024, "ORM": 1024}[suf]
        if t in TERRAIN_LAYERS and suf == "BC":
            maxs = 1024
        if max(im.size) > maxs:
            im = im.resize((maxs, maxs), Image.LANCZOS)
        if has_alpha:
            dst = f"Textures/T_{t}_{suf}.png"
            im.save(os.path.join(OUT, dst), optimize=True)
        else:
            dst = f"Textures/T_{t}_{suf}.jpg"
            im.convert("RGB").save(os.path.join(OUT, dst), quality={"N": 86, "BC": 88, "ORM": 85}[suf], subsampling=0 if suf == "N" else 2)
        tex_bytes += os.path.getsize(os.path.join(OUT, dst))
        manifest["textures"].append(dict(name=f"T_{t}_{suf}", file=dst, srgb=srgb and kind == "color", kind=kind, alpha=bool(has_alpha)))
print("textures : %.1f Mo" % (tex_bytes / 1e6), flush=True)

# ------------------------------------------------------------------ 6. matériaux
MASTER = {"opaque": "Base", "masked": "Enseigne", "foliage": "Feuillage", "glass": "Couleur", "flat": "Couleur", "water": "Eau",
          "terrain": "Terrain", "emissive": "Lanterne"}
texnames = {t["name"] for t in manifest["textures"]}
for m, spec in MATS.items():
    kind = spec["kind"]
    e = dict(name=m, master=spec.get("master", MASTER[kind]), params=dict(WIND.get(m, {})), tile_m=float(TILE.get(m, 1.0)))
    if spec.get("tex"):
        t = spec["tex"]
        for suf in ("BC", "N", "ORM"):
            if f"T_{t}_{suf}" in texnames:
                e[suf] = f"T_{t}_{suf}"
    if "color" in spec:
        e["params"]["Couleur"] = list(spec["color"]) + [1.0]
    if "rough" in spec:
        e["params"]["Rugosite"] = spec["rough"]
    if "metallic" in spec:
        e["params"]["Metal"] = spec["metallic"]
    if "rough_scale" in spec:
        e["params"]["EchelleRugosite"] = spec["rough_scale"]
    if "base_tint" in spec:
        e["params"]["Teinte"] = list(spec["base_tint"]) + [1.0]
    if kind == "emissive":
        e["params"]["Emission"] = 0.0
    if kind == "terrain":
        e["layers"] = [dict(BC=f"T_{l}_BC", N=f"T_{l}_N", ORM=f"T_{l}_ORM") for l in TERRAIN_LAYERS]
        e["macro"] = "T_Macro_BC"
    manifest["materials"].append(e)

# ------------------------------------------------------------------ 7. ambiance, sons, départ du joueur
from common import grid_sample
zp = float(grid_sample(G, [-4.0], [12.0])[0]) + 1.0
manifest["ambiance"] = dict(sun_elevation=34.0, sun_azimuth=235.0, sun_lux=10.0, sun_temperature=5600.0, fog_density=0.006, fog_falloff=0.08,
                            volumetric_fog=True, exposure_bias=0.0, saturation=1.06, white_temp=6150.0, bloom=0.55,
                            player_start=to_ue_points([(-4.0, 12.0, zp)])[0].round(1).tolist())
# sons : fontaines (spatialisés), cigales (ambiance générale + quelques foyers dans les arbres autour du village)
fountains = [to_ue_points([(x, y, z + 1.0)])[0].round(1).tolist() for n, x, y, z in M.get("places", []) if n == "fontaine"]
trees = [a for k, a in N.items() if k.startswith("Arbre_")]
tp = np.concatenate(trees)[:, :3]
d = np.hypot(tp[:, 0] + 10, tp[:, 1])
cand = tp[(d > 120) & (d < 450)]
rng_s = np.random.default_rng(5)
pick_ = cand[rng_s.choice(len(cand), size=min(10, len(cand)), replace=False)] if len(cand) else np.zeros((0, 3))
cicadas = [to_ue_points([(x, y, z + 4.0)])[0].round(1).tolist() for x, y, z in pick_]
manifest["sounds"] = [
    dict(name="S_Cigales", file="Sons/Cigales.wav", volume=0.35, spatial=False, locations=[to_ue_points([(-10.0, 0.0, 40.0)])[0].round(1).tolist()]),
    dict(name="S_Cigales", file="Sons/Cigales.wav", volume=0.9, spatial=True, radius_cm=6000.0, locations=cicadas),
    dict(name="S_Fontaine", file="Sons/Fontaine.wav", volume=0.7, spatial=True, radius_cm=1800.0, locations=fountains),
    # joués par le jeu (UVPVegetationSubsystem) : souffle du vent, froissements au passage dans la végétation
    dict(name="S_Vent", file="Sons/Vent.wav", volume=1.0, spatial=False, loop=True, locations=[]),
] + [dict(name=f"S_Froissement_{k}", file=f"Sons/Froissement_{k}.wav", volume=1.0, spatial=False, loop=False, locations=[]) for k in range(4)] + [
    dict(name=f"S_Porte_{k}", file=f"Sons/Porte_{k}.wav", volume=1.0, spatial=False, loop=False, locations=[]) for k in ("Ouverture", "Fermeture")]
manifest["credits"] = ["Données cartographiques : © contributeurs OpenStreetMap (ODbL), via Overture Maps Foundation",
                       "Relief : Copernicus DEM GLO-30 © DLR e.V. 2010-2014 et © Airbus Defence and Space GmbH 2014-2018, fourni dans le cadre du programme Copernicus",
                       "Lieux : Overture Maps Foundation (CDLA Permissive 2.0)",
                       "Textures, modèles et sons : générés procéduralement pour ce projet"]
# village envahi : points d'apparition des zombies, maisons visitables, parcours de parkour
manifest["zombie_spawns"] = to_ue_points(np.array(Z["spawns"], np.float64)).round(1).tolist()
# portes mobiles (acteurs AVPPorte) : charnière, orientation, vantail, sens d'ouverture (vers l'intérieur)
manifest["doors"] = []
_rng_doors = np.random.default_rng(77)
for dr in B.get("doors", []):
    loc = to_ue_points([(dr["x"], dr["y"], dr["z"])])[0].round(1).tolist()
    ouverte = dr.get("theme") in ("saccagee",) or (dr.get("theme") not in ("refuge", "bourgeoise") and _rng_doors.random() < 0.15)
    manifest["doors"].append(dict(loc=loc, yaw=round(float(-np.degrees(dr["yaw"])), 2), mesh=f"Mod_{dr['leaf']}", scale=round(dr["sx"], 3),
                                  open_angle=-100.0 * dr.get("open_sign", 1), color=dr["color"], open=bool(ouverte), house=dr["house"]))
manifest["visitable_houses"] = [dict(id=v["id"], loc=to_ue_points([(v["x"], v["y"], v["z"])])[0].round(1).tolist(), style=v["style"],
                                     theme=(v.get("plan") or {}).get("theme", ""))
                                for v in B.get("visit", [])]
manifest["parkour"] = [dict(kind=r["kind"], loc=to_ue_points([(r["x"], r["y"], r.get("z", 0.0))])[0].round(1).tolist()) for r in Z["route"]]
print("zombies : %d points d'apparition, %d maisons visitables (%d portes), %d éléments de parcours"
      % (len(manifest["zombie_spawns"]), len(manifest["visitable_houses"]), len(manifest["doors"]), len(manifest["parkour"])))
print("export terminé en %.0fs" % (time.time() - T0))
with open(os.path.join(OUT, "Village.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
