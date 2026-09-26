#include "TMMovementComponent.h"

#include "TMMShapes.h"

#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	float Smooth01(float T) { T = FMath::Clamp(T, 0.f, 1.f); return T * T * (3.f - 2.f * T); }
	float EaseInOut(float T) { return T < 0.5f ? 2.f * T * T : 1.f - FMath::Pow(-2.f * T + 2.f, 2.f) / 2.f; }
	constexpr float RollDuration = 0.6f;
}

UTMMovementComponent::UTMMovementComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

float UTMMovementComponent::GetSpeed() const
{
	return Move ? Move->Velocity.Size2D() : 0.f;
}

void UTMMovementComponent::BeginPlay()
{
	Super::BeginPlay();
	Character = Cast<ACharacter>(GetOwner());
	if (!Character)
	{
		UE_LOG(LogTemp, Warning, TEXT("TMMovementComponent doit être ajouté à un Character."));
		SetComponentTickEnabled(false);
		return;
	}
	Move = Character->GetCharacterMovement();
	Move->GetNavAgentPropertiesRef().bCanCrouch = true;
	Move->bCanWalkOffLedgesWhenCrouching = true;
	DefaultFriction = Move->GroundFriction;
	DefaultBraking = Move->BrakingDecelerationWalking;
	Character->LandedDelegate.AddDynamic(this, &UTMMovementComponent::HandleLanded);
	SetCamera(Camera ? Camera.Get() : Character->FindComponentByClass<UCameraComponent>());
}

void UTMMovementComponent::SetCamera(UCameraComponent* InCamera)
{
	Camera = InCamera;
	if (!Camera || !Character) return;
	CameraBase = Camera->GetRelativeLocation();
	// hauteur des yeux au-dessus des pieds, personnage debout
	StandEye = CameraBase.Z + Character->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
	EyeHeight = StandEye;
	DefaultFov = Camera->FieldOfView;
	Fov = DefaultFov;
	if (bDriveCamera) Camera->bUsePawnControlRotation = false;
	if (bShowLegs && LegParts.Num() == 0) BuildLegs();
}

void UTMMovementComponent::CrouchPressed()
{
	bCrouchHeld = true;
	CrouchBuffer = 0.3f;
}

void UTMMovementComponent::JumpPressed()
{
	if (!Character || RollT > 0.f) return;
	const float Tired = Stamina < 0.1f ? 0.9f : 1.f;
	if (bSliding)
	{
		// saut en sortie de glissade : on garde l'élan
		EndSlide();
		Move->JumpZVelocity = (JumpVelocity - 20.f) * Tired;
		const float Hs = GetSpeed();
		if (Hs > 1.f) { const float K = (Hs + 30.f) / Hs; Move->Velocity.X *= K; Move->Velocity.Y *= K; }
	}
	else Move->JumpZVelocity = (Character->bIsCrouched ? CrouchJumpVelocity : JumpVelocity) * Tired;
	// un personnage accroupi ne peut pas sauter : on se relève tout de suite
	if (Character->bIsCrouched) { Move->bWantsToCrouch = false; Move->UnCrouch(false); }
	if (Character->CanJump()) SpendStamina(0.06f);
	Character->Jump();
}

void UTMMovementComponent::JumpReleased()
{
	if (Character) Character->StopJumping();
}

void UTMMovementComponent::TickComponent(float Dt, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(Dt, TickType, ThisTickFunction);
	if (!Character || !Move) return;
	CrouchBuffer -= Dt; SlideCooldown -= Dt; Recover -= Dt;
	if (KickT > 0.f) KickT -= Dt;
	UpdateMovement(Dt);
	if (Camera) UpdateCamera(Dt);
	if (LegParts.Num()) AnimateLegs();
}

