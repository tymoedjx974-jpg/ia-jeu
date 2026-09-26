#pragma once

#include "CoreMinimal.h"

// Noms partagés entre le module d'éditeur (création des matériaux) et le jeu (mise à jour chaque image)
namespace VPVegetation
{
	// collection de paramètres de matériau lue par le feuillage et l'écorce
	inline const TCHAR* CollectionPath() { return TEXT("/Game/VillageProvence/Materials/MPC_VP_Vent.MPC_VP_Vent"); }

	inline FName ForceVent() { return FName(TEXT("VentForce")); }
	inline FName DirectionVentX() { return FName(TEXT("VentDirX")); }
	inline FName DirectionVentY() { return FName(TEXT("VentDirY")); }

	// personnages qui écartent la végétation : xyz = position des pieds (cm), w = rayon (cm, partie entière) + force (partie décimale)
	constexpr int32 NumInteracteurs = 16;
	inline FName Interacteur(int32 Index) { return FName(*FString::Printf(TEXT("Interacteur%d"), Index)); }
	inline FLinearColor InteracteurVide() { return FLinearColor(0.f, 0.f, -1.0e8f, 0.f); }

	// sons (importés par le module d'éditeur)
	constexpr int32 NumFroissements = 4;
	inline FString SonVent() { return TEXT("/Game/VillageProvence/Sons/S_Vent.S_Vent"); }
	inline FString SonFroissement(int32 Index) { return FString::Printf(TEXT("/Game/VillageProvence/Sons/S_Froissement_%d.S_Froissement_%d"), Index, Index); }

	// étiquette des composants de végétation basse (herbes, lavande, buissons, vigne) : froissement au passage
	inline FName TagSouple() { return FName(TEXT("VP_Souple")); }
}
