#include "TMMeleeComponent.h"

#include "TMMShapes.h"
#include "TMMovementComponent.h"

#include "Camera/CameraComponent.h"
#include "Engine/OverlapResult.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/DamageType.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"

namespace
{
	// durée, instant de l'impact, délai avant le coup suivant, dégâts, allonge (cm), recul infligé (cm/s)
	struct FStrikeDef { float Dur, Hit, Cool, Dmg, Reach, Push; bool bDown, bWide, bKnife; };
	const FStrikeDef& StrikeDef(ETMStrike S)
	{
		static const FStrikeDef Defs[] = {
			{0.f, 0.f, 0.f, 0.f, 0.f, 0.f, false, false, false},
			{0.30f, 0.10f, 0.24f, 10.f, 155.f, 250.f, false, false, false}, // direct
			{0.38f, 0.14f, 0.32f, 16.f, 165.f, 350.f, false, false, false}, // croisé
			{0.50f, 0.20f, 0.55f, 24.f, 145.f, 600.f, true, true, false},   // crochet : renverse
			{0.44f, 0.15f, 0.40f, 50.f, 180.f, 100.f, false, false, true},  // estoc
			{0.40f, 0.14f, 0.36f, 36.f, 175.f, 150.f, false, true, true},   // taillade
		};
		return Defs[(int32)S];
	}
	float Smooth01(float T) { T = FMath::Clamp(T, 0.f, 1.f); return T * T * (3.f - 2.f * T); }
}

UTMMeleeComponent::UTMMeleeComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

bool UTMMeleeComponent::IsTargetUnaware_Implementation(AActor* Target) const
{
	return false;
}

void UTMMeleeComponent::BeginPlay()
{
	Super::BeginPlay();
	Movement = GetOwner()->FindComponentByClass<UTMMovementComponent>();
	Camera = Movement && Movement->GetCamera() ? Movement->GetCamera() : GetOwner()->FindComponentByClass<UCameraComponent>();
	if (bShowArms && Camera) BuildArms();
}

void UTMMeleeComponent::Equip(ETMMeleeWeapon Weapon)
{
	if (Weapon == Equipped) return;
	Equipped = Weapon;
	Strike = ETMStrike::None;
	SwitchT = Cooldown = 0.36f;
	if (Movement) Movement->SpeedMultiplier = Weapon == ETMMeleeWeapon::None ? 1.f : 1.05f;
	OnEquipChanged.Broadcast(Weapon);
}

void UTMMeleeComponent::AttackPressed()
{
	bHeld = true;
	StartStrike();
}

void UTMMeleeComponent::StartStrike()
{
	if (Equipped == ETMMeleeWeapon::None || Cooldown > 0.f || SwitchT > 0.f) return;
	const bool bKnife = Equipped == ETMMeleeWeapon::Knife;
	const float Now = GetWorld()->GetTimeSeconds();
	Combo = Now - LastStrikeTime < 0.75f ? Combo + 1 : 0;
	LastStrikeTime = Now;
	// couteau : estoc puis taillade ; poings : direct, croisé, crochet
	if (bKnife) Strike = Combo % 2 ? ETMStrike::Slash : ETMStrike::Stab;
	else Strike = Combo % 3 == 0 ? ETMStrike::Jab : Combo % 3 == 1 ? ETMStrike::Cross : ETMStrike::Hook;
	StrikeT = 0.f;
	bStrikeDone = false;
	Cooldown = StrikeDef(Strike).Cool;
	if (Movement) Movement->SpendStamina(0.025f);
}

void UTMMeleeComponent::Kick()
{
	ACharacter* C = Cast<ACharacter>(GetOwner());
	if (!C || KickCooldown > 0.f || (Movement && (Movement->IsKicking() || Movement->IsRolling()))) return;
	// armé du genou, extension, impact, retour : le coup ne touche qu'au moment où la jambe se tend
	const ETMKickMode Mode = Movement && Movement->IsSliding() ? ETMKickMode::Slide : C->GetCharacterMovement()->IsFalling() ? ETMKickMode::Air : ETMKickMode::Front;
	const float Dur = Mode == ETMKickMode::Slide ? 0.42f : Mode == ETMKickMode::Air ? 0.46f : 0.56f;
	KickHitAt = Mode == ETMKickMode::Slide ? 0.07f : Mode == ETMKickMode::Air ? 0.17f : 0.25f;
	KickElapsed = 0.f;
	bKickDone = false;
	KickCooldown = Dur + 0.12f;
	if (Movement) { Movement->StartKickPose(Mode, Dur, KickHitAt); Movement->SpendStamina(0.06f); }
}