void UTMMovementComponent::UpdateMovement(float Dt)
{
	const bool bGround = Move->IsMovingOnGround();
	const float Hs = GetSpeed();
	if (Move->IsFalling()) LastFallSpeed = FMath::Max(0.f, -Move->Velocity.Z);

	// direction voulue par le joueur, dans son repère (avant / côté)
	const FRotator YawRot(0.f, Character->GetControlRotation().Yaw, 0.f);
	const FVector Fwd = FRotationMatrix(YawRot).GetUnitAxis(EAxis::X);
	const FVector Right = FRotationMatrix(YawRot).GetUnitAxis(EAxis::Y);
	const FVector In = Character->GetLastMovementInputVector().GetClampedToMaxSize(1.f);
	MoveInput = FVector2D(FVector::DotProduct(In, Right), FVector::DotProduct(In, Fwd));

	// endurance : le sprint fatigue, on récupère après une courte pause
	bSprinting = bSprintHeld && MoveInput.Y > 0.1f && Stamina > 0.02f && !bCrouchHeld && bGround && !bSliding && RollT <= 0.f;
	if (bSprinting && Hs > 100.f) { Stamina = FMath::Max(0.f, Stamina - SprintDrainPerSecond * Dt); StaminaDelay = 0.9f; }
	else { StaminaDelay -= Dt; if (StaminaDelay <= 0.f) Stamina = FMath::Min(1.f, Stamina + RegenPerSecond * Dt); }

	if (RollT > 0.f)
	{
		RollT -= Dt;
		if (RollT <= 0.f && bCrouchHeld && Hs > 400.f) StartSlide(false);
	}

	// glissade : il faut de l'élan, courte poussée, puis le frottement du sol freine
	if (!bSliding && bGround && CrouchBuffer > 0.f && Hs > SlideMinSpeed && RollT <= 0.f && Recover <= 0.f)
	{
		CrouchBuffer = 0.f;
		StartSlide(true);
	}
	if (bSliding)
	{
		if (!bGround || !bCrouchHeld || Hs < SlideEndSpeed)
		{
			EndSlide();
			if (bGround && !bCrouchHeld) Recover = FMath::Max(Recover, 0.18f);
		}
		else
		{
			SlideT += Dt;
			const float Dec = (SlideFriction + Hs * 0.18f + (SlideT > 0.9f ? 300.f : 0.f)) * Dt;
			const float Ns = FMath::Max(0.f, Hs - Dec);
			FVector H(Move->Velocity.X, Move->Velocity.Y, 0.f);
			H *= Hs > 1.f ? Ns / Hs : 0.f;
			// dans une pente, la gravité entraîne la glissade
			if (Move->CurrentFloor.bBlockingHit)
			{
				const FVector N = Move->CurrentFloor.HitResult.ImpactNormal;
				const FVector G(0.f, 0.f, -980.f);
				FVector Along = G - N * FVector::DotProduct(G, N);
				Along.Z = 0.f;
				H += Along * 0.8f * Dt;
			}
			// on ne dirige presque plus
			H += (Fwd * MoveInput.Y + Right * MoveInput.X) * 90.f * Dt;
			Move->Velocity.X = H.X;
			Move->Velocity.Y = H.Y;
		}
	}

	const bool bWantLow = bSliding || bCrouchHeld || RollT > 0.f;
	if (bWantLow && !Character->bIsCrouched) Character->Crouch();
	else if (!bWantLow && Character->bIsCrouched) Character->UnCrouch();

	if (bSliding || RollT > 0.f)
	{
		// pendant une glissade ou une roulade, les entrées n'accélèrent plus le corps
		Move->MaxAcceleration = 0.f;
		return;
	}

	float Target;
	if (Character->bIsCrouched) Target = MoveInput.Y < -0.1f ? CrouchBackSpeed : CrouchSpeed;
	else if (MoveInput.Y < -0.1f) Target = BackSpeed;
	else if (FMath::Abs(MoveInput.Y) < 0.1f && FMath::Abs(MoveInput.X) > 0.1f) Target = StrafeSpeed;
	else Target = bSprinting ? SprintSpeed : WalkSpeed;
	Target *= SpeedMultiplier * ActionSlow;
	if (bSprinting && Stamina < 0.3f) Target *= 0.8f + Stamina * 0.66f;
	if (Recover > 0.f) Target *= 0.45f;
	if (KickT > 0.f && KickMode == ETMKickMode::Front) Target *= 0.3f;
	Move->MaxWalkSpeed = Target;
	Move->MaxWalkSpeedCrouched = Target;

	// l'élan : départ vif, accélération plus lente près de la vitesse de pointe, virages larges en sprint
	const float Frac = FMath::Clamp((Hs - 250.f) / 310.f, 0.f, 1.f);
	Move->MaxAcceleration = FMath::Lerp(1900.f, 650.f, Frac);
	Move->GroundFriction = FMath::Lerp(DefaultFriction, 2.5f, Frac);
	Move->BrakingDecelerationWalking = In.IsNearlyZero() ? DefaultBraking : 700.f;
}

