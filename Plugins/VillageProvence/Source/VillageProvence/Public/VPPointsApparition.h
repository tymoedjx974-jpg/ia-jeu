#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VPPointsApparition.generated.h"

/**
 * Points d'apparition des zombies dans le village (rues, places, champs, maisons visitables),
 * placés par « Construire le village provençal ». Le mode de jeu les interroge pour faire apparaître
 * des zombies autour du joueur, hors de sa vue.
 */
UCLASS(HideCategories = (Rendering, Replication, Collision, Input, LOD, Cooking, Physics, Networking, HLOD))
class VILLAGEPROVENCE_API AVPPointsApparition : public AActor
{
	GENERATED_BODY()

public:
	AVPPointsApparition();

	/** Points d'apparition au sol (repère du monde, cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Zombies")
	TArray<FVector> Points;

	/** Rez-de-chaussée des maisons visitables (zombies cachés à l'intérieur, butin, objectifs...). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Zombies")
	TArray<FVector> MaisonsVisitables;

	/**
	 * Jusqu'à Nombre points entre DistanceMin et DistanceMax du centre, dans un ordre aléatoire.
	 * Si Regard n'est pas nul, les points situés devant (dans un cône de 70°) et à moins de DistanceCachee sont écartés.
	 */
	UFUNCTION(BlueprintCallable, Category = "Village provençal|Zombies")
	TArray<FVector> GetPointsAutour(FVector Centre, float DistanceMin = 1500.f, float DistanceMax = 6000.f, int32 Nombre = 8,
		FVector Regard = FVector::ZeroVector, float DistanceCachee = 3500.f) const;

	/** Un point au hasard autour du centre ; renvoie faux s'il n'y en a aucun. */
	UFUNCTION(BlueprintCallable, Category = "Village provençal|Zombies")
	bool GetPointAleatoire(FVector Centre, float DistanceMin, float DistanceMax, FVector& Point) const;

	/** Le premier acteur de ce type dans le monde (ou nul). */
	UFUNCTION(BlueprintPure, Category = "Village provençal|Zombies", meta = (WorldContext = "WorldContextObject"))
	static AVPPointsApparition* Get(const UObject* WorldContextObject);

#if WITH_EDITOR
	/** Affiche les points quelques secondes dans la fenêtre de l'éditeur. */
	UFUNCTION(CallInEditor, Category = "Zombies")
	void Afficher();
#endif
};
