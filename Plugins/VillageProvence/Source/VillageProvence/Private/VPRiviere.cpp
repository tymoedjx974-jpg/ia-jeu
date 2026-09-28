#include "VPRiviere.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PhysicsVolume.h"
#include "GameFramework/WorldSettings.h"

AVPRiviere::AVPRiviere()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Racine = CreateDefaultSubobject<USceneComponent>(TEXT("Racine"));
	Racine->SetMobility(EComponentMobility::Static);
	RootComponent = Racine;
}

UBoxComponent* AVPRiviere::AjouterTroncon(const FVector& Centre, float Yaw, const FVector& Taille, int32 Index)
{
	UBoxComponent* Box = NewObject<UBoxComponent>(this, *FString::Printf(TEXT("Eau_%d"), Index), RF_Transactional);
	Box->SetMobility(EComponentMobility::Static);
	Box->SetupAttachment(RootComponent);
	Box->SetBoxExtent(Taille * 0.5f);
	Box->SetWorldLocationAndRotation(Centre, FRotator(0.f, Yaw, 0.f));
	// ne bloque rien : détecte seulement les personnages qui entrent dans l'eau
	Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Box->SetCollisionObjectType(ECC_WorldStatic);
	Box->SetCollisionResponseToAllChannels(ECR_Ignore);
	Box->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	Box->SetGenerateOverlapEvents(true);
	Box->SetCanEverAffectNavigation(false);
	Box->SetHiddenInGame(true);
	Box->ShapeColor = FColor(40, 120, 255);
	Box->ComponentTags.AddUnique(FName(TEXT("VP_Eau")));
	AddInstanceComponent(Box);
	Box->RegisterComponent();
	return Box;
}

void AVPRiviere::BeginPlay()
{
	Super::BeginPlay();
	// volume d'eau « sans forme » : c'est nous qui y plaçons les personnages en entrant dans le lit
	FActorSpawnParameters P;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	VolumeEau = GetWorld()->SpawnActor<APhysicsVolume>(APhysicsVolume::StaticClass(), GetActorTransform(), P);
	if (VolumeEau)
	{
		VolumeEau->bWaterVolume = true;
		VolumeEau->FluidFriction = Frottement;
		VolumeEau->TerminalVelocity = VitesseTerminale;
		VolumeEau->Priority = 10;
	}
	TArray<UBoxComponent*> Boxes;
	GetComponents<UBoxComponent>(Boxes);
	for (UBoxComponent* Box : Boxes)
	{
		Box->OnComponentBeginOverlap.AddDynamic(this, &AVPRiviere::OnEntree);
		Box->OnComponentEndOverlap.AddDynamic(this, &AVPRiviere::OnSortie);
	}
}

void AVPRiviere::OnEntree(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index, bool bFromSweep, const FHitResult& Hit)
{
	ACharacter* Perso = Cast<ACharacter>(Autre);
	if (!Perso || !VolumeEau || AutreComp != Perso->GetRootComponent())
	{
		return;
	}
	int32& N = Nageurs.FindOrAdd(Perso);
	if (N++ > 0)
	{
		return;                                 // déjà dans l'eau (passage d'un tronçon au suivant)
	}
	if (UCharacterMovementComponent* CMC = Perso->GetCharacterMovement())
	{
		if (USceneComponent* Upd = CMC->UpdatedComponent)
		{
			Upd->SetShouldUpdatePhysicsVolume(false);
			Upd->SetPhysicsVolume(VolumeEau, true);
		}
		CMC->SetMovementMode(MOVE_Swimming);
	}
}

void AVPRiviere::OnSortie(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index)
{
	ACharacter* Perso = Cast<ACharacter>(Autre);
	if (!Perso || AutreComp != Perso->GetRootComponent())
	{
		return;
	}
	int32* N = Nageurs.Find(Perso);
	if (!N)
	{
		return;
	}
	if (--(*N) > 0)
	{
		return;
	}
	Nageurs.Remove(Perso);
	if (UCharacterMovementComponent* CMC = Perso->GetCharacterMovement())
	{
		if (USceneComponent* Upd = CMC->UpdatedComponent)
		{
			Upd->SetShouldUpdatePhysicsVolume(true);
			Upd->UpdatePhysicsVolume(true);
		}
		if (CMC->MovementMode == MOVE_Swimming)
		{
			CMC->SetMovementMode(MOVE_Falling);
		}
	}
}

bool AVPRiviere::EstDansLaRiviere(const AActor* Qui) const
{
	const int32* N = Nageurs.Find(const_cast<AActor*>(Qui));
	return N && *N > 0;
}
