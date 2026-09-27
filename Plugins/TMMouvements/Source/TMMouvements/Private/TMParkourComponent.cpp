#include "TMParkourComponent.h"

#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "TMMovementComponent.h"

UTMParkourComponent::UTMParkourComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// après le mouvement du personnage (qui consomme les entrées de déplacement)
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void UTMParkourComponent::BeginPlay()
{
	Super::BeginPlay();
	Character = Cast<ACharacter>(GetOwner());
	if (!Character)
	{
		UE_LOG(LogTemp, Warning, TEXT("TMParkourComponent doit être ajouté à un Character."));
		SetComponentTickEnabled(false);
		return;
	}
	Move = Character->GetCharacterMovement();
	TMMove = Character->FindComponentByClass<UTMMovementComponent>();
}

// ------------------------------------------------------------------ requêtes
bool UTMParkourComponent::Trace(const FVector& A, const FVector& B, FHitResult& Hit) const
{
	FCollisionQueryParams Params(SCENE_QUERY_STAT(TMParkour), false, Character);
	if (!GetWorld()->LineTraceSingleByChannel(Hit, A, B, ECC_Visibility, Params))
	{
		return false;
	}
	// les personnages (zombies, pillards) ne servent pas d'appui
	return !(Hit.GetActor() && Hit.GetActor()->IsA<APawn>());
}

bool UTMParkourComponent::Sweep(const FVector& A, const FVector& B, float Radius, FHitResult& Hit) const
{
	FCollisionQueryParams Params(SCENE_QUERY_STAT(TMParkour), false, Character);
	if (!GetWorld()->SweepSingleByChannel(Hit, A, B, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(Radius), Params))
	{
		return false;
	}
	return !(Hit.GetActor() && Hit.GetActor()->IsA<APawn>());
}

bool UTMParkourComponent::CapsuleFits(const FVector& Center) const
{
	const UCapsuleComponent* Cap = Character->GetCapsuleComponent();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(TMParkourFit), false, Character);
	const FCollisionShape Shape = FCollisionShape::MakeCapsule(Cap->GetScaledCapsuleRadius() - 2.f, Cap->GetScaledCapsuleHalfHeight() - 2.f);
	return !GetWorld()->OverlapBlockingTestByChannel(Center, FQuat::Identity, Cap->GetCollisionObjectType(), Shape, Params, Cap->GetCollisionResponseToChannels());
}

FVector UTMParkourComponent::Facing() const
{
	// direction voulue : l'entrée de déplacement si elle existe, sinon le regard
	const FVector In = Character->GetLastMovementInputVector().GetSafeNormal2D();
	if (!In.IsNearlyZero())
	{
		return In;
	}
	return FRotator(0.f, Character->GetControlRotation().Yaw, 0.f).Vector();
}

