# Village provençal — plugin Unreal Engine 5

Un village provençal complet de **4 × 4 km**, construit sur le **plan réel de Roussillon (Vaucluse)** : les rues, les ruelles, les places et l'emplacement de chaque bâtiment viennent des cartes ouvertes (OpenStreetMap via Overture Maps), et le relief vient du modèle de terrain européen Copernicus.

![Place de la mairie](Docs/place.jpg)

| | |
| --- | --- |
| ![Église et monument aux morts](Docs/eglise.jpg) | ![Vue générale du village perché](Docs/vue_generale.jpg) |
| ![Champ de lavande](Docs/lavande.jpg) | ![Vignes au pied du village](Docs/vignes.jpg) |

*Aperçus calculés avec Blender Cycles à partir des mêmes données que le plugin. Dans Unreal, avec Lumen, le rendu sera différent.*

## Contenu

| | |
| --- | --- |
| **Bâtiments** | 1 949 bâtiments : maisons de village, mas, villas, remises, auvents. Chaque maison est générée avec ses fenêtres, volets provençaux (à écharpe en Z, persiennes, ouverts, fermés), génoise sous le toit, tuiles canal, cheminées, remises voûtées, balcons en fer forgé, jardinières et pots de fleurs. Environ 21 000 fenêtres et 2 200 portes. |
| **Monuments** | Église Saint-Michel avec clocher et cloche, beffroi avec horloge et campanile en fer forgé, mairie avec drapeaux, plaque « MAIRIE » et devise, monument aux morts, deux fontaines. |
| **Commerces** | Placés à l'emplacement des commerces réels (noms inventés) : cafés et restaurants avec terrasses et parasols, boulangerie, coiffeur, pharmacie avec croix verte, épicerie, bar-tabac avec sa carotte, galeries, savons de Provence, santons, cave à vins, hôtel, poste. |
| **Rues** | Calades de galets dans le vieux village, places dallées en terrasse avec murs de soutènement, routes goudronnées avec lignes blanches, chemins, escaliers, 47 plaques de rue émaillées aux vrais noms (rue de l'Église, rue des Bourgades…), panneaux d'entrée « ROUSSILLON », panneaux directionnels, 223 réverbères, lanternes murales, bancs. |
| **Nature** | Environ 900 000 plantes : pinèdes et chênes verts, garrigue, 167 000 segments de rangs de vigne, champs de lavande en rangs, oliveraies, vergers, haies de cyprès contre le mistral, allée de platanes à l'entrée du village, pins parasols, lauriers-roses, balles de foin sur les champs moissonnés, 269 piscines de mas. Le feuillage bouge avec le vent. |
| **Terrain** | Relief réel (village perché à 330 m, vallée à 180 m), falaises d'ocre du sentier des Ocres, 8 types de sol (garrigue sèche, terre labourée, ocre, roche, sous-bois, herbe, chemin, chaume). À l'horizon : le Luberon, les monts de Vaucluse et le **mont Ventoux**. |
| **Ambiance** | Soleil de fin d'après-midi, ciel et atmosphère physiques, nuages volumétriques, brume, Lumen. Sons en boucle : **chant des cigales** et **fontaines**. |

Tout est généré : aucune texture, aucun modèle ni aucun son n'a été copié d'Internet. Les textures (pierre, enduit à la chaux, tuiles canal, calade…) ont été calculées pour ce projet.

## 1. Installer le plugin

1. Copie le dossier `Plugins/VillageProvence` (avec son sous-dossier `Data`, 125 Mo) dans le dossier `Plugins` de ton projet, à côté de `TMMouvements`.
2. Ouvre le projet. Unreal propose de compiler le nouveau module : réponds **Oui**. Il faut Visual Studio 2022 avec « Développement Desktop en C++ », comme pour l'autre plugin.
3. Vérifie dans **Edit > Plugins** que « Village provençal (Roussillon) » est coché.

Version conseillée : Unreal Engine 5.3 ou plus récent. Nanite et Lumen doivent être actifs, ce qui est le réglage par défaut des projets UE5.

## 2. Construire le village

1. Crée un niveau vide : **File > New Level > Empty Open World**, ou **Empty Level** si ton jeu n'utilise pas World Partition.
2. Menu **Tools > Village provençal > Construire le village provençal**.
3. Attends la fin : une barre de progression s'affiche. Compte 10 à 30 minutes selon le PC, puis encore quelques minutes de compilation des shaders.
4. Enregistre le niveau (**Ctrl+S**). Les assets sont déjà enregistrés dans `Content/VillageProvence`.

Le plugin crée :

- `Content/VillageProvence/Textures`, `Materials` et `Meshes` : 112 textures, 7 matériaux maîtres avec leurs instances, les maillages Nanite du bâti, du terrain et de la voirie, les arbres avec 3 niveaux de détail.
- Dans le niveau, un dossier **VillageProvence** : Terrain, Bati, Voirie, Mobilier, Monuments, Vegetation, Details, Ambiance, Sons.

Les autres commandes du même menu :

- **Replacer le village (sans recréer les assets)** : place le village dans un autre niveau en réutilisant les assets, en quelques minutes.
- **Retirer le village du niveau** : supprime les acteurs du village. Les assets restent dans le Content Browser.

## 3. Jouer dans le village

- Un **Player Start** est placé sur la place de la mairie, devant la fontaine. Il n'est créé que si le niveau n'en a pas déjà un.
- Dans **World Settings**, choisis le **GameMode** de ton jeu pour jouer avec ton personnage.
- Le village est à l'échelle réelle (1 unité = 1 cm). Les toits, les murs et le terrain ont des collisions exactes : tu peux marcher dans les ruelles et **courir sur les toits** avec le plugin TMMouvements. Les troncs d'arbres, les réverbères et les bancs bloquent aussi le joueur. Les herbes, la lavande et la vigne se traversent.
- La lumière, le ciel, la brume et le Post Process ne sont ajoutés que s'ils manquent : ceux de ton niveau ne sont pas modifiés.

## Performances

La zone est grande et très détaillée. Si ton PC peine :

- Dans `VillageProvence/Vegetation`, cache ou supprime quelques acteurs `VP_Vegetation_x_y` éloignés : chacun couvre environ 1 km².
- Réduis les distances d'affichage des herbes et buissons : sélectionne un composant dans l'acteur, puis règle **Instance End Cull Distance**.
- Supprime les sons dans le dossier `Sons` si tu n'en veux pas.
- Tous les acteurs du village restent chargés en permanence : on voit ainsi le village perché depuis les champs de lavande, à 1,5 km. Si tu préfères que World Partition les décharge au loin, coche **Is Spatially Loaded** sur les acteurs du dossier `VillageProvence`, sauf `Terrain`. Le bâti et la voirie sont découpés en blocs de 256 m, la végétation par km².

## Personnaliser

- **Couleurs et matériaux** : tout se règle dans les instances de matériaux de `Content/VillageProvence/Materials` (`MI_Enduit`, `MI_TuilesCanal`, `MI_PierreMoellons`…). Les volets de chaque couleur ont leur instance dans `Materials/Teintes`.
- **Encore plus de réalisme** : remplace une texture par une texture Megascans ou Fab dans l'instance de matériau (BaseColor, Normal, ORM). Le paramètre `Tiling` règle la taille. La géométrie ne change pas.
- **Le jour et la nuit** : les lanternes ont un matériau `MI_Lanterne` avec un paramètre `Emission` (0 le jour ; essaie 20 la nuit).
- **Régénérer le village** : le générateur Python complet est dans `Tools/VillageProvence` (voir `generer_tout.sh`). Il récupère les données réelles, reconstruit tout, et peut produire des aperçus avec Blender. Tu peux y changer les couleurs des façades, la densité des arbres ou le nom du village.

## Si la compilation échoue

Ce plugin a été écrit sans éditeur Unreal sous la main : il n'a pas encore été compilé. Si Visual Studio ou Unreal affiche une erreur, copie le message et envoie-le-moi, je le corrigerai. Il en va de même pour une erreur pendant la construction : ouvre **Window > Output Log** et filtre sur `LogVillageProvence`.

## Crédits des données

- Plan des rues, bâtiments, parcelles : © contributeurs [OpenStreetMap](https://www.openstreetmap.org/copyright) (licence ODbL), via la fondation Overture Maps.
- Lieux (commerces) : Overture Maps Foundation (CDLA Permissive 2.0). Les noms affichés sur les enseignes sont inventés.
- Relief : Copernicus DEM GLO-30, © DLR e.V. 2010-2014 et © Airbus Defence and Space GmbH 2014-2018, fourni dans le cadre du programme Copernicus de l'Union européenne.
- Textures, modèles 3D et sons : générés procéduralement pour ce projet.

Si tu publies ton jeu, garde ces mentions dans les crédits. Elles sont obligatoires pour OpenStreetMap et Copernicus.
