#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VPRiviere.generated.h"

class APhysicsVolume;
class UBoxComponent;
class UPrimitiveComponent;

/**
 * Eau de la rivière des Ocres, placée par « Construire le village provençal ».
 * Des boîtes (UBoxComponent) couvrent le lit tronçon par tronçon ; un personnage qui y entre nage (mode Swimming du
 * CharacterMovement, volume d'eau) et reprend sa marche en sortant. Le plan d'eau visible n'a pas de collision.
 */
UCLASS(HideCategories = (Replication, Input, LOD, Cooking, Networking, HLOD))
class VILLAGEPROVENCE_API AVPRiviere : public AActor
{
	GENERATED_BODY()

public:
	AVPRiviere();

	/** Freinage dans l'eau (FluidFriction du volume d'eau). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Rivière")
	float Frottement = 0.3f;

	/** Vitesse maximale de chute dans l'eau (cm/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Rivière")
	float VitesseTerminale = 400.f;

	/** Ajoute un tronçon d'eau (appelé par le constructeur de village, dans l'éditeur). */
	UBoxComponent* AjouterTroncon(const FVector& Centre, float Yaw, const FVector& Taille, int32 Index);

	/** Vrai si l'acteur est dans l'eau de la rivière. */
	UFUNCTION(BlueprintPure, Category = "Village provençal|Rivière")
	bool EstDansLaRiviere(const AActor* Qui) const;

protected:
	virtual void BeginPlay() override;

private:
	UFUNCTION()
	void OnEntree(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index, bool bFromSweep, const FHitResult& Hit);

	UFUNCTION()
	void OnSortie(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index);

	UPROPERTY(Transient)
	TObjectPtr<APhysicsVolume> VolumeEau;

	TMap<TWeakObjectPtr<AActor>, int32> Nageurs;
};