void UTMMeleeComponent::TickComponent(float Dt, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(Dt, TickType, ThisTickFunction);
	Cooldown -= Dt; SwitchT -= Dt; KickCooldown -= Dt;
	if (HitStopT > 0.f)
	{
		HitStopT -= FApp::GetDeltaTime();
		if (HitStopT <= 0.f) UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
	}
	if (!bKickDone)
	{
		KickElapsed += Dt;
		if (KickElapsed >= KickHitAt) { bKickDone = true; ResolveKick(); }
	}
	if (Strike != ETMStrike::None)
	{
		const FStrikeDef& D = StrikeDef(Strike);
		StrikeT += Dt;
		if (!bStrikeDone && StrikeT >= D.Hit) { bStrikeDone = true; ResolveStrike(); }
		if (StrikeT >= D.Dur) Strike = ETMStrike::None;
	}
	if (bHeld && Cooldown <= 0.f) StartStrike();
	if (Movement) Movement->ActionSlow = Strike != ETMStrike::None ? 0.8f : 1.f;
	if (ArmsRoot) AnimateArms(Dt);
}

bool UTMMeleeComponent::IsHead(AActor* Target, const FHitResult& Hit) const
{
	if (Hit.BoneName.ToString().Contains(TEXT("head"))) return true;
	FVector Origin, Extent;
	Target->GetActorBounds(true, Origin, Extent);
	return Hit.ImpactPoint.Z > Origin.Z + Extent.Z - 28.f;
}

AActor* UTMMeleeComponent::TraceTarget(const FVector& Start, const FVector& Dir, float Reach, FHitResult& OutHit, bool& bOutWall) const
{
	FCollisionQueryParams Params(SCENE_QUERY_STAT(TMMelee), false, GetOwner());
	FCollisionObjectQueryParams Obj;
	Obj.AddObjectTypesToQuery(ECC_Pawn);
	Obj.AddObjectTypesToQuery(ECC_PhysicsBody);
	Obj.AddObjectTypesToQuery(ECC_WorldStatic);
	Obj.AddObjectTypesToQuery(ECC_WorldDynamic);
	bOutWall = false;
	if (!GetWorld()->SweepSingleByObjectType(OutHit, Start, Start + Dir * Reach, FQuat::Identity, Obj, FCollisionShape::MakeSphere(12.f), Params)) return nullptr;
	AActor* A = OutHit.GetActor();
	if (A && A->IsA<APawn>()) return A;
	bOutWall = true;
	return nullptr;
}

void UTMMeleeComponent::DealDamage(AActor* Target, float Damage, bool bHead, const FVector& Dir, const FHitResult& Hit, FName Kind, float Push, float Lift)
{
	APawn* Owner = Cast<APawn>(GetOwner());
	UGameplayStatics::ApplyPointDamage(Target, Damage, Dir, Hit, Owner ? Owner->GetController() : nullptr, GetOwner(), UDamageType::StaticClass());
	if (ACharacter* C = Cast<ACharacter>(Target))
		if (Push > 0.f || Lift > 0.f) C->LaunchCharacter(Dir.GetSafeNormal2D() * Push + FVector(0.f, 0.f, Lift), false, Lift > 0.f);
	OnMeleeHit.Broadcast(Target, Damage, bHead, Kind);
}

void UTMMeleeComponent::DoHitStop(float Seconds)
{
	if (!bHitStop) return;
	HitStopT = Seconds;
	UGameplayStatics::SetGlobalTimeDilation(this, 0.1f);
}

