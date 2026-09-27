#!/usr/bin/env bash
# Régénère entièrement le village et les données du plugin Unreal (Linux ou WSL, Python 3.11).
set -e
cd "$(dirname "$0")"
python fetch_data.py                 # données réelles (Overture Maps + Copernicus)
python plan_terrain.py               # relief corrigé, parcelles, routes, couches du sol
python textures.py                   # textures PBR procédurales
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
