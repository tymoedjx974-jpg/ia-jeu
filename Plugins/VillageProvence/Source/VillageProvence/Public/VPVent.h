#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VPVent.generated.h"

class UArrowComponent;
class USoundBase;

/**
 * Réglages du vent du village : direction, force, rafales et sons.
 * Un seul acteur par niveau ; sans lui, un mistral léger souffle par défaut.
 * La flèche indique le sens dans lequel le vent pousse la végétation.
 */
UCLASS(Blueprintable, HideCategories = (Rendering, Replication, Collision, Input, LOD, Cooking, Physics, Networking, HLOD, DataLayers))
class VILLAGEPROVENCE_API AVPVent : public AActor
{
	GENERATED_BODY()

public:
	AVPVent();

	/** D'où vient le vent, en degrés depuis le nord dans le sens horaire (330 = mistral de nord-nord-ouest, 180 = vent du sud). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vent", meta = (ClampMin = "0", ClampMax = "360"))
	float DirectionDegres = 330.f;

	/** Force moyenne : 0 = calme plat, 0,4 = brise, 1 = mistral fort, 1,5 = tempête. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vent", meta = (ClampMin = "0", ClampMax = "2"))
	float Force = 0.45f;

	/** Intensité des rafales (0 = vent régulier). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vent", meta = (ClampMin = "0", ClampMax = "1"))
	float Rafales = 0.6f;

	/** Écart maximal de direction pendant les rafales, en degrés. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vent", meta = (ClampMin = "0", ClampMax = "90"))
	float VariationDirection = 12.f;

	/** Rayon (cm) dans lequel un personnage écarte les herbes, la lavande et les buissons. 0 = selon sa capsule. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Végétation", meta = (ClampMin = "0", ClampMax = "300"))
	float RayonPassage = 0.f;

	/** Temps (s) que met une herbe couchée à se relever derrière le joueur. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Végétation", meta = (ClampMin = "0.1", ClampMax = "5"))
	float TempsRedressement = 1.2f;

	/** Souffle du vent entendu par le joueur, qui suit les rafales. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sons")
	bool bSonDuVent = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sons", meta = (ClampMin = "0", ClampMax = "2"))
	float VolumeVent = 0.45f;

	/** Froissement des herbes et des buissons quand le joueur les traverse. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sons")
	bool bFroissements = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sons", meta = (ClampMin = "0", ClampMax = "2"))
	float VolumeFroissements = 0.7f;

	/** Boucle du souffle du vent (renseignée par la construction du village). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sons")
	TObjectPtr<USoundBase> SonVent;

	/** Sons de froissement joués au hasard (renseignés par la construction du village). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sons")
	TArray<TObjectPtr<USoundBase>> SonsFroissement;

	/** Sens dans lequel le vent pousse (vecteur horizontal unitaire, repère Unreal). */
	UFUNCTION(BlueprintPure, Category = "Vent")
	FVector GetSensDuVent() const;

#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif
	virtual void OnConstruction(const FTransform& Transform) override;

private:
	void UpdateArrow();

	UPROPERTY(VisibleAnywhere, Category = "Vent")
	TObjectPtr<UArrowComponent> Fleche;
};
