#include "VPPointsApparition.h"

#include "Components/SceneComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"

AVPPointsApparition::AVPPointsApparition()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Racine = CreateDefaultSubobject<USceneComponent>(TEXT("Racine"));
	Racine->SetMobility(EComponentMobility::Static);
	RootComponent = Racine;
}

TArray<FVector> AVPPointsApparition::GetPointsAutour(FVector Centre, float DistanceMin, float DistanceMax, int32 Nombre, FVector Regard, float DistanceCachee) const
{
	TArray<FVector> Out;
	const FVector Look = Regard.GetSafeNormal2D();
	const float MinSq = DistanceMin * DistanceMin;
	const float MaxSq = DistanceMax * DistanceMax;
	for (const FVector& P : Points)
	{
		const FVector To = P - Centre;
		const float D2 = (float)To.SizeSquared2D();
		if (D2 < MinSq || D2 > MaxSq)
		{
			continue;
		}
		if (!Look.IsNearlyZero() && D2 < DistanceCachee * DistanceCachee && FVector::DotProduct(To.GetSafeNormal2D(), Look) > 0.34f)
		{
			continue;
		}
		Out.Add(P);
	}
	// mélange (Fisher-Yates) puis coupe
	for (int32 I = Out.Num() - 1; I > 0; --I)
	{
		Out.Swap(I, FMath::RandRange(0, I));
	}
	if (Nombre >= 0 && Out.Num() > Nombre)
	{
		Out.SetNum(Nombre);
	}
	return Out;
}

bool AVPPointsApparition::GetPointAleatoire(FVector Centre, float DistanceMin, float DistanceMax, FVector& Point) const
{
	const TArray<FVector> One = GetPointsAutour(Centre, DistanceMin, DistanceMax, 1);
	if (One.Num() == 0)
	{
		return false;
	}
	Point = One[0];
	return true;
}

AVPPointsApparition* AVPPointsApparition::Get(const UObject* WorldContextObject)
{
	UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	if (!World)
	{
		return nullptr;
	}
	for (TActorIterator<AVPPointsApparition> It(World); It; ++It)
	{
		return *It;
	}
	return nullptr;
}

#if WITH_EDITOR
void AVPPointsApparition::Afficher()
{
	if (UWorld* World = GetWorld())
	{
		for (const FVector& P : Points)
		{
			DrawDebugSphere(World, P + FVector(0.f, 0.f, 90.f), 60.f, 8, FColor(200, 40, 30), false, 20.f);
		}
		for (const FVector& P : MaisonsVisitables)
		{
			DrawDebugBox(World, P + FVector(0.f, 0.f, 150.f), FVector(80.f), FColor(40, 200, 60), false, 20.f);
		}
	}
}
#endif
