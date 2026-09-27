#!/usr/bin/env bash
# Régénère entièrement le village et les données du plugin Unreal (Linux ou WSL, Python 3.11).
set -e
cd "$(dirname "$0")"
python fetch_data.py                 # données réelles (Overture Maps + Copernicus)
python plan_terrain.py               # relief corrigé, parcelles, routes, couches du sol
python textures.py                   # textures PBR procédurales
# écorce d'olivier recomposée à partir d'une vraie photo (photos/olivier_tronc.jpg), à la place de la version procédurale
python photo_texture.py photos/olivier_tronc.jpg EcorceOlivier --taille 1.0 --resolution 1024 \
    --morceaux 2761 3312 2896 3600 --px-par-m 1400 --relief 0.0025 --rugosite 0.7 0.9 \
    --taches 0.6 --mousse 0.3 --albedo 0.52 --saturation 0.7
python foliage_tex.py                # atlas de feuillage
python signs_tex.py                  # enseignes, plaques de rue, panneaux
python zombie_tex.py                 # inscriptions à la bombe, traces de sang
python buildings.py                  # 1 949 bâtiments, dont 34 maisons visitables meublées
python roads.py                      # voirie, places en terrasse
python nature.py                     # végétation
python mobilier.py                   # piscines, fontaines, bancs, réverbères, panneaux
python farterrain.py                 # horizon (Luberon, mont Ventoux)
python envahi.py                     # village envahi : voitures, barricades, camp, parcours de toit en toit
python export_ue.py ../../Plugins/VillageProvence/Data
python sons.py ../../Plugins/VillageProvence/Data/Sons
# aperçus Blender (facultatif) : python render_views.py place eglise vue_generale
#                                 python interior_view.py buildings_out.pkl
