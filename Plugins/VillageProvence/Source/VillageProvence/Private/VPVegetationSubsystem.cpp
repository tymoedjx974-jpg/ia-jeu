#include "VPVegetationSubsystem.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Sound/SoundBase.h"
#include "UObject/UObjectIterator.h"
#include "VPInteractionVegetationComponent.h"
#include "VPVent.h"

namespace
{
	// pas de balayage des acteurs et de la végétation (secondes)
	constexpr double ActorScanPeriod = 0.5;
	constexpr double VegetationScanPeriod = 10.0;
	constexpr double RustleCheckPeriod = 0.12;
	// au-delà, un personnage n'écarte plus les plantes (elles ne bougent plus à cette distance de la caméra)
	constexpr float MaxInteractionDistance = 8000.f;
}

bool UVPVegetationSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	if (!Super::ShouldCreateSubsystem(Outer))
	{
		return false;
	}
	const UWorld* World = Cast<UWorld>(Outer);
	return World && (World->WorldType == EWorldType::Game || World->WorldType == EWorldType::PIE || World->WorldType == EWorldType::Editor);
}

void UVPVegetationSubsystem::Deinitialize()
{
	if (WindAudio)
	{
		WindAudio->Stop();
		WindAudio = nullptr;
	}
	Tracked.Empty();
	Components.Empty();
	SoftVegetation.Empty();
	Super::Deinitialize();
}

TStatId UVPVegetationSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UVPVegetationSubsystem, STATGROUP_Tickables);
}

void UVPVegetationSubsystem::SetVent(float DirectionDegres, float Force, float Rafales)
{
	if (AVPVent* Vent = VentActor.Get())
	{
		Vent->DirectionDegres = DirectionDegres;
		Vent->Force = Force;
		Vent->Rafales = Rafales;
		return;
	}
	bOverride = true;
	Override.DirectionDegres = DirectionDegres;
	Override.Force = FMath::Max(0.f, Force);
	Override.Rafales = FMath::Clamp(Rafales, 0.f, 1.f);
}

void UVPVegetationSubsystem::RegisterInteraction(UVPInteractionVegetationComponent* Component)
{
	Components.AddUnique(Component);
	if (AActor* Owner = Component ? Component->GetOwner() : nullptr)
	{
		Tracked.FindOrAdd(TWeakObjectPtr<AActor>(Owner)).Actor = Owner;
	}
}

void UVPVegetationSubsystem::UnregisterInteraction(UVPInteractionVegetationComponent* Component)
{
	Components.Remove(Component);
}

bool UVPVegetationSubsystem::EnsureCollection()
{
	if (Collection)
	{
		return true;
	}
	const double Now = FPlatformTime::Seconds();
	if (Now < NextCollectionTry)
	{
		return false;
	}
	// le village n'est peut-être pas encore construit : on réessaie de temps en temps, sans message
	NextCollectionTry = Now + 5.0;
	Collection = LoadObject<UMaterialParameterCollection>(nullptr, VPVegetation::CollectionPath(), nullptr, LOAD_NoWarn | LOAD_Quiet);
	return Collection != nullptr;
}

UVPVegetationSubsystem::FSettings UVPVegetationSubsystem::ReadSettings()
{
	UWorld* World = GetWorld();
	const double Now = FPlatformTime::Seconds();
	if (!VentActor.IsValid() && Now >= NextActorScan)
	{
		for (TActorIterator<AVPVent> It(World); It; ++It)
		{
			VentActor = *It;
			break;
		}
	}
	FSettings S;
	if (const AVPVent* Vent = VentActor.Get())
	{
		S.DirectionDegres = Vent->DirectionDegres;
		S.Force = Vent->Force;
		S.Rafales = Vent->Rafales;
		S.VariationDirection = Vent->VariationDirection;
		S.RayonPassage = Vent->RayonPassage;
		S.TempsRedressement = FMath::Max(0.1f, Vent->TempsRedressement);
		S.bSonDuVent = Vent->bSonDuVent;
		S.VolumeVent = Vent->VolumeVent;
		S.bFroissements = Vent->bFroissements;
		S.VolumeFroissements = Vent->VolumeFroissements;
	}
	else if (bOverride)
	{
		S.DirectionDegres = Override.DirectionDegres;
		S.Force = Override.Force;
		S.Rafales = Override.Rafales;
	}
	return S;
}

