# Générateur du village provençal

Scripts Python qui produisent les données du plugin `Plugins/VillageProvence` à partir de données réelles :

- **Overture Maps** (OpenStreetMap, lieux) : bâtiments, routes, ruelles, parcelles de vigne, de lavande et d'oliviers, forêts, haies, piscines, commerces ;
- **Copernicus DEM GLO-30** : relief de la zone et de l'horizon (Luberon, mont Ventoux).

Tout le reste est généré : textures PBR, fenêtres et volets, arbres, enseignes, sons.

## Utilisation

Python 3.11 (Linux ou WSL sous Windows) :

```bash
pip install -r requirements.txt
./generer_tout.sh
```

Le script remplace le dossier `Plugins/VillageProvence/Data`. Ensuite, dans Unreal : **Tools > Village provençal > Construire le village provençal**.

## Que modifier ?

| Fichier | Contenu |
| --- | --- |
| `plan_terrain.py` | zone jouable (`ZONE` dans `common.py`), relief, falaises d'ocre, couches du sol |
| `buildings.py` | palettes des façades et des volets (`OCHRES`, `CREAMS`, `SHUTTERS`), étages, toits, commerces, mairie, église |
| `modules.py` | fenêtres, volets, portes, vitrines, balcons, lanternes, mobilier |
| `trees.py` | espèces d'arbres et de plantes |
| `nature.py` | densité et répartition de la végétation |
| `signs_tex.py` | textes des enseignes, nom du village sur les panneaux (`VILLAGE`) |
| `textures.py` | textures procédurales |
| `render_views.py` | aperçus Blender (Cycles) |


## Remplacer une texture par une photo réelle

`photo_texture.py` transforme une photo de matière (mur, toit, calade, bois, écorce, sol) en texture du village :

```
python photo_texture.py mur.jpg PierreMoellons --taille 2.0 --relief 0.02
python photo_texture.py enduit.jpg Enduit --taille 1.5 --relief 0.003 --teinte
python export_ue.py ../../Plugins/VillageProvence/Data
```

- **Préparation** : la photo est recadrée au carré, puis l'éclairage de la prise de vue est retiré, pour garder la couleur propre de la matière.
- **Raccord** : la texture est rendue raccordable sans couture : la photo reste intacte au centre, les bords sont fondus.
- **Cartes générées** : relief, normale, occlusion et rugosité, calculés à partir de la photo.
- **Échelle** : `--taille` est la largeur réelle photographiée, en mètres. Reporte-la dans `materials.TILE` si elle diffère.

Photographie de face, par temps couvert, sans ombre portée. Utilise uniquement des photos que tu as le droit d'utiliser : les tiennes, ou des photos sous licence CC0.