bool UTMParkourComponent::FindLedge(float MaxHeight, bool bCheckHeadroom, FVector& OutTarget, float& OutHeight) const
{
	const UCapsuleComponent* Cap = Character->GetCapsuleComponent();
	const float R = Cap->GetScaledCapsuleRadius();
	const float HH = Cap->GetScaledCapsuleHalfHeight();
	const FVector Loc = Character->GetActorLocation();
	const float FeetZ = Loc.Z - HH;
	const FVector Fwd = Facing();

	// 1. un mur devant, à hauteur de hanche puis de poitrine
	FHitResult Wall;
	bool bWall = false;
	for (const float Z : { 60.f, 110.f, 150.f })
	{
		const FVector A(Loc.X, Loc.Y, FeetZ + Z);
		if (Sweep(A, A + Fwd * (R + 55.f), 12.f, Wall) && FMath::Abs(Wall.ImpactNormal.Z) < 0.55f && !Wall.bStartPenetrating)
		{
			bWall = true;
			break;
		}
	}
	if (!bWall)
	{
		return false;
	}
	const FVector Dir = -FVector(Wall.ImpactNormal.X, Wall.ImpactNormal.Y, 0.f).GetSafeNormal();
	if (FVector::DotProduct(Dir, Fwd) < 0.5f)
	{
		return false;
	}

	// 2. le dessus du rebord : on descend depuis la hauteur maximale, un peu au-delà de la face du mur
	FHitResult Top;
	const FVector P = Wall.ImpactPoint + Dir * 28.f;
	const FVector TopStart(P.X, P.Y, FeetZ + MaxHeight + 25.f);
	const FVector TopEnd(P.X, P.Y, FeetZ + MantleMinHeight - 5.f);
	if (!Trace(TopStart, TopEnd, Top) || Top.bStartPenetrating || Top.ImpactNormal.Z < 0.7f)
	{
		return false;
	}
	const float H = Top.ImpactPoint.Z - FeetZ;
	if (H < MantleMinHeight || H > MaxHeight)
	{
		return false;
	}

	// 3. de la place pour se tenir debout sur le rebord, et au-dessus de la tête pendant la montée
	const FVector Target(Wall.ImpactPoint.X + Dir.X * (R + 12.f), Wall.ImpactPoint.Y + Dir.Y * (R + 12.f), Top.ImpactPoint.Z + HH + 3.f);
	if (!CapsuleFits(Target))
	{
		return false;
	}
	if (bCheckHeadroom)
	{
		FHitResult Head;
		const FVector Up(Loc.X, Loc.Y, Target.Z);
		if (Sweep(Loc + FVector(0.f, 0.f, HH - R), Up + FVector(0.f, 0.f, HH - R), R - 3.f, Head))
		{
			return false;
		}
	}
	OutTarget = Target;
	OutHeight = H;
	return true;
}

bool UTMParkourComponent::FindVault(FVector& OutOver, FVector& OutLanding) const
{
	const UCapsuleComponent* Cap = Character->GetCapsuleComponent();
	const float R = Cap->GetScaledCapsuleRadius();
	const float HH = Cap->GetScaledCapsuleHalfHeight();
	const FVector Loc = Character->GetActorLocation();
	const float FeetZ = Loc.Z - HH;
	const FVector Vel2D(Move->Velocity.X, Move->Velocity.Y, 0.f);
	if (Vel2D.Size() < VaultMinSpeed)
	{
		return false;
	}
	const FVector Fwd = Vel2D.GetSafeNormal();
	FHitResult Wall;
	const FVector A(Loc.X, Loc.Y, FeetZ + 35.f);
	if (!Sweep(A, A + Fwd * (R + 70.f), 10.f, Wall) || FMath::Abs(Wall.ImpactNormal.Z) > 0.55f || Wall.bStartPenetrating)
	{
		return false;
	}
	const FVector Dir = -FVector(Wall.ImpactNormal.X, Wall.ImpactNormal.Y, 0.f).GetSafeNormal();
	if (FVector::DotProduct(Dir, Fwd) < 0.6f)
	{
		return false;
	}
	// hauteur de l'obstacle
	FHitResult Top;
	const FVector P = Wall.ImpactPoint + Dir * 15.f;
	if (!Trace(FVector(P.X, P.Y, FeetZ + VaultMaxHeight + 20.f), FVector(P.X, P.Y, FeetZ + 20.f), Top) || Top.bStartPenetrating)
	{
		return false;
	}
	const float H = Top.ImpactPoint.Z - FeetZ;
	if (H < VaultMinHeight || H > VaultMaxHeight)
	{
		return false;
	}
	// l'autre côté : on avance jusqu'à retrouver le sol à peu près à la hauteur des pieds
	for (float D = 30.f; D <= VaultMaxDepth + 20.f; D += 15.f)
	{
		const FVector Q = Wall.ImpactPoint + Dir * D;
		FHitResult Down;
		if (!Trace(FVector(Q.X, Q.Y, Top.ImpactPoint.Z + 10.f), FVector(Q.X, Q.Y, FeetZ - 120.f), Down))
		{
			continue;
		}
		if (Down.ImpactPoint.Z < Top.ImpactPoint.Z - 30.f && Down.ImpactPoint.Z > FeetZ - 110.f && Down.ImpactNormal.Z > 0.7f)
		{
			const FVector Land = Down.ImpactPoint + Dir * (R + 20.f) + FVector(0.f, 0.f, HH + 3.f);
			if (!CapsuleFits(Land))
			{
				return false;
			}
			const FVector Over = Wall.ImpactPoint + Dir * (D * 0.5f);
			OutOver = FVector(Over.X, Over.Y, Top.ImpactPoint.Z + HH * 0.6f + 12.f);
			OutLanding = Land;
			return true;
		}
	}
	return false;
}