void UVPVegetationSubsystem::Tick(float DeltaTime)
{
	UWorld* World = GetWorld();
	if (!World || !EnsureCollection())
	{
		return;
	}
	// en jeu, le vent s'arrête quand le jeu est en pause, comme le temps des matériaux
	const bool bGame = World->IsGameWorld();
	const double Time = bGame ? World->GetTimeSeconds() : FPlatformTime::Seconds();
	const FSettings Settings = ReadSettings();
	UpdateWind(Time, Settings);
	if (bGame)
	{
		UpdateInteractors(DeltaTime, Time, Settings);
		UpdateSounds(DeltaTime, Time, Settings);
	}
	if (FPlatformTime::Seconds() >= NextActorScan)
	{
		NextActorScan = FPlatformTime::Seconds() + ActorScanPeriod;
	}
}

void UVPVegetationSubsystem::UpdateWind(double Time, const FSettings& S)
{
	// rafales : deux bruits lents superposés ; la direction louvoie un peu autour de la moyenne
	const float Slow = FMath::PerlinNoise1D((float)FMath::Fmod(Time * 0.09, 10000.0) + 3.1f);
	const float Fast = FMath::PerlinNoise1D((float)FMath::Fmod(Time * 0.37, 10000.0) + 11.7f);
	const float Gust = FMath::Clamp(0.5f + 1.1f * Slow + 0.45f * Fast, 0.f, 1.4f);
	CurrentForce = FMath::Max(0.f, S.Force * (1.f + S.Rafales * (Gust - 0.5f) * 1.3f));

	const float Wobble = FMath::PerlinNoise1D((float)FMath::Fmod(Time * 0.05, 10000.0) + 27.3f);
	const float Vers = FMath::DegreesToRadians(S.DirectionDegres + 180.f + S.VariationDirection * 1.6f * Wobble);
	CurrentDirection = FVector(FMath::Sin(Vers), -FMath::Cos(Vers), 0.f);

	if (UMaterialParameterCollectionInstance* Instance = GetWorld()->GetParameterCollectionInstance(Collection))
	{
		Instance->SetScalarParameterValue(VPVegetation::ForceVent(), CurrentForce);
		Instance->SetScalarParameterValue(VPVegetation::DirectionVentX(), (float)CurrentDirection.X);
		Instance->SetScalarParameterValue(VPVegetation::DirectionVentY(), (float)CurrentDirection.Y);
	}
}

bool UVPVegetationSubsystem::GetViewLocation(FVector& Out) const
{
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0))
	{
		if (PC->PlayerCameraManager)
		{
			Out = PC->PlayerCameraManager->GetCameraLocation();
			return true;
		}
		if (APawn* Pawn = PC->GetPawn())
		{
			Out = Pawn->GetActorLocation();
			return true;
		}
	}
	return false;
}