void UTMMeleeComponent::ResolveStrike()
{
	if (!Camera) return;
	const FStrikeDef& D = StrikeDef(Strike);
	const FVector O = Camera->GetComponentLocation();
	const FVector F = Camera->GetForwardVector(), R = Camera->GetRightVector(), U = Camera->GetUpVector();
	const float Reach = D.Reach + 30.f, Span = D.bWide ? 0.5f : 0.26f;

	// éventail de rayons : l'arc du bras balaie un peu sur le côté et vers le bas
	AActor* Best = nullptr;
	FHitResult BestHit;
	float BestScore = 1e9f;
	bool bBestHead = false, bWall = false;
	for (int32 i = 0; i < 7; ++i)
		for (int32 v = 0; v < 2; ++v)
		{
			const float A = (i / 6.f - 0.5f) * 2.f * Span;
			const FVector Dir = (F + R * FMath::Tan(A) - U * (v ? 0.22f : 0.f)).GetSafeNormal();
			FHitResult H; bool bW;
			if (AActor* T = TraceTarget(O, Dir, Reach, H, bW))
			{
				const float Score = H.Distance + FMath::Abs(A) * 80.f + (v ? 25.f : 0.f);
				if (Score < BestScore) { BestScore = Score; Best = T; BestHit = H; bBestHead = !v && IsHead(T, H); }
			}
			bWall |= bW;
		}

	if (!Best)
	{
		if (bWall && Movement) Movement->AddShake(0.25f);
		return;
	}
	const float Hm = GetOwner()->GetVelocity().Size2D() / 100.f;
	float Dmg = D.Dmg * (bBestHead ? (D.bKnife ? 2.2f : 1.25f) : 1.f) + Hm * (D.bKnife ? 0.8f : 1.4f);
	if (IsTargetUnaware(Best)) Dmg *= D.bKnife ? KnifeSneakMultiplier : 2.f;
	DealDamage(Best, Dmg * DamageScale, bBestHead, F, BestHit, D.bKnife ? TEXT("knife") : TEXT("punch"), D.Push, D.bDown ? 250.f : 0.f);
	if (Movement) Movement->AddShake(D.bKnife ? 0.25f : 0.4f);
	DoHitStop(D.bKnife ? 0.035f : 0.05f);
}

void UTMMeleeComponent::ResolveKick()
{
	ACharacter* C = Cast<ACharacter>(GetOwner());
	if (!C) return;
	const ETMKickMode Mode = Movement ? Movement->GetKickMode() : ETMKickMode::Front;
	const bool bSlide = Mode == ETMKickMode::Slide, bAir = Mode == ETMKickMode::Air;
	const float Hs = C->GetVelocity().Size2D(), Hm = Hs / 100.f;
	const float Power = (KickDamage + Hm * 5.f + (bSlide || bAir ? 14.f : 0.f)) * DamageScale;
	const float Reach = (bSlide ? 220.f : bAir ? 240.f : 210.f) + 34.f;
	const FVector Loc = C->GetActorLocation();
	const FVector Fwd = FRotationMatrix(FRotator(0.f, C->GetControlRotation().Yaw, 0.f)).GetUnitAxis(EAxis::X);

	TArray<FOverlapResult> Overlaps;
	FCollisionObjectQueryParams Obj;
	Obj.AddObjectTypesToQuery(ECC_Pawn);
	Obj.AddObjectTypesToQuery(ECC_PhysicsBody);
	FCollisionQueryParams Params(SCENE_QUERY_STAT(TMKick), false, C);
	GetWorld()->OverlapMultiByObjectType(Overlaps, Loc, FQuat::Identity, Obj, FCollisionShape::MakeSphere(Reach), Params);

	// de face : la cible la plus proche dans l'axe ; en glissade : tout ce qui est devant les jambes
	TSet<AActor*> Seen;
	TArray<AActor*> Targets;
	AActor* Nearest = nullptr;
	float NearScore = 1e9f;
	for (const FOverlapResult& O : Overlaps)
	{
		AActor* A = O.GetActor();
		if (!A || A == C || !A->IsA<APawn>() || Seen.Contains(A)) continue;
		Seen.Add(A);
		const FVector To = A->GetActorLocation() - Loc;
		const float Dist = To.Size2D();
		if (Dist > Reach || To.Z < -120.f || To.Z > (bSlide ? 60.f : 130.f)) continue;
		const float Al = FVector::DotProduct(To.GetSafeNormal2D(), Fwd);
		if (Al < (bSlide ? 0.5f : 0.55f) && Dist > 80.f) continue;
		if (bSlide) Targets.Add(A);
		else { const float Sc = Dist * (1.6f - Al); if (Sc < NearScore) { NearScore = Sc; Nearest = A; } }
	}
	if (Nearest) Targets.Add(Nearest);

	for (AActor* A : Targets)
	{
		FHitResult H;
		H.ImpactPoint = A->GetActorLocation();
		H.Location = H.ImpactPoint;
		const float Dmg = IsTargetUnaware(A) ? Power * 2.5f : Power;
		DealDamage(A, Dmg, false, Fwd, H, TEXT("kick"), bSlide ? 500.f + Hs * 0.6f : 800.f + Hs * 0.9f, bSlide ? 250.f : bAir ? 550.f : 450.f);
	}
	if (Targets.Num())
	{
		if (Movement) Movement->AddShake(0.9f);
		DoHitStop(0.075f);
	}
	else
	{
		// coup de pied dans un mur : l'impact remonte dans la jambe
		FHitResult H;
		if (GetWorld()->LineTraceSingleByChannel(H, Loc, Loc + Fwd * 90.f, ECC_Visibility, Params))
		{
			if (Movement) Movement->AddShake(0.4f);
			C->GetCharacterMovement()->Velocity -= Fwd * 120.f;
		}
	}
}