bool UTMParkourComponent::FindLadder(FHitResult& OutHit) const
{
	const UCapsuleComponent* Cap = Character->GetCapsuleComponent();
	const FVector Loc = Character->GetActorLocation();
	const FVector Fwd = Facing();
	for (const float Z : { 0.f, -40.f, 40.f })
	{
		const FVector A = Loc + FVector(0.f, 0.f, Z);
		if (Sweep(A, A + Fwd * (Cap->GetScaledCapsuleRadius() + 45.f), 15.f, OutHit) && OutHit.GetComponent() && OutHit.GetComponent()->ComponentHasTag(LadderTag))
		{
			return true;
		}
	}
	return false;
}

// ------------------------------------------------------------------ déclenchement
bool UTMParkourComponent::TryParkour()
{
	if (!Character || !Move)
	{
		return false;
	}
	if (State == ETMParkourState::Ladder)
	{
		// saut depuis l'échelle : on se repousse du mur
		EndState(false, LadderNormal * 380.f + FVector(0.f, 0.f, 320.f));
		Cooldown = 0.5f;
		return true;
	}
	if (State != ETMParkourState::None)
	{
		return true;
	}
	FVector Target, Over, Landing;
	float H = 0.f;
	const float Speed = FVector(Move->Velocity.X, Move->Velocity.Y, 0.f).Size();
	if (Move->IsMovingOnGround())
	{
		if (FindVault(Over, Landing))
		{
			const FVector Loc = Character->GetActorLocation();
			const float Dist = FVector::Dist(Loc, Over) + FVector::Dist(Over, Landing);
			StartMove(ETMParkourState::Vault, { Loc, Over, Landing }, FMath::Clamp(Dist / FMath::Max(Speed, 1.f) * 1.1f, 0.35f, 0.75f),
				FVector(Move->Velocity.X, Move->Velocity.Y, 0.f) * 0.9f);
			return true;
		}
		// au sol, les petits rebords se passent en sautant normalement
		if (FindLedge(MantleMaxHeightGround, true, Target, H) && H > 105.f)
		{
			const FVector Loc = Character->GetActorLocation();
			StartMove(ETMParkourState::Mantle, { Loc, FVector(Loc.X, Loc.Y, Target.Z + 5.f), Target },
				(0.32f + H / 420.f) / FMath::Max(0.2f, MantleSpeed), Facing() * 150.f);
			return true;
		}
		// une échelle devant : on l'attrape
		FHitResult Ladder;
		if (FindLadder(Ladder))
		{
			EnterLadder(Ladder);
			return true;
		}
		return false;
	}
	if (Move->IsFalling() && FindLedge(MantleMaxHeightAir, true, Target, H))
	{
		const FVector Loc = Character->GetActorLocation();
		StartMove(ETMParkourState::Mantle, { Loc, FVector(Loc.X, Loc.Y, Target.Z + 5.f), Target },
			(0.28f + H / 480.f) / FMath::Max(0.2f, MantleSpeed), Facing() * 150.f);
		return true;
	}
	return false;
}