void UTMMovementComponent::StartSlide(bool bBoost)
{
	bSliding = true;
	SlideT = 0.f;
	SpendStamina(0.05f);
	const float Hs = GetSpeed();
	if (bBoost && SlideCooldown <= 0.f && Hs > 1.f)
	{
		const float K = FMath::Min(SlideMaxSpeed, Hs + SlideBoost) / Hs;
		Move->Velocity.X *= K; Move->Velocity.Y *= K;
		SlideCooldown = 1.2f;
	}
	// plus de freinage automatique : le frottement est appliqué à la main
	Move->GroundFriction = 0.f;
	Move->BrakingDecelerationWalking = 0.f;
	Move->MaxWalkSpeed = 2000.f;
	Move->MaxWalkSpeedCrouched = 2000.f;
	Character->Crouch();
	Dip = FMath::Max(Dip, 10.f);
	OnSlideStarted.Broadcast();
}

void UTMMovementComponent::EndSlide()
{
	bSliding = false;
	Move->GroundFriction = DefaultFriction;
	Move->BrakingDecelerationWalking = DefaultBraking;
}

void UTMMovementComponent::HandleLanded(const FHitResult& Hit)
{
	const float S = LastFallSpeed;
	LastFallSpeed = 0.f;
	const float Hs = GetSpeed();

	// roulade : s'accroupir juste avant de toucher le sol, aucun dégât
	if (S > HardLandingSpeed && CrouchBuffer > 0.f)
	{
		RollT = RollDuration;
		CrouchBuffer = 0.f;
		const FVector Fwd = FRotationMatrix(FRotator(0.f, Character->GetControlRotation().Yaw, 0.f)).GetUnitAxis(EAxis::X);
		const float Sp = FMath::Max(Hs, 420.f);
		Move->Velocity.X = Fwd.X * Sp; Move->Velocity.Y = Fwd.Y * Sp;
		OnRoll.Broadcast();
		return;
	}
	// atterrissage accroupi avec de l'élan : on enchaîne sur une glissade
	if (bCrouchHeld && Hs > 440.f && S <= HardLandingSpeed) { StartSlide(false); return; }

	Dip = FMath::Min(45.f, S * 0.028f);
	if (S > 600.f) { Move->Velocity.X *= 0.7f; Move->Velocity.Y *= 0.7f; }
	// réception lourde : les jambes encaissent, on repart plus lentement
	if (S > HardLandingSpeed)
	{
		Recover = FMath::Min(0.55f, 0.15f + (S - HardLandingSpeed) * 0.0006f);
		Shake = FMath::Max(Shake, 0.35f);
		OnHardLanding.Broadcast(S);
	}
	if (S > FallDamageSpeed)
	{
		const float Dmg = (S - FallDamageSpeed) * FallDamagePerSpeed;
		OnFallDamage.Broadcast(Dmg);
		if (bApplyFallDamage) UGameplayStatics::ApplyDamage(Character, Dmg, Character->GetController(), Character, nullptr);
	}
}

