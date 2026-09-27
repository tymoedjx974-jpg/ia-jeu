# Mouvements réalistes — plugin Unreal Engine 5

Trois composants à ajouter au personnage de ton jeu, sans ville ni arme :

- **TM Movement** : course avec élan et endurance, accroupi progressif, glissade, roulade, réceptions lourdes, caméra au rythme des pas, jambes visibles pendant les glissades et les coups de pied.
- **TM Parkour** (facultatif) : attraper un rebord et se hisser, franchir en courant les obstacles bas, monter aux échelles.
- **TM Melee** (facultatif) : coup de pied sur **A**, couteau et coups de poing. Ton arme actuelle reste en place.

Ton personnage garde ses propres entrées. Il suffit de relier quelques touches aux fonctions des composants.

## 1. Installer le plugin

1. Copie le dossier `Plugins/TMMouvements` dans le dossier `Plugins` de ton projet. Crée ce dossier à côté du fichier `.uproject` s'il n'existe pas.
2. Ouvre ton projet. Unreal propose de compiler les modules manquants : réponds **Oui**. Visual Studio 2022 doit être installé, avec « Développement Desktop en C++ ».
3. Vérifie dans **Edit > Plugins** que « Mouvements réalistes (Toits Morts) » est coché.

## 2. Ajouter les composants au personnage

Ouvre le Blueprint de ton personnage, puis **Add Component** : ajoute **TM Movement**, **TM Parkour** pour le parkour et **TM Melee** si tu veux le corps à corps.

La caméra doit être attachée à la capsule, comme dans le modèle First Person d'Unreal. Le composant la trouve tout seul. Sinon, appelle `Set Camera` au démarrage.

## 3. Relier les touches (Event Graph du personnage)

| Touche | Événement | À brancher sur |
| --- | --- | --- |
| Maj | Pressed / Released | `TM Movement → Sprint Pressed` / `Sprint Released` |
| C | Pressed / Released | `TM Movement → Crouch Pressed` / `Crouch Released` |
| Espace | Pressed / Released | `TM Movement → Jump Pressed` / `Jump Released` (remplace le nœud `Jump`) |
| A | Pressed | `TM Melee → Kick` |
| Touche du couteau | Pressed | `TM Melee → Equip (Knife)` |
| Touche des poings | Pressed | `TM Melee → Equip (Fists)` |
| Touche de ton arme | Pressed | `TM Melee → Equip (None)` |
| Clic gauche | Pressed / Released | Si `Is Melee Equipped` : `Attack Pressed` / `Attack Released`, sinon ton tir habituel |

Z Q S D ne changent pas : ton personnage continue d'appeler `Add Movement Input`. C'est le composant qui règle la vitesse et l'élan.

Pour cacher ton arme quand le couteau ou les poings sont en main, utilise l'événement **On Equip Changed** de TM Melee : `Weapon == None` → ton arme est visible, sinon cache-la.

## 4. Points à vérifier dans ton jeu

- **Sprint existant** : si ton personnage change déjà `Max Walk Speed` pour sprinter, supprime cette logique. Le composant fixe la vitesse à chaque image.
- **Balancement de caméra existant** : désactive-le, ou décoche `Drive Camera` dans TM Movement. Sans cette case, seules la hauteur des yeux et le balancement vertical restent actifs.
- **Dégâts** : les coups arrivent sur les ennemis par `Apply Point Damage`. Leur événement `Event AnyDamage` ou `Event PointDamage` les reçoit déjà. Les ennemis de type Character sont aussi repoussés par les coups.
- **Dégâts de chute** : ils sont appliqués à ton personnage par `Apply Damage`. Décoche `Apply Fall Damage` si tu ne les veux pas, ou utilise l'événement `On Fall Damage`.
- **Exécutions** : pour qu'un coup de couteau tue d'un coup un ennemi qui ne t'a pas vu, crée un Blueprint enfant de TM Melee. Redéfinis-y la fonction `Is Target Unaware`, et renvoie « vrai » quand ton IA n'a pas repéré le joueur.

## Parkour (TM Parkour)

Il se déclenche tout seul avec la touche Saut de TM Movement. Il n'y a rien à brancher en plus.

| Figure | Comment |
| --- | --- |
| **Se hisser** | Face à un mur, appuie sur Saut : le personnage saute, attrape le rebord et se hisse, jusqu'à 2,30 m au-dessus des pieds. En l'air, il attrape tout seul le rebord devant lui si tu avances vers le mur (toits, balcons, caisses, bennes, murets). |
| **Franchir** | En courant vers un obstacle bas (40 à 130 cm : voiture, sacs de sable, barrière, muret), le personnage passe par-dessus sans ralentir. |
| **Échelles** | Avance vers une échelle pour l'attraper. Avancer fait monter. Reculer, ou avancer en regardant vers le bas, fait descendre. En haut, le personnage se hisse sur le toit. Saut te repousse de l'échelle. |

Les échelles sont les composants qui portent l'étiquette **TM_Echelle**. Le village provençal les étiquette déjà. Pour tes propres échelles, ajoute cette étiquette dans **Component Tags**.

Si ton personnage n'utilise pas TM Movement, appelle `TM Parkour → Try Parkour` à l'appui de Saut, et ne fais `Jump` que s'il renvoie faux.

## Réglages

Tout se règle dans le panneau Détails des composants : vitesses (cm/s), endurance, glissade, hauteur de saut, dégâts de chute, amplitude du balancement de tête, dégâts du corps à corps, arrêt sur image.

| Mouvement | Valeur par défaut |
| --- | --- |
| Marche | 3,1 m/s |
| Sprint | 5,6 m/s (10 s d'endurance) |
| Accroupi | 1,7 m/s |
| Glissade | minimum 4,6 m/s au départ, environ 1 s |
| Réception lourde | au-delà de 8,5 m/s de chute |
| Dégâts de chute | au-delà de 14 m/s de chute |

Ce plugin n'a pas encore été compilé : il a été écrit sans éditeur Unreal. Si la compilation affiche une erreur, copie-la et je la corrigerai.