// ---------- bras : poings en garde, couteau ----------
USceneComponent* UTMMeleeComponent::BuildArm(float Side)
{
	AActor* Owner = GetOwner();
	USceneComponent* Hand = TMMShapes::Pivot(Owner, ArmsRoot, FVector::ZeroVector);
	UMaterialInterface* Glove = TMMShapes::Mat(this, FLinearColor(0.035f, 0.03f, 0.026f));
	UMaterialInterface* Skin = TMMShapes::Mat(this, FLinearColor(0.42f, 0.2f, 0.13f));
	UMaterialInterface* Sleeve = TMMShapes::Mat(this, FLinearColor(0.07f, 0.075f, 0.045f));
	// poing fermé : dos de la main ganté, doigts repliés, pouce verrouillé devant
	TMMShapes::Add(Owner, Hand, TMMShapes::Cube(), FVector(2.f, 0.f, 1.f), FVector(9.f, 8.5f, 5.f), Glove);
	TMMShapes::Add(Owner, Hand, TMMShapes::Cube(), FVector(6.5f, 0.f, 1.2f), FVector(3.f, 8.8f, 3.4f), Glove);
	TMMShapes::Add(Owner, Hand, TMMShapes::Cylinder(), FVector(7.f, 0.f, -1.6f), FVector(4.6f, 4.6f, 8.4f), Skin, FRotator(0.f, 0.f, 90.f));
	TMMShapes::Add(Owner, Hand, TMMShapes::Cylinder(), FVector(7.8f, -Side * 1.2f, -4.f), FVector(2.6f, 2.6f, 5.2f), Skin, FRotator(0.f, 0.f, 90.f));
	TMMShapes::Add(Owner, Hand, TMMShapes::Sphere(), FVector(3.f, -Side * 4.4f, -2.2f), FVector(3.4f, 3.f, 3.f), Glove);
	TMMShapes::Add(Owner, Hand, TMMShapes::Cylinder(), FVector(-3.f, 0.f, 0.f), FVector(6.5f, 6.f, 4.f), Glove, FRotator(90.f, 0.f, 0.f));
	const FVector Wrist(-4.f, 0.f, 0.f), Elbow(-30.f, Side * 8.f, -26.f);
	TMMShapes::Limb(Owner, Hand, Wrist, Elbow, 6.8f, Skin);
	TMMShapes::Limb(Owner, Hand, FMath::Lerp(Wrist, Elbow, 0.55f), Elbow + (Elbow - Wrist) * 0.6f, 9.8f, Sleeve);
	return Hand;
}