void UVPVegetationSubsystem::UpdateInteractors(float DeltaTime, double Time, const FSettings& S)
{
	UWorld* World = GetWorld();
	UMaterialParameterCollectionInstance* Instance = World->GetParameterCollectionInstance(Collection);
	if (!Instance)
	{
		return;
	}

	// tous les pions (joueur, personnages IA, animaux) écartent la végétation
	if (FPlatformTime::Seconds() >= NextActorScan)
	{
		for (TActorIterator<APawn> It(World); It; ++It)
		{
			Tracked.FindOrAdd(TWeakObjectPtr<AActor>(*It)).Actor = *It;
		}
		for (auto It = Tracked.CreateIterator(); It; ++It)
		{
			if (!It.Value().Actor.IsValid())
			{
				It.RemoveCurrent();
			}
		}
		Components.RemoveAll([](const TWeakObjectPtr<UVPInteractionVegetationComponent>& C) { return !C.IsValid(); });
	}

	FVector View = FVector::ZeroVector;
	const bool bHasView = GetViewLocation(View);
	const APawn* PlayerPawn = UGameplayStatics::GetPlayerPawn(World, 0);
	const float Dt = FMath::Max(DeltaTime, 1.0e-3f);
	const float Recovery = S.TempsRedressement;

	TArray<FSlot> Candidates;
	for (TPair<TWeakObjectPtr<AActor>, FTracked>& Pair : Tracked)
	{
		FTracked& T = Pair.Value;
		AActor* Actor = T.Actor.Get();
		if (!Actor || Actor->IsHidden())
		{
			continue;
		}
		const UVPInteractionVegetationComponent* Settings = Actor->FindComponentByClass<UVPInteractionVegetationComponent>();
		if (Settings && !Settings->bActif)
		{
			continue;
		}
		float CapsuleRadius = 0.f, CapsuleHalfHeight = 0.f;
		Actor->GetSimpleCollisionCylinder(CapsuleRadius, CapsuleHalfHeight);
		FVector Feet = Actor->GetActorLocation() - FVector(0.f, 0.f, CapsuleHalfHeight);
		if (Settings)
		{
			Feet.Z += Settings->DecalageVertical;
		}

		// vitesse lissée : un personnage qui court couche les herbes plus loin
		if (T.LastSeen > 0.0)
		{
			const float Instant = (float)FVector::Dist2D(Feet, T.LastLocation) / Dt;
			T.Speed = FMath::Lerp(T.Speed, FMath::Min(Instant, 3000.f), 0.2f);
		}
		T.LastLocation = Feet;
		T.LastSeen = Time;

		// traînée : les herbes couchées se relèvent peu à peu derrière le personnage
		if (T.Trail.Num() == 0 || FVector::Dist(T.Trail.Last().Location, Feet) > 30.f)
		{
			T.Trail.Add({ Feet, Time });
		}
		T.Trail.RemoveAll([Time, Recovery](const FTrailPoint& P) { return Time - P.Time > Recovery * 2.5; });
		if (T.Trail.Num() > 6)
		{
			T.Trail.RemoveAt(0, T.Trail.Num() - 6);
		}

		const float Distance = bHasView ? (float)FVector::Dist(View, Feet) : 0.f;
		if (Distance > MaxInteractionDistance)
		{
			continue;
		}
		float Radius = Settings && Settings->Rayon > 0.f ? Settings->Rayon
			: (S.RayonPassage > 0.f ? S.RayonPassage : FMath::Clamp(CapsuleRadius * 1.6f, 40.f, 250.f));
		const float Force = Settings ? Settings->Force : 1.f;
		const float Run = FMath::Clamp(T.Speed / 500.f, 0.f, 1.f);
		const bool bPlayer = Actor == PlayerPawn;
		const float Priority = Distance - (bPlayer ? 100000.f : 0.f);

		Candidates.Add({ Feet, Radius * (1.f + 0.2f * Run), Force * (0.8f + 0.2f * Run), Priority });
		for (const FTrailPoint& P : T.Trail)
		{
			const float Age = (float)(Time - P.Time);
			const float Strength = Force * 0.9f * FMath::Exp(-Age / Recovery);
			if (Strength < 0.08f || FVector::Dist2D(P.Location, Feet) < Radius * 0.5f)
			{
				continue;
			}
			Candidates.Add({ P.Location, Radius * 0.9f, Strength, Priority + 500.f + Age * 300.f });
		}
	}

	Candidates.Sort([](const FSlot& A, const FSlot& B) { return A.Priority < B.Priority; });
	const int32 Used = FMath::Min(Candidates.Num(), VPVegetation::NumInteracteurs);
	for (int32 I = 0; I < Used; ++I)
	{
		const FSlot& C = Candidates[I];
		// rayon en partie entière, force en partie décimale (voir le code du matériau)
		const float Packed = FMath::FloorToFloat(FMath::Clamp(C.Radius, 1.f, 5000.f)) + FMath::Clamp(C.Strength, 0.f, 0.99f);
		Instance->SetVectorParameterValue(VPVegetation::Interacteur(I), FLinearColor((float)C.Location.X, (float)C.Location.Y, (float)C.Location.Z, Packed));
	}
	for (int32 I = Used; I < LastUsedSlots; ++I)
	{
		Instance->SetVectorParameterValue(VPVegetation::Interacteur(I), VPVegetation::InteracteurVide());
	}
	LastUsedSlots = Used;
}

