"""Registre des matériaux, partagé par le générateur, l'aperçu Blender et l'export Unreal."""

# taille réelle (m) couverte par une répétition de texture : les UV des maillages sont en mètres / TILE
TILE = {
    "Enduit": 3.0, "PierreMoellons": 3.0, "PierreTaille": 3.0, "TuilesCanal": 2.0, "Genoise": 1.12,
    "Calade": 2.0, "Dallage": 3.0, "Asphalte": 4.0, "Gravier": 2.0, "BoisPeint": 1.0, "BoisBrut": 1.0,
    "Fer": 1.0, "Bronze": 1.0, "TerreCuite": 1.0, "Toile": 1.0, "Eau": 2.0, "Verre": 1.0,
    "EcorcePlatane": 1.0, "EcorceOlivier": 1.0, "EcorcePin": 1.0, "EcorceChene": 1.0,
    "Terrain": 4.0, "Paille": 1.0, "Piscine": 2.0, "EauPiscine": 2.0,
    "Rocher": 2.0, "BoisVernis": 1.0, "Parquet": 1.2, "CarreauxCiment": 0.8, "Tomettes": 1.12, "Faience": 1.0, "TissuProvence": 0.5, "Carrosserie": 1.0, "Brique": 1.0,
}

# kind : opaque | masked | foliage | glass | water | terrain | emissive
MATS = {
    "Enduit": dict(kind="opaque", tex="Enduit"),
    "PierreMoellons": dict(kind="opaque", tex="PierreMoellons"),
    "PierreTaille": dict(kind="opaque", tex="PierreTaille"),
    "TuilesCanal": dict(kind="opaque", tex="TuilesCanal"),
    "Genoise": dict(kind="opaque", tex="Genoise"),
    "Calade": dict(kind="opaque", tex="Calade"),
    "Dallage": dict(kind="opaque", tex="Dallage"),
    "Asphalte": dict(kind="opaque", tex="Asphalte"),
    "Gravier": dict(kind="opaque", tex="Gravier"),
    "BoisPeint": dict(kind="opaque", tex="BoisPeint"),
    "BoisBrut": dict(kind="opaque", tex="BoisBrut"),
    "Fer": dict(kind="opaque", tex="Fer"),
    "Bronze": dict(kind="opaque", tex="Fer", base_tint=(0.55, 0.40, 0.22), metallic=1.0, rough_scale=0.6),
    "TerreCuite": dict(kind="opaque", tex="TerreCuite"),
    "Toile": dict(kind="opaque", tex="Toile"),
    "Verre": dict(kind="glass", color=(0.035, 0.04, 0.045), rough=0.06),
    "Eau": dict(kind="water", tex="Eau", color=(0.05, 0.12, 0.13), rough=0.03),
    "Enseignes": dict(kind="masked", tex="Enseignes"),
    "Lanterne": dict(kind="emissive", color=(1.0, 0.78, 0.45), strength=0.0),
    "EcorcePlatane": dict(kind="opaque", tex="EcorcePlatane"),
    "EcorceOlivier": dict(kind="opaque", tex="EcorceOlivier"),
    "EcorcePin": dict(kind="opaque", tex="EcorcePin"),
    "EcorceChene": dict(kind="opaque", tex="EcorceChene"),
    "FeuillesOlivier": dict(kind="foliage", tex="FeuillesOlivier"),
    "FeuillesLaurier": dict(kind="foliage", tex="FeuillesLaurier"),
    "FeuillesPlatane": dict(kind="foliage", tex="FeuillesPlatane"),
    "FeuillesChene": dict(kind="foliage", tex="FeuillesChene"),
    "FeuillesFruitier": dict(kind="foliage", tex="FeuillesFruitier"),
    "FeuillesVigne": dict(kind="foliage", tex="FeuillesVigne"),
    "AiguillesPin": dict(kind="foliage", tex="AiguillesPin"),
    "FeuillesCypres": dict(kind="foliage", tex="FeuillesCypres"),
    "FeuillesGarrigue": dict(kind="foliage", tex="FeuillesGarrigue"),
    "Lavande": dict(kind="foliage", tex="Lavande"),
    "HerbeSeche": dict(kind="foliage", tex="HerbeSeche"),
    "HerbeVerte": dict(kind="foliage", tex="HerbeVerte"),
    "Fleurs": dict(kind="foliage", tex="Fleurs"),
    "Glycine": dict(kind="foliage", tex="Glycine"),
    "Marquage": dict(kind="flat", color=(0.78, 0.78, 0.76), rough=0.55),
    "Paille": dict(kind="opaque", tex="Chaume"),
    "Horizon": dict(kind="opaque", tex="Horizon"),
    "Piscine": dict(kind="flat", color=(0.55, 0.78, 0.82), rough=0.3),
    "EauPiscine": dict(kind="water", tex="Eau", color=(0.12, 0.42, 0.48), rough=0.02),
    "Terrain": dict(kind="terrain"),
    "Rocher": dict(kind="opaque", tex="Roche"),
    # intérieurs des maisons visitables
    "Tomettes": dict(kind="opaque", tex="Tomettes"),
    "Parquet": dict(kind="opaque", tex="Parquet"),
    "BoisVernis": dict(kind="opaque", tex="BoisVernis"),
    "CarreauxCiment": dict(kind="opaque", tex="CarreauxCiment"),
    "Brique": dict(kind="opaque", tex="Brique"),
    "Faience": dict(kind="opaque", tex="Faience"),
    "TissuProvence": dict(kind="opaque", tex="TissuProvence"),
    "Porcelaine": dict(kind="flat", color=(0.86, 0.85, 0.82), rough=0.12),
    "Miroir": dict(kind="flat", color=(0.9, 0.9, 0.9), rough=0.02, metallic=1.0),
    # village envahi : voitures abandonnées, inscriptions, sang
    "Carrosserie": dict(kind="opaque", tex="Carrosserie"),
    "Pneu": dict(kind="flat", color=(0.03, 0.03, 0.03), rough=0.85),
    "Plastique": dict(kind="flat", color=(0.12, 0.26, 0.16), rough=0.55),
    "Graffitis": dict(kind="masked", tex="Graffitis"),
}

