#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "VPVegetationShared.h"
#include "VPVegetationSubsystem.generated.h"

class AVPVent;
class UAudioComponent;
class UInstancedStaticMeshComponent;
class UMaterialParameterCollection;
class USoundBase;
class UVPInteractionVegetationComponent;

/**
 * Anime la végétation du village : vent avec rafales et plantes qui s'écartent au passage des personnages.
 * Chaque image, il écrit dans la collection MPC_VP_Vent la force et la direction du vent,
 * ainsi que la position des personnages proches ; les matériaux du feuillage et de l'écorce en déduisent le mouvement.
 */
UCLASS()
class VILLAGEPROVENCE_API UVPVegetationSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool IsTickableInEditor() const override { return true; }

	/** Change le vent (utile pour la météo du jeu). Direction : d'où vient le vent, en degrés depuis le nord. */
	UFUNCTION(BlueprintCallable, Category = "Village provençal|Vent")
	void SetVent(float DirectionDegres, float Force, float Rafales);

	/** Force du vent à cet instant, rafales comprises. */
	UFUNCTION(BlueprintPure, Category = "Village provençal|Vent")
	float GetForceVentActuelle() const { return CurrentForce; }

	/** Sens dans lequel le vent pousse à cet instant (vecteur horizontal unitaire). */
	UFUNCTION(BlueprintPure, Category = "Village provençal|Vent")
	FVector GetSensVentActuel() const { return CurrentDirection; }

	void RegisterInteraction(UVPInteractionVegetationComponent* Component);
	void UnregisterInteraction(UVPInteractionVegetationComponent* Component);

private:
	struct FTrailPoint
	{
		FVector Location;
		double Time;
	};

	struct FTracked
	{
		TWeakObjectPtr<AActor> Actor;
		TArray<FTrailPoint> Trail;
		FVector LastLocation = FVector::ZeroVector;
		float Speed = 0.f;
		double LastSeen = 0.0;
	};

	struct FSlot
	{
		FVector Location;
		float Radius;
		float Strength;
		float Priority;
	};

	struct FSettings
	{
		float DirectionDegres = 330.f;
		float Force = 0.45f;
		float Rafales = 0.6f;
		float VariationDirection = 12.f;
		float RayonPassage = 0.f;
		float TempsRedressement = 1.2f;
		bool bSonDuVent = true;
		float VolumeVent = 0.45f;
		bool bFroissements = true;
		float VolumeFroissements = 0.7f;
	};

	bool EnsureCollection();
	FSettings ReadSettings();
	void UpdateWind(double Time, const FSettings& Settings);
	void UpdateInteractors(float DeltaTime, double Time, const FSettings& Settings);
	void UpdateSounds(float DeltaTime, double Time, const FSettings& Settings);
	bool GetViewLocation(FVector& Out) const;
	int32 CountSoftVegetation(const FVector& Center, float Radius);

	UPROPERTY(Transient)
	TObjectPtr<UMaterialParameterCollection> Collection;

	UPROPERTY(Transient)
	TObjectPtr<UAudioComponent> WindAudio;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USoundBase>> RustleSounds;

	TWeakObjectPtr<AVPVent> VentActor;
	TArray<TWeakObjectPtr<UVPInteractionVegetationComponent>> Components;
	TArray<TWeakObjectPtr<UInstancedStaticMeshComponent>> SoftVegetation;
	TMap<TWeakObjectPtr<AActor>, FTracked> Tracked;

	bool bOverride = false;
	FSettings Override;
	bool bCollectionMissing = false;
	bool bSoundsLoaded = false;
	double NextCollectionTry = 0.0;
	double NextActorScan = 0.0;
	double NextVegetationScan = 0.0;
	double NextRustle = 0.0;
	double NextRustleCheck = 0.0;
	int32 LastRustleCount = 0;
	float CurrentForce = 0.f;
	FVector CurrentDirection = FVector(0.5f, 0.866f, 0.f);
	int32 LastUsedSlots = VPVegetation::NumInteracteurs;
};