int32 UVPVegetationSubsystem::CountSoftVegetation(const FVector& Center, float Radius)
{
	const double Now = FPlatformTime::Seconds();
	if (Now >= NextVegetationScan)
	{
		NextVegetationScan = Now + VegetationScanPeriod;
		SoftVegetation.Reset();
		UWorld* World = GetWorld();
		for (TObjectIterator<UInstancedStaticMeshComponent> It; It; ++It)
		{
			if (It->GetWorld() == World && It->ComponentHasTag(VPVegetation::TagSouple()))
			{
				SoftVegetation.Add(*It);
			}
		}
	}
	int32 Count = 0;
	for (const TWeakObjectPtr<UInstancedStaticMeshComponent>& Weak : SoftVegetation)
	{
		const UInstancedStaticMeshComponent* Component = Weak.Get();
		if (!Component || !Component->Bounds.GetBox().ExpandBy(Radius).IsInsideOrOn(Center))
		{
			continue;
		}
		Count += Component->GetInstancesOverlappingSphere(Center, Radius, true).Num();
		if (Count >= 8)
		{
			break;
		}
	}
	return Count;
}

void UVPVegetationSubsystem::UpdateSounds(float DeltaTime, double Time, const FSettings& S)
{
	UWorld* World = GetWorld();
	if (!bSoundsLoaded)
	{
		bSoundsLoaded = true;
		const AVPVent* Vent = VentActor.Get();
		USoundBase* Wind = Vent ? Vent->SonVent.Get() : nullptr;
		if (!Wind)
		{
			Wind = LoadObject<USoundBase>(nullptr, *VPVegetation::SonVent(), nullptr, LOAD_NoWarn | LOAD_Quiet);
		}
		if (Wind)
		{
			WindAudio = UGameplayStatics::CreateSound2D(World, Wind, 0.f, 1.f, 0.f, nullptr, false, false);
		}
		if (Vent)
		{
			for (USoundBase* Sound : Vent->SonsFroissement)
			{
				if (Sound)
				{
					RustleSounds.Add(Sound);
				}
			}
		}
		if (RustleSounds.Num() == 0)
		{
			for (int32 I = 0; I < VPVegetation::NumFroissements; ++I)
			{
				if (USoundBase* Sound = LoadObject<USoundBase>(nullptr, *VPVegetation::SonFroissement(I), nullptr, LOAD_NoWarn | LOAD_Quiet))
				{
					RustleSounds.Add(Sound);
				}
			}
		}
	}

	// souffle du vent : suit les rafales
	if (WindAudio)
	{
		if (S.bSonDuVent && S.VolumeVent > 0.f)
		{
			const float Level = FMath::Pow(FMath::Clamp(CurrentForce / 0.9f, 0.f, 1.8f), 1.3f);
			WindAudio->SetVolumeMultiplier(FMath::Max(0.001f, S.VolumeVent * Level));
			WindAudio->SetPitchMultiplier(0.85f + 0.25f * FMath::Clamp(CurrentForce, 0.f, 1.5f));
			if (!WindAudio->IsPlaying())
			{
				WindAudio->Play();
			}
		}
		else if (WindAudio->IsPlaying())
		{
			WindAudio->Stop();
		}
	}

	// froissement quand le joueur traverse les herbes, la lavande, les buissons ou la vigne
	const APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0);
	if (!S.bFroissements || !Player || RustleSounds.Num() == 0)
	{
		return;
	}
	const FTracked* T = Tracked.Find(TWeakObjectPtr<AActor>(const_cast<APawn*>(Player)));
	if (!T)
	{
		return;
	}
	if (Time >= NextRustleCheck)
	{
		NextRustleCheck = Time + RustleCheckPeriod;
		LastRustleCount = T->Speed > 60.f ? CountSoftVegetation(T->LastLocation + FVector(0.f, 0.f, 40.f), 70.f) : 0;
	}
	if (LastRustleCount > 0 && T->Speed > 90.f && Time >= NextRustle)
	{
		const float Loud = FMath::Clamp(0.35f + T->Speed / 600.f, 0.35f, 1.2f) * FMath::Clamp(0.6f + 0.1f * LastRustleCount, 0.6f, 1.2f);
		USoundBase* Sound = RustleSounds[FMath::RandRange(0, RustleSounds.Num() - 1)];
		UGameplayStatics::PlaySound2D(World, Sound, S.VolumeFroissements * Loud, FMath::FRandRange(0.85f, 1.15f));
		NextRustle = Time + FMath::Clamp(0.5f - T->Speed / 1400.f, 0.18f, 0.45f) * FMath::FRandRange(0.85f, 1.15f);
	}
}
