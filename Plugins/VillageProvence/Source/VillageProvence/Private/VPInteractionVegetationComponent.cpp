#include "VPInteractionVegetationComponent.h"

#include "Engine/World.h"
#include "VPVegetationSubsystem.h"

UVPInteractionVegetationComponent::UVPInteractionVegetationComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UVPInteractionVegetationComponent::BeginPlay()
{
	Super::BeginPlay();
	if (UWorld* World = GetWorld())
	{
		if (UVPVegetationSubsystem* Subsystem = World->GetSubsystem<UVPVegetationSubsystem>())
		{
			Subsystem->RegisterInteraction(this);
		}
	}
}

void UVPInteractionVegetationComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		if (UVPVegetationSubsystem* Subsystem = World->GetSubsystem<UVPVegetationSubsystem>())
		{
			Subsystem->UnregisterInteraction(this);
		}
	}
	Super::EndPlay(EndPlayReason);
}
