#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TMMovementComponent.generated.h"

class ACharacter;
class UCameraComponent;
class UCharacterMovementComponent;
class USceneComponent;

UENUM(BlueprintType)
enum class ETMKickMode : uint8 { Front, Air, Slide };

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FTMMoveSignal);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FTMFloatSignal, float, Value);

// Mouvements réalistes pour n'importe quel ACharacter : élan, sprint avec endurance, accroupi progressif,
// glissade freinée par le sol, roulade, réceptions lourdes, caméra au rythme des pas, jambes visibles.
// Le personnage garde ses propres entrées (AddMovementInput) : ce composant règle la vitesse, l'accélération
// et la caméra. Brancher Sprint / Crouch / Jump sur les fonctions ci-dessous.
UCLASS(ClassGroup = (ToitsMorts), meta = (BlueprintSpawnableComponent))
class TMMOUVEMENTS_API UTMMovementComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UTMMovementComponent();

	// ---------- vitesses (cm/s) ----------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Vitesses") float WalkSpeed = 310.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Vitesses") float SprintSpeed = 560.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Vitesses") float BackSpeed = 220.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Vitesses") float StrafeSpeed = 270.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Vitesses") float CrouchSpeed = 170.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Vitesses") float CrouchBackSpeed = 120.f;
	// < 1 avec une arme lourde, > 1 à mains nues
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Vitesses") float SpeedMultiplier = 1.f;

	// ---------- endurance (1 = pleine) ----------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Endurance") float SprintDrainPerSecond = 0.1f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Endurance") float RegenPerSecond = 0.2f;

	// ---------- glissade ----------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Glissade") float SlideMinSpeed = 460.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Glissade") float SlideBoost = 100.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Glissade") float SlideMaxSpeed = 740.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Glissade") float SlideFriction = 360.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Glissade") float SlideEndSpeed = 200.f;

	// ---------- sauts et chutes ----------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Sauts") float JumpVelocity = 420.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Sauts") float CrouchJumpVelocity = 340.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Sauts") float HardLandingSpeed = 850.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Sauts") float FallDamageSpeed = 1400.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Sauts") float FallDamagePerSpeed = 0.055f;
	// applique les dégâts de chute via ApplyDamage (sinon, seul l'événement OnFallDamage est envoyé)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Sauts") bool bApplyFallDamage = true;

	// ---------- caméra ----------
	// la caméra suit le regard + balancement, inclinaisons, secousses (désactive bUsePawnControlRotation)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Camera") bool bDriveCamera = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Camera") float CrouchEyeDrop = 57.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Camera") float SlideEyeDrop = 84.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Camera") float HeadBobScale = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Camera") bool bSpeedFov = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mouvements|Camera") bool bShowLegs = true;

	// ---------- événements ----------
	UPROPERTY(BlueprintAssignable, Category = "Mouvements") FTMMoveSignal OnSlideStarted;
	UPROPERTY(BlueprintAssignable, Category = "Mouvements") FTMMoveSignal OnRoll;
	UPROPERTY(BlueprintAssignable, Category = "Mouvements") FTMFloatSignal OnHardLanding;
	UPROPERTY(BlueprintAssignable, Category = "Mouvements") FTMFloatSignal OnFallDamage;
	UPROPERTY(BlueprintAssignable, Category = "Mouvements") FTMMoveSignal OnFootstep;

	// ---------- à brancher sur les entrées du personnage ----------
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void SprintPressed() { bSprintHeld = true; }
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void SprintReleased() { bSprintHeld = false; }
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void CrouchPressed();
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void CrouchReleased() { bCrouchHeld = false; }
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void JumpPressed();
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void JumpReleased();
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void SetCamera(UCameraComponent* InCamera);
	UFUNCTION(BlueprintCallable, Category = "Mouvements") void AddShake(float Amount) { Shake = FMath::Max(Shake, Amount); }

	UFUNCTION(BlueprintPure, Category = "Mouvements") float GetStamina() const { return Stamina; }
	UFUNCTION(BlueprintPure, Category = "Mouvements") bool IsSprinting() const { return bSprinting; }
	UFUNCTION(BlueprintPure, Category = "Mouvements") bool IsSliding() const { return bSliding; }
	UFUNCTION(BlueprintPure, Category = "Mouvements") bool IsRolling() const { return RollT > 0.f; }
	UFUNCTION(BlueprintPure, Category = "Mouvements") float GetSpeed() const;

	// utilisé par le composant de corps à corps
	UCameraComponent* GetCamera() const { return Camera; }
	float GetBobPhase() const { return BobPhase; }
	float GetDip() const { return DipSmooth; }
	void SpendStamina(float Amount) { Stamina = FMath::Max(0.f, Stamina - Amount); }
	void StartKickPose(ETMKickMode Mode, float Dur, float Hit) { KickMode = Mode; KickDur = Dur; KickHit = Hit; KickT = Dur; }
	bool IsKicking() const { return KickT > 0.f; }
	ETMKickMode GetKickMode() const { return KickMode; }
	float ActionSlow = 1.f;

protected:
	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	UFUNCTION() void HandleLanded(const FHitResult& Hit);

	void UpdateMovement(float Dt);
	void UpdateCamera(float Dt);
	void StartSlide(bool bBoost);
	void EndSlide();
	void BuildLegs();
	void PoseLeg(int32 Index, const FVector& Loc, float Hip, float Knee, float Ankle, float Yaw);
	void AnimateLegs();

	UPROPERTY() TObjectPtr<ACharacter> Character;
	UPROPERTY() TObjectPtr<UCharacterMovementComponent> Move;
	UPROPERTY() TObjectPtr<UCameraComponent> Camera;
	UPROPERTY() TArray<TObjectPtr<USceneComponent>> LegParts; // racine, genou, cheville × 2

	FVector CameraBase = FVector::ZeroVector;
	float StandEye = 162.f;
	float EyeHeight = 162.f;
	float DefaultFriction = 8.f;
	float DefaultBraking = 1600.f;
	float DefaultFov = 90.f;

	FVector2D MoveInput = FVector2D::ZeroVector;
	bool bSprintHeld = false;
	bool bCrouchHeld = false;
	float CrouchBuffer = 0.f;

	bool bSprinting = false;
	bool bSliding = false;
	float SlideT = 0.f;
	float SlideCooldown = 0.f;
	float RollT = 0.f;
	float Recover = 0.f;
	float Stamina = 1.f;
	float StaminaDelay = 0.f;
	float LastFallSpeed = 0.f;

	float BobPhase = 0.f;
	float Dip = 0.f;
	float DipSmooth = 0.f;
	float Lean = 0.f;
	float CamRoll = 0.f;
	float Shake = 0.f;
	float Fov = 90.f;

	float KickT = 0.f;
	float KickDur = 0.55f;
	float KickHit = 0.25f;
	ETMKickMode KickMode = ETMKickMode::Front;
};
