#include "VPPorte.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

AVPPorte::AVPPorte()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	Charniere = CreateDefaultSubobject<USceneComponent>(TEXT("Charniere"));
	RootComponent = Charniere;

	Vantail = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Vantail"));
	Vantail->SetupAttachment(Charniere);
	Vantail->SetMobility(EComponentMobility::Movable);
	Vantail->SetCollisionProfileName(TEXT("BlockAll"));
	// le navmesh passe par l'embrasure : les IA (zombies) peuvent chercher un chemin à travers la porte
	Vantail->SetCanEverAffectNavigation(false);

	// zone de détection : l'embrasure, 1,6 m de part et d'autre du mur
	Detection = CreateDefaultSubobject<UBoxComponent>(TEXT("Detection"));
	Detection->SetupAttachment(Charniere);
	Detection->SetRelativeLocation(FVector(45.f, 0.f, 110.f));
	Detection->SetBoxExtent(FVector(70.f, 160.f, 110.f));
	Detection->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	Detection->SetGenerateOverlapEvents(true);
	Detection->SetCanEverAffectNavigation(false);
}

void AVPPorte::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	bCibleOuverte = bOuverteAuDepart;
	AppliquerAngle(bOuverteAuDepart ? AngleOuverture : 0.f);
}

void AVPPorte::BeginPlay()
{
	Super::BeginPlay();
	Detection->OnComponentBeginOverlap.AddDynamic(this, &AVPPorte::OnDetectionDebut);
	Detection->OnComponentEndOverlap.AddDynamic(this, &AVPPorte::OnDetectionFin);
	DefinirEtat(bOuverteAuDepart);
}

bool AVPPorte::Declenche(const AActor* Autre) const
{
	const APawn* Pawn = Cast<APawn>(Autre);
	if (!Pawn)
	{
		return false;
	}
	return Pawn->IsPlayerControlled() || bOuvertureParIA;
}

void AVPPorte::OnDetectionDebut(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index, bool bFromSweep, const FHitResult& Hit)
{
	if (!Declenche(Autre))
	{
		return;
	}
	++Presents;
	TempsSansPresence = 0.f;
	if (bOuvertureAuto)
	{
		Ouvrir();
	}
}

void AVPPorte::OnDetectionFin(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index)
{
	if (!Declenche(Autre))
	{
		return;
	}
	Presents = FMath::Max(0, Presents - 1);
	if (Presents == 0 && bFermetureAuto && bCibleOuverte)
	{
		TempsSansPresence = 0.f;
		SetActorTickEnabled(true);
	}
}

void AVPPorte::Ouvrir()
{
	if (bVerrouillee || bCibleOuverte)
	{
		return;
	}
	bCibleOuverte = true;
	if (SonOuverture)
	{
		UGameplayStatics::PlaySoundAtLocation(this, SonOuverture, Vantail->GetComponentLocation());
	}
	DebutMouvement();
}

void AVPPorte::Fermer()
{
	if (!bCibleOuverte)
	{
		return;
	}
	bCibleOuverte = false;
	if (SonFermeture)
	{
		UGameplayStatics::PlaySoundAtLocation(this, SonFermeture, Vantail->GetComponentLocation());
	}
	DebutMouvement();
}

void AVPPorte::Basculer()
{
	if (bCibleOuverte)
	{
		Fermer();
	}
	else
	{
		Ouvrir();
	}
}

void AVPPorte::DefinirEtat(bool bOuverte)
{
	bCibleOuverte = bOuverte;
	AppliquerAngle(bOuverte ? AngleOuverture : 0.f);
	FinMouvement();
}

void AVPPorte::DebutMouvement()
{
	bEnMouvement = true;
	// pendant le mouvement, le vantail ne pousse pas les personnages (sinon le joueur peut rester coincé)
	Vantail->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	SetActorTickEnabled(true);
}

void AVPPorte::FinMouvement()
{
	bEnMouvement = false;
	Vantail->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
	if (!(bFermetureAuto && bCibleOuverte && Presents == 0))
	{
		SetActorTickEnabled(false);
	}
}

void AVPPorte::AppliquerAngle(float NouvelAngle)
{
	Angle = NouvelAngle;
	Vantail->SetRelativeRotation(FRotator(0.f, Angle, 0.f));
}

void AVPPorte::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bEnMouvement)
	{
		const float Cible = bCibleOuverte ? AngleOuverture : 0.f;
		AppliquerAngle(FMath::FInterpConstantTo(Angle, Cible, DeltaSeconds, Vitesse));
		if (FMath::IsNearlyEqual(Angle, Cible, 0.01f))
		{
			FinMouvement();
		}
		return;
	}
	// fermeture automatique quand plus personne n'est dans l'embrasure
	if (bFermetureAuto && bCibleOuverte && Presents == 0)
	{
		TempsSansPresence += DeltaSeconds;
		if (TempsSansPresence >= DelaiFermeture)
		{
			Fermer();
		}
	}
	else
	{
		SetActorTickEnabled(false);
	}
}

AVPPorte* AVPPorte::BasculerPorteProche(AActor* Qui, float Rayon)
{
	if (!Qui || !Qui->GetWorld())
	{
		return nullptr;
	}
	const FVector Pos = Qui->GetActorLocation();
	AVPPorte* Best = nullptr;
	float BestD2 = Rayon * Rayon;
	for (TActorIterator<AVPPorte> It(Qui->GetWorld()); It; ++It)
	{
		// distance au milieu du vantail fermé (la charnière est sur un côté)
		const FVector Milieu = It->GetActorLocation() + It->GetActorForwardVector() * 45.f + FVector(0.f, 0.f, 90.f);
		const float D2 = (float)FVector::DistSquared(Pos, Milieu);
		if (D2 < BestD2)
		{
			BestD2 = D2;
			Best = *It;
		}
	}
	if (Best)
	{
		Best->Basculer();
	}
	return Best;
}