void UTMMovementComponent::UpdateCamera(float Dt)
{
	const float Hm = GetSpeed() / 100.f;
	const bool bGround = Move->IsMovingOnGround();
	const bool bCrouch = Character->bIsCrouched && !bSliding;
	const float Run = FMath::Clamp((Hm - 3.4f) / 2.2f, 0.f, 1.f);
	const float Time = GetWorld()->GetTimeSeconds();

	// on s'accroupit et on se relève en ~0,2 s ; la glissade fait tomber le regard d'un coup
	const float EyeT = RollT > 0.f ? StandEye - 92.f : bSliding ? StandEye - SlideEyeDrop : Character->bIsCrouched ? StandEye - CrouchEyeDrop : StandEye;
	const float Rate = (bSliding || RollT > 0.f) ? 16.f : (EyeT > EyeHeight ? 7.f : 10.f);
	EyeHeight += (EyeT - EyeHeight) * FMath::Min(1.f, Dt * Rate);

	float BZ = 0.f, BY = 0.f, BobRoll = 0.f, BobPitch = 0.f;
	if (bGround && !bSliding && Hm > 0.3f && RollT <= 0.f)
	{
		// cadence réelle : ~2 pas/s en marchant, ~3 en sprint, plus lente accroupi ; tête au plus bas à l'appui
		const float Cad = bCrouch ? 1.3f + Hm * 0.4f : 1.5f + Hm * 0.28f;
		const float Prev = BobPhase;
		BobPhase += Dt * PI * Cad;
		const float F = FMath::Min(1.15f, Hm / 4.2f) * (bCrouch ? 0.55f : 1.f) * HeadBobScale;
		const float Sn = FMath::Abs(FMath::Sin(BobPhase));
		BZ = (Sn * 5.f + Run * Sn * Sn * 3.5f) * F - 3.f * F;
		BY = FMath::Cos(BobPhase) * (2.8f + Run * 1.2f) * F;
		BobRoll = FMath::Cos(BobPhase) * (0.46f + Run * 0.57f) * F;
		BobPitch = (0.5f - Sn) * (0.34f + Run * 0.69f) * F;
		if (FMath::FloorToInt(Prev / PI) != FMath::FloorToInt(BobPhase / PI)) { Dip += (0.6f + Run * 1.4f) * F; OnFootstep.Broadcast(); }
	}
	else if (bGround && !bSliding)
	{
		// à l'arrêt : la respiration, plus ample quand on est essoufflé
		BZ = FMath::Sin(Time * (1.4f + (1.f - Stamina) * 2.2f)) * (0.3f + (1.f - Stamina) * 1.2f) * HeadBobScale;
	}
	DipSmooth += (Dip - DipSmooth) * FMath::Min(1.f, Dt * 25.f);
	Dip *= FMath::Exp(-Dt * 7.f);

	const float Half = Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	Camera->SetRelativeLocation(FVector(CameraBase.X, CameraBase.Y + BY, EyeHeight - Half + BZ - DipSmooth));

	if (bSpeedFov)
	{
		const float FovT = DefaultFov + FMath::Clamp((Hm - 4.8f) * 2.6f, 0.f, 10.f) + (bSliding ? 3.f : 0.f);
		Fov += (FovT - Fov) * FMath::Min(1.f, Dt * 5.f);
		Camera->SetFieldOfView(Fov);
	}
	if (!bDriveCamera) return;

	// buste penché en avant en sprint, en arrière en glissade
	const float LeanT = (bSprinting && bGround ? -2.6f * Run : 0.f) + (bSliding ? 2.9f : 0.f) + (Recover > 0.f ? -3.4f : 0.f);
	Lean += (LeanT - Lean) * FMath::Min(1.f, Dt * 6.f);
	const float RollTarget = (bSliding ? 3.4f : 0.f) - MoveInput.X + BobRoll;
	CamRoll += (RollTarget - CamRoll) * FMath::Min(1.f, Dt * 8.f);

	float PitchOff = 0.f;
	if (RollT > 0.f) PitchOff -= 360.f * EaseInOut(1.f - RollT / RollDuration);
	if (KickT > 0.f && KickMode == ETMKickMode::Front) PitchOff -= FMath::Sin((1.f - KickT / KickDur) * PI) * 1.7f;
	const float Sh = Shake;
	Shake *= FMath::Exp(-Dt * 9.f);

	FRotator R = Character->GetControlRotation();
	R.Pitch += PitchOff + BobPitch + Lean + FMath::FRandRange(-1.f, 1.f) * Sh * 0.9f;
	R.Yaw += FMath::FRandRange(-1.f, 1.f) * Sh * 0.9f;
	R.Roll = CamRoll;
	Camera->SetWorldRotation(R);
}

// ---------- jambes visibles pendant les glissades et les coups de pied ----------
void UTMMovementComponent::BuildLegs()
{
	AActor* Owner = GetOwner();
	UMaterialInterface* Pants = TMMShapes::Mat(this, FLinearColor(0.045f, 0.045f, 0.035f));
	UMaterialInterface* Boot = TMMShapes::Mat(this, FLinearColor(0.05f, 0.028f, 0.015f));
	UMaterialInterface* Sole = TMMShapes::Mat(this, FLinearColor(0.01f, 0.01f, 0.01f));
	for (float Side : { 1.f, -1.f })
	{
		USceneComponent* Root = TMMShapes::Pivot(Owner, Camera, FVector(-6.f, Side * 11.f, -60.f));
		TMMShapes::Limb(Owner, Root, FVector::ZeroVector, FVector(0.f, 0.f, -47.f), 19.f, Pants);
		USceneComponent* Knee = TMMShapes::Pivot(Owner, Root, FVector(0.f, 0.f, -45.f));
		TMMShapes::Add(Owner, Knee, TMMShapes::Sphere(), FVector::ZeroVector, FVector(17.f, 16.5f, 17.f), Pants);
		TMMShapes::Limb(Owner, Knee, FVector::ZeroVector, FVector(0.f, 0.f, -44.f), 15.f, Pants);
		USceneComponent* Ankle = TMMShapes::Pivot(Owner, Knee, FVector(0.f, 0.f, -44.f));
		TMMShapes::Add(Owner, Ankle, TMMShapes::Cylinder(), FVector(0.f, 0.f, 4.f), FVector(13.5f, 12.5f, 20.f), Boot);
		TMMShapes::Add(Owner, Ankle, TMMShapes::Cylinder(), FVector(7.5f, 0.f, -3.f), FVector(10.5f, 11.5f, 29.f), Boot, FRotator(90.f, 0.f, 0.f));
		TMMShapes::Add(Owner, Ankle, TMMShapes::Cube(), FVector(7.f, 0.f, -8.5f), FVector(30.f, 12.f, 2.6f), Sole);
		TMMShapes::Add(Owner, Ankle, TMMShapes::Cube(), FVector(-4.f, 0.f, -9.f), FVector(8.f, 12.f, 4.f), Sole);
		for (int32 k = 0; k < 4; ++k)
			TMMShapes::Add(Owner, Ankle, TMMShapes::Cube(), FVector(7.f + k * 1.2f, 0.f, 3.f - k * 2.8f), FVector(1.f, 6.f, 0.8f), Sole, FRotator(-28.f, 0.f, 0.f));
		TArray<USceneComponent*> Kids;
		Root->GetChildrenComponents(true, Kids);
		for (USceneComponent* C : Kids)
			if (UPrimitiveComponent* P = Cast<UPrimitiveComponent>(C)) { P->SetOnlyOwnerSee(true); P->SetCastShadow(false); }
		Root->SetVisibility(false, true);
		LegParts.Add(Root); LegParts.Add(Knee); LegParts.Add(Ankle);
	}
}