TERRAIN_LAYERS = ["SolSec", "TerreLabouree", "Ocre", "Roche", "SolForet", "Herbe", "Chemin", "Chaume"]


def uv_scale(mat):
    return TILE.get(mat, 1.0)


# Vent et passage des personnages (paramètres des matériaux Unreal M_VP_Feuillage / M_VP_Ecorce) :
#   Souplesse   : 0 à 1, les plantes s'écartent quand un personnage passe
#   Ondulation  : cm, vagues du vent qui traversent herbes et lavande
#   Frisson     : cm, frémissement des feuilles
#   Flexibilite : flexion du tronc (même valeur pour l'écorce et le feuillage d'une espèce)
ARBRE = dict(Souplesse=0.25, Ondulation=0.0, Frisson=5.0, Flexibilite=1.0)
WIND = {
    "FeuillesOlivier": ARBRE, "FeuillesLaurier": ARBRE, "FeuillesPlatane": ARBRE, "FeuillesChene": ARBRE, "FeuillesFruitier": ARBRE,
    "AiguillesPin": dict(ARBRE, Frisson=3.0), "FeuillesCypres": dict(ARBRE, Frisson=2.5),
    "FeuillesVigne": dict(Souplesse=0.45, Ondulation=3.0, Frisson=4.0, Flexibilite=0.0),
    "FeuillesGarrigue": dict(Souplesse=0.55, Ondulation=4.0, Frisson=3.0, Flexibilite=0.0),
    "Lavande": dict(Souplesse=1.0, Ondulation=10.0, Frisson=2.0, Flexibilite=0.0),
    "HerbeSeche": dict(Souplesse=1.0, Ondulation=14.0, Frisson=2.0, Flexibilite=0.0),
    "HerbeVerte": dict(Souplesse=1.0, Ondulation=14.0, Frisson=2.0, Flexibilite=0.0),
    "Fleurs": dict(Souplesse=0.25, Ondulation=2.0, Frisson=3.0, Flexibilite=0.0),
    "Glycine": dict(Souplesse=0.0, Ondulation=0.0, Frisson=2.0, Flexibilite=0.0),
    "EcorcePlatane": dict(Flexibilite=1.0), "EcorceOlivier": dict(Flexibilite=1.0),
    "EcorcePin": dict(Flexibilite=1.0), "EcorceChene": dict(Flexibilite=1.0),
}
# l'écorce des arbres utilise le matériau maître qui plie au vent
for _m in ("EcorcePlatane", "EcorceOlivier", "EcorcePin", "EcorceChene"):
    MATS[_m]["master"] = "Ecorce"