void UTMParkourComponent::StartMove(ETMParkourState NewState, const TArray<FVector>& Points, float Duration, const FVector& ExitVelocity)
{
	State = NewState;
	Path = Points;
	// temps cumulé proportionnel aux longueurs, la montée un peu plus lente
	PathT.Reset();
	PathT.Add(0.f);
	float Total = 0.f;
	for (int32 I = 1; I < Path.Num(); ++I)
	{
		const FVector D = Path[I] - Path[I - 1];
		Total += D.Size() * (FMath::Abs(D.Z) > D.Size2D() ? 1.3f : 1.f) + 1.f;
		PathT.Add(Total);
	}
	for (float& T : PathT)
	{
		T /= FMath::Max(Total, 1.f);
	}
	MoveT = 0.f;
	MoveDur = FMath::Max(Duration, 0.05f);
	MoveExitVelocity = ExitVelocity;
	Move->StopMovementImmediately();
	Move->SetMovementMode(MOVE_None);
	if (TMMove)
	{
		TMMove->SpendStamina(NewState == ETMParkourState::Mantle ? MantleStamina : MantleStamina * 0.5f);
		TMMove->AddShake(NewState == ETMParkourState::Mantle ? 0.25f : 0.15f);
	}
	OnParkourStarted.Broadcast(State);
}

void UTMParkourComponent::EnterLadder(const FHitResult& Hit)
{
	State = ETMParkourState::Ladder;
	LadderNormal = FVector(Hit.ImpactNormal.X, Hit.ImpactNormal.Y, 0.f).GetSafeNormal();
	const float R = Character->GetCapsuleComponent()->GetScaledCapsuleRadius();
	LadderAnchor = Hit.ImpactPoint + LadderNormal * (R + 6.f);
	Move->StopMovementImmediately();
	Move->SetMovementMode(MOVE_None);
	OnParkourStarted.Broadcast(State);
}

void UTMParkourComponent::EndState(bool bWalking, const FVector& ExitVelocity)
{
	const ETMParkourState Old = State;
	State = ETMParkourState::None;
	Move->SetMovementMode(bWalking ? MOVE_Walking : MOVE_Falling);
	Move->Velocity = ExitVelocity;
	OnParkourEnded.Broadcast(Old);
}

// ------------------------------------------------------------------ mise à jour
void UTMParkourComponent::TickComponent(float Dt, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(Dt, TickType, ThisTickFunction);
	if (!Character || !Move)
	{
		return;
	}
	Cooldown -= Dt;
	switch (State)
	{
	case ETMParkourState::Mantle:
	case ETMParkourState::Vault:
		TickMove(Dt);
		return;
	case ETMParkourState::Ladder:
		TickLadder(Dt);
		return;
	default:
		break;
	}
	if (Cooldown > 0.f)
	{
		return;
	}
	const FVector In = Character->GetLastMovementInputVector();
	const float Forward = FVector::DotProduct(In.GetSafeNormal2D(), FRotator(0.f, Character->GetControlRotation().Yaw, 0.f).Vector());
	// échelle : on avance vers elle
	if (Forward > 0.5f)
	{
		FHitResult Ladder;
		if (FindLadder(Ladder) && FVector::DotProduct(In.GetSafeNormal2D(), -Ladder.ImpactNormal.GetSafeNormal2D()) > 0.5f)
		{
			EnterLadder(Ladder);
			return;
		}
	}
	// en l'air, on attrape le rebord devant soi
	if (bAutoMantle && Move->IsFalling() && Forward > 0.3f && Move->Velocity.Z < 250.f)
	{
		FVector Target;
		float H = 0.f;
		if (FindLedge(MantleMaxHeightAir, true, Target, H))
		{
			const FVector Loc = Character->GetActorLocation();
			StartMove(ETMParkourState::Mantle, { Loc, FVector(Loc.X, Loc.Y, Target.Z + 5.f), Target },
				(0.28f + H / 480.f) / FMath::Max(0.2f, MantleSpeed), Facing() * 150.f);
			return;
		}
	}
	// en courant, on franchit les obstacles bas
	if (bAutoVault && Move->IsMovingOnGround() && Forward > 0.5f)
	{
		FVector Over, Landing;
		if (FindVault(Over, Landing))
		{
			const FVector Loc = Character->GetActorLocation();
			const float Speed = FVector(Move->Velocity.X, Move->Velocity.Y, 0.f).Size();
			const float Dist = FVector::Dist(Loc, Over) + FVector::Dist(Over, Landing);
			StartMove(ETMParkourState::Vault, { Loc, Over, Landing }, FMath::Clamp(Dist / FMath::Max(Speed, 1.f) * 1.1f, 0.35f, 0.75f),
				FVector(Move->Velocity.X, Move->Velocity.Y, 0.f) * 0.9f);
		}
	}
}

