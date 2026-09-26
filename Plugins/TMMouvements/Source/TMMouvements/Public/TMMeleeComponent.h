#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TMMeleeComponent.generated.h"

class UTMMovementComponent;
class UCameraComponent;
class USceneComponent;

UENUM(BlueprintType)
enum class ETMMeleeWeapon : uint8 { None, Knife, Fists };

UENUM(BlueprintType)
enum class ETMStrike : uint8 { None, Jab, Cross, Hook, Stab, Slash };

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FTMMeleeHitSignal, AActor*, Target, float, Damage, bool, bHead, FName, Kind);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FTMEquipSignal, ETMMeleeWeapon, Weapon);

// Coup de pied (A), couteau et coups de poing, à côté de l'arme existante du jeu.
// Les dégâts passent par ApplyPointDamage : les ennemis les reçoivent dans leur événement AnyDamage / PointDamage.
UCLASS(Blueprintable, ClassGroup = (ToitsMorts), meta = (BlueprintSpawnableComponent))
class TMMOUVEMENTS_API UTMMeleeComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UTMMeleeComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Corps a corps") float DamageScale = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Corps a corps") float KickDamage = 34.f;
	// multiplicateur sur une cible qui ne vous a pas repéré (le couteau tue alors d'un coup)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Corps a corps") float KnifeSneakMultiplier = 20.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Corps a corps") bool bShowArms = true;
	// court arrêt sur image à l'impact
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Corps a corps") bool bHitStop = true;

	UPROPERTY(BlueprintAssignable, Category = "Corps a corps") FTMMeleeHitSignal OnMeleeHit;
	UPROPERTY(BlueprintAssignable, Category = "Corps a corps") FTMEquipSignal OnEquipChanged;

	// ---------- à brancher sur les entrées ----------
	// touche A : coup de pied (de face, sauté, ou balayage en glissade)
	UFUNCTION(BlueprintCallable, Category = "Corps a corps") void Kick();
	// clic quand le couteau ou les poings sont en main ; maintenir enchaîne les coups
	UFUNCTION(BlueprintCallable, Category = "Corps a corps") void AttackPressed();
	UFUNCTION(BlueprintCallable, Category = "Corps a corps") void AttackReleased() { bHeld = false; }
	// None = retour à l'arme du jeu
	UFUNCTION(BlueprintCallable, Category = "Corps a corps") void Equip(ETMMeleeWeapon Weapon);
	UFUNCTION(BlueprintPure, Category = "Corps a corps") ETMMeleeWeapon GetEquipped() const { return Equipped; }
	UFUNCTION(BlueprintPure, Category = "Corps a corps") bool IsMeleeEquipped() const { return Equipped != ETMMeleeWeapon::None; }

	// À redéfinir dans un Blueprint enfant pour les exécutions : la cible ne vous a-t-elle pas repéré ?
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Corps a corps") bool IsTargetUnaware(AActor* Target) const;

protected:
	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	void StartStrike();
	void ResolveStrike();
	void ResolveKick();
	void DealDamage(AActor* Target, float Damage, bool bHead, const FVector& Dir, const FHitResult& Hit, FName Kind, float Push, float Lift);
	AActor* TraceTarget(const FVector& Start, const FVector& Dir, float Reach, FHitResult& OutHit, bool& bOutWall) const;
	bool IsHead(AActor* Target, const FHitResult& Hit) const;
	void DoHitStop(float Seconds);
	void BuildArms();
	USceneComponent* BuildArm(float Side);
	void AnimateArms(float Dt);

	UPROPERTY() TObjectPtr<UTMMovementComponent> Movement;
	UPROPERTY() TObjectPtr<UCameraComponent> Camera;
	UPROPERTY() TObjectPtr<USceneComponent> ArmsRoot;
	UPROPERTY() TObjectPtr<USceneComponent> HandL;
	UPROPERTY() TObjectPtr<USceneComponent> HandR;
	UPROPERTY() TObjectPtr<USceneComponent> Knife;

	ETMMeleeWeapon Equipped = ETMMeleeWeapon::None;
	ETMStrike Strike = ETMStrike::None;
	float StrikeT = 0.f;
	bool bStrikeDone = true;
	bool bHeld = false;
	int32 Combo = 0;
	float LastStrikeTime = -10.f;
	float Cooldown = 0.f;
	float SwitchT = 0.f;
	float KickCooldown = 0.f;
	float KickElapsed = 0.f;
	float KickHitAt = 0.f;
	bool bKickDone = true;
	float HitStopT = 0.f;
	float LastYaw = 0.f;
	float LastPitch = 0.f;
	float SwayX = 0.f;
	float SwayY = 0.f;
};
