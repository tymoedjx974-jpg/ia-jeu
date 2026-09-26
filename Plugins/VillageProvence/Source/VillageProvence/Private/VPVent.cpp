#include "VPVent.h"

#include "Components/ArrowComponent.h"
#include "Components/SceneComponent.h"

AVPVent::AVPVent()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Racine = CreateDefaultSubobject<USceneComponent>(TEXT("Racine"));
	Racine->SetMobility(EComponentMobility::Static);
	RootComponent = Racine;

	Fleche = CreateDefaultSubobject<UArrowComponent>(TEXT("Fleche"));
	Fleche->SetupAttachment(Racine);
	Fleche->SetUsingAbsoluteRotation(true);
	Fleche->ArrowSize = 4.f;
	Fleche->ArrowColor = FColor(80, 170, 255);
	Fleche->bIsScreenSizeScaled = true;
	Fleche->SetHiddenInGame(true);
}

FVector AVPVent::GetSensDuVent() const
{
	// le vent vient de DirectionDegres (depuis le nord, sens horaire) et pousse à l'opposé ; l'axe Y d'Unreal pointe vers le sud
	const float Vers = FMath::DegreesToRadians(DirectionDegres + 180.f);
	return FVector(FMath::Sin(Vers), -FMath::Cos(Vers), 0.f);
}

void AVPVent::UpdateArrow()
{
	if (Fleche)
	{
		Fleche->SetWorldRotation(GetSensDuVent().Rotation());
	}
}

void AVPVent::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	UpdateArrow();
}

#if WITH_EDITOR
void AVPVent::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	UpdateArrow();
}
#endif