void UTMParkourComponent::TickMove(float Dt)
{
	MoveT += Dt;
	const float A = FMath::Clamp(MoveT / MoveDur, 0.f, 1.f);
	int32 Seg = 1;
	while (Seg < PathT.Num() - 1 && A > PathT[Seg])
	{
		++Seg;
	}
	const float T0 = PathT[Seg - 1], T1 = PathT[Seg];
	const float Local = FMath::SmoothStep(0.f, 1.f, (A - T0) / FMath::Max(T1 - T0, 1e-4f));
	Character->SetActorLocation(FMath::Lerp(Path[Seg - 1], Path[Seg], Local), false);
	if (A >= 1.f)
	{
		EndState(State == ETMParkourState::Mantle, MoveExitVelocity);
	}
}

void UTMParkourComponent::TickLadder(float Dt)
{
	const UCapsuleComponent* Cap = Character->GetCapsuleComponent();
	const float HH = Cap->GetScaledCapsuleHalfHeight();
	const FVector Loc = Character->GetActorLocation();
	const FVector In = Character->GetLastMovementInputVector();
	// avancer vers l'échelle = monter ; en regardant vers le bas, avancer = descendre ; reculer = descendre
	float Up = FVector::DotProduct(In, -LadderNormal);
	const float Pitch = FRotator::NormalizeAxis(Character->GetControlRotation().Pitch);
	if (Pitch < -35.f)
	{
		Up = -Up;
	}
	const float Side = FVector::DotProduct(In, FVector::CrossProduct(FVector::UpVector, LadderNormal));
	FVector Next(LadderAnchor.X, LadderAnchor.Y, Loc.Z + Up * ClimbSpeed * Dt);

	// toujours une échelle devant ? sinon on est en haut : on se hisse sur le toit
	FHitResult Rung;
	const FVector Head = FVector(LadderAnchor.X, LadderAnchor.Y, Next.Z + HH * 0.6f);
	const bool bLadderAtHead = Sweep(Head, Head - LadderNormal * 45.f, 12.f, Rung) && Rung.GetComponent() && Rung.GetComponent()->ComponentHasTag(LadderTag);
	if (!bLadderAtHead && Up > 0.f)
	{
		FVector Target;
		float H = 0.f;
		if (FindLedge(MantleMaxHeightAir + 40.f, false, Target, H))
		{
			StartMove(ETMParkourState::Mantle, { Loc, FVector(Loc.X, Loc.Y, Target.Z + 8.f), Target }, (0.35f + H / 480.f) / FMath::Max(0.2f, MantleSpeed),
				-LadderNormal * 120.f);
			return;
		}
		Next.Z = Loc.Z;
	}
	// en bas : le sol sous les pieds
	if (Up < 0.f)
	{
		FHitResult Floor;
		if (Trace(Loc, Loc - FVector(0.f, 0.f, HH + 6.f), Floor))
		{
			EndState(true, FVector::ZeroVector);
			Cooldown = 0.4f;
			return;
		}
	}
	// s'écarter de côté ou reculer franchement : on lâche l'échelle
	if (FMath::Abs(Side) > 0.8f && FMath::Abs(Up) < 0.2f)
	{
		EndState(false, FVector::CrossProduct(FVector::UpVector, LadderNormal) * Side * 150.f);
		Cooldown = 0.5f;
		return;
	}
	FHitResult Block;
	Character->SetActorLocation(Next, true, &Block);
	if (TMMove && FMath::Abs(Up) > 0.1f)
	{
		TMMove->SpendStamina(0.02f * Dt);
	}
}
