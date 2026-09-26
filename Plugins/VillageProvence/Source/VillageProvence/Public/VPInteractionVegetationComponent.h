#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VPInteractionVegetationComponent.generated.h"

/**
 * Réglage facultatif du passage d'un acteur dans la végétation.
 * Tous les pions (joueur, personnages IA, animaux) écartent déjà les herbes automatiquement ;
 * ce composant permet de changer le rayon et la force, de désactiver l'effet,
 * ou de l'ajouter à un acteur qui n'est pas un pion (véhicule, objet lancé...).
 */
UCLASS(ClassGroup = (VillageProvence), meta = (BlueprintSpawnableComponent, DisplayName = "Interaction végétation (village)"))
class VILLAGEPROVENCE_API UVPInteractionVegetationComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UVPInteractionVegetationComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Végétation")
	bool bActif = true;

	/** Rayon (cm) dans lequel les plantes s'écartent. 0 = selon la capsule de collision. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Végétation", meta = (ClampMin = "0", ClampMax = "1000"))
	float Rayon = 0.f;

	/** Force de la poussée (0 à 1). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Végétation", meta = (ClampMin = "0", ClampMax = "1"))
	float Force = 1.f;

	/** Décalage vertical (cm) du point de contact par rapport au bas de la capsule. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Végétation")
	float DecalageVertical = 0.f;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
};