void UTMMeleeComponent::BuildArms()
{
	AActor* Owner = GetOwner();
	ArmsRoot = TMMShapes::Pivot(Owner, Camera, FVector::ZeroVector);
	HandL = BuildArm(-1.f);
	HandR = BuildArm(1.f);
	UMaterialInterface* Steel = TMMShapes::Mat(this, FLinearColor(0.55f, 0.57f, 0.6f));
	UMaterialInterface* Edge = TMMShapes::Mat(this, FLinearColor(0.85f, 0.87f, 0.9f));
	UMaterialInterface* Dark = TMMShapes::Mat(this, FLinearColor(0.03f, 0.03f, 0.03f));
	UMaterialInterface* Grip = TMMShapes::Mat(this, FLinearColor(0.012f, 0.012f, 0.011f));
	// couteau de combat : manche, pommeau, garde, lame à dos droit et pointe relevée
	Knife = TMMShapes::Pivot(Owner, HandR, FVector(5.f, 0.f, -1.f), FRotator(10.f, 0.f, 0.f));
	TMMShapes::Add(Owner, Knife, TMMShapes::Cylinder(), FVector::ZeroVector, FVector(3.f, 2.6f, 12.f), Grip, FRotator(90.f, 0.f, 0.f));
	TMMShapes::Add(Owner, Knife, TMMShapes::Sphere(), FVector(-6.5f, 0.f, 0.f), FVector(3.2f, 3.2f, 3.2f), Dark);
	TMMShapes::Add(Owner, Knife, TMMShapes::Cube(), FVector(6.5f, 0.f, 0.f), FVector(0.9f, 2.4f, 6.2f), Dark);
	TMMShapes::Add(Owner, Knife, TMMShapes::Cube(), FVector(15.5f, 0.f, 0.4f), FVector(17.f, 0.5f, 3.f), Steel);
	TMMShapes::Add(Owner, Knife, TMMShapes::Cube(), FVector(15.f, 0.f, -1.3f), FVector(16.f, 0.55f, 0.7f), Edge);
	TMMShapes::Add(Owner, Knife, TMMShapes::Cube(), FVector(25.f, 0.f, 0.5f), FVector(4.6f, 0.5f, 2.2f), Steel, FRotator(22.f, 0.f, 0.f));

	TArray<USceneComponent*> Kids;
	ArmsRoot->GetChildrenComponents(true, Kids);
	for (USceneComponent* K : Kids)
		if (UPrimitiveComponent* P = Cast<UPrimitiveComponent>(K)) { P->SetOnlyOwnerSee(true); P->SetCastShadow(false); }
	ArmsRoot->SetVisibility(false, true);
}