void UTMMovementComponent::PoseLeg(int32 Index, const FVector& Loc, float Hip, float Knee, float Ankle, float Yaw)
{
	USceneComponent* Root = LegParts[Index * 3];
	Root->SetVisibility(true, true);
	Root->SetRelativeLocationAndRotation(Loc, FRotator(FMath::RadiansToDegrees(Hip), FMath::RadiansToDegrees(Yaw), 0.f));
	LegParts[Index * 3 + 1]->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(Knee), 0.f, 0.f));
	LegParts[Index * 3 + 2]->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(Ankle), 0.f, 0.f));
}

void UTMMovementComponent::AnimateLegs()
{
	LegParts[0]->SetVisibility(false, true);
	LegParts[3]->SetVisibility(false, true);
	if (KickT > 0.f)
	{
		const float K = 1.f - KickT / KickDur, Hk = KickHit / KickDur;
		if (KickMode == ETMKickMode::Slide)
		{
			const float E = Smooth01(K / FMath::Max(0.01f, Hk)), Back = Smooth01((K - 0.6f) / 0.4f);
			PoseLeg(0, FVector(-2.f, 10.f, -46.f), FMath::Lerp(1.2f, 1.56f, E) - Back * 0.2f, FMath::Lerp(-0.8f, 0.f, E) - Back * 0.5f, -0.25f * E, 0.f);
			PoseLeg(1, FVector(-8.f, -13.f, -50.f), 1.05f, -1.9f, 0.f, -0.3f);
			return;
		}
		// armé : genou monté, jambe repliée ; extension brutale jusqu'à l'impact ; tenue ; retour
		const float Ch = Smooth01(K / (Hk * 0.6f)), Ex = Smooth01((K - Hk * 0.6f) / (Hk * 0.4f)), Back = Smooth01((K - Hk - 0.15f) / (0.85f - Hk));
		const bool bAir = KickMode == ETMKickMode::Air;
		const float Hip = FMath::Lerp(FMath::Lerp(0.15f, 1.3f, Ch), bAir ? 1.62f : 1.75f, Ex) * (1.f - Back) + Back * 0.3f;
		const float Knee = FMath::Lerp(FMath::Lerp(-0.3f, -2.f, Ch), 0.f, Ex) * (1.f - Back) - Back * 1.3f;
		PoseLeg(0, FVector(-6.f, 11.f, -60.f + Ex * (1.f - Back) * 10.f), Hip, Knee, -0.15f * Ex * (1.f - Back), 0.08f);
		if (bAir) PoseLeg(1, FVector(-10.f, -12.f, -62.f), 0.9f, -1.6f, 0.f, -0.2f);
		return;
	}
	if (bSliding)
	{
		// jambe d'appui tendue devant, l'autre repliée dessous, vibrations du sol
		const float V = FMath::Sin(GetWorld()->GetTimeSeconds() * 38.f) * 1.2f;
		PoseLeg(0, FVector(-2.f, 10.f, -47.f + V), 1.5f, -0.08f, -0.2f, 0.f);
		PoseLeg(1, FVector(-10.f, -13.f, -50.f + V), 1.08f, -1.95f, 0.f, -0.32f);
	}
}
