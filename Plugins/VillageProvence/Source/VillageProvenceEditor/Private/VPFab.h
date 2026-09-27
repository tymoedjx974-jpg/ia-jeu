#pragma once

#include "CoreMinimal.h"

// Remplace les textures procédurales du village par des surfaces Fab / Megascans déjà ajoutées au projet.
// Les correspondances (mots-clés, taille des surfaces, teinte) sont dans Data/TexturesFab.json, modifiable.
class FVPFab
{
public:
	// cherche les textures du projet et les branche dans les instances de matériaux du village ; renvoie le compte rendu
	static FString Apply();
	// remet les textures d'origine du village
	static FString Restore();
};