void UTMMeleeComponent::AnimateArms(float Dt)
{
	const bool bShow = Equipped != ETMMeleeWeapon::None;
	ArmsRoot->SetVisibility(bShow, true);
	if (!bShow) return;
	Knife->SetVisibility(Equipped == ETMMeleeWeapon::Knife, true);

	APawn* Owner = Cast<APawn>(GetOwner());
	const FRotator CR = Owner ? Owner->GetControlRotation() : FRotator::ZeroRotator;
	const float DYaw = FRotator::NormalizeAxis(CR.Yaw - LastYaw), DPitch = FRotator::NormalizeAxis(CR.Pitch - LastPitch);
	LastYaw = CR.Yaw; LastPitch = CR.Pitch;
	// inertie des bras quand on tourne la tête
	SwayX += (FMath::Clamp(-DYaw * 1.5f, -4.f, 4.f) - SwayX) * FMath::Min(1.f, Dt * 10.f);
	SwayY += (FMath::Clamp(-DPitch * 1.5f, -4.f, 4.f) - SwayY) * FMath::Min(1.f, Dt * 10.f);

	const ACharacter* C = Cast<ACharacter>(GetOwner());
	const float Hm = GetOwner()->GetVelocity().Size2D() / 100.f;
	const bool bSlide = Movement && Movement->IsSliding();
	const bool bGround = C && C->GetCharacterMovement()->IsMovingOnGround() && !bSlide;
	const float Bob = Movement ? Movement->GetBobPhase() : 0.f;
	const float F = bGround ? FMath::Min(1.2f, Hm / 4.5f) : 0.f;
	const float Run = FMath::Clamp((Hm - 2.5f) / 3.f, 0.f, 1.f);
	const bool bKnife = Equipped == ETMMeleeWeapon::Knife;

	float Z = SwayY - FMath::Abs(FMath::Sin(Bob)) * 1.2f * F - (Movement ? Movement->GetDip() * 0.25f : 0.f);
	if (SwitchT > 0.f) Z -= FMath::Sin((1.f - SwitchT / 0.36f) * PI) * 40.f;
	if (Movement && Movement->IsRolling()) Z -= 35.f;
	float Yaw = 0.f, Roll = bSlide ? 7.f : 0.f;

	// garde : poings devant le visage ; couteau tenu bas, lame vers l'avant
	FVector R = bKnife ? FVector(40.f, 19.f, -19.f) : FVector(36.f, 16.f, -17.f), L(40.f, -16.f, -15.f);
	FRotator RR(bKnife ? 7.f : 0.f, 0.f, 0.f), LR = FRotator::ZeroRotator;
	if (bGround && Hm > 0.4f && Strike == ETMStrike::None)
	{
		// en courant, les bras balancent en opposition avec les jambes
		const float S = FMath::Sin(Bob), A = 3.f + Run * 7.f;
		R.Z += S * A - Run * 6.f; R.X -= S * A * 1.4f;
		L.Z -= S * A + Run * 5.f; L.X += S * A * 1.4f;
		RR.Pitch += -14.f * Run + 11.f * S * Run;
		LR.Pitch += -14.f * Run - 11.f * S * Run;
	}
	if (Strike != ETMStrike::None)
	{
		const FStrikeDef& D = StrikeDef(Strike);
		const float K = StrikeT / D.Dur, Hk = D.Hit / D.Dur;
		const float E = K < Hk ? Smooth01(K / Hk) : 1.f - Smooth01((K - Hk) / (1.f - Hk));
		switch (Strike)
		{
		case ETMStrike::Jab:
			L = FMath::Lerp(L, FVector(74.f, -3.f, -7.f), E); LR = FRotator(6.f * E, 6.f * E, 11.f * E); R.X -= 4.f * E;
			break;
		case ETMStrike::Cross:
			R = FMath::Lerp(R, FVector(76.f, 0.f, -7.f), E); RR = FRotator(6.f * E, -14.f * E, -20.f * E); L.X -= 6.f * E; Yaw = -4.6f * E;
			break;
		case ETMStrike::Hook:
		{
			const float A = K < Hk ? -0.6f + Smooth01(K / Hk) * 1.4f : 0.8f;
			L = FMath::Lerp(L, FVector(34.f + FMath::Cos(A) * 28.f, FMath::Sin(A) * 22.f, -8.f), E);
			LR = FRotator(0.f, 51.f * E * (A < 0.2f ? 1.f : 0.5f), 69.f * E); Yaw = 8.f * E;
			break;
		}
		case ETMStrike::Stab:
			R = FMath::Lerp(R, FVector(66.f, 4.f, -10.f), E); RR = FRotator(7.f - 5.7f * E, -8.6f * E, 0.f); L.X -= 5.f * E;
			break;
		case ETMStrike::Slash:
		{
			const float A = K < Hk ? Smooth01(K / Hk) : 1.f;
			R = FMath::Lerp(R, FVector(50.f, FMath::Lerp(34.f, -24.f, A), FMath::Lerp(-8.f, -16.f, A)), E);
			RR = FRotator(11.5f * E, -FMath::Lerp(34.f, -29.f, A) * E, FMath::Lerp(52.f, -40.f, A) * E); Yaw = -FMath::Lerp(5.7f, -6.9f, A) * E;
			break;
		}
		default: break;
		}
	}
	ArmsRoot->SetRelativeLocationAndRotation(FVector(0.f, SwayX + FMath::Cos(Bob) * 1.2f * F, Z), FRotator(0.f, Yaw, Roll));
	HandR->SetRelativeLocationAndRotation(R, RR);
	HandL->SetRelativeLocationAndRotation(L, LR);
}
