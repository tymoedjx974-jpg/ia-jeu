#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TMParkourComponent.generated.h"

class ACharacter;
class UCharacterMovementComponent;
class UPrimitiveComponent;
class UTMMovementComponent;

UENUM(BlueprintType)
enum class ETMParkourState : uint8
{
	None,
	Mantle,     // se hisser sur un rebord
	Vault,      // franchir un obstacle bas en courant
	Ladder      // monter ou descendre une échelle
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FTMParkourSignal, ETMParkourState, State);

// Parkour pour n'importe quel ACharacter : attraper un rebord et se hisser (murs, toits, balcons, caisses),
// franchir un obstacle bas en courant (voitures, sacs de sable, barrières, murets), monter aux échelles
// (composants portant l'étiquette TM_Echelle) et se hisser sur le toit en haut de l'échelle.
// Avec UTMMovementComponent, la touche Saut déclenche le parkour automatiquement ; sinon, appeler TryParkour()
// sur l'appui de Saut et ne sauter que s'il renvoie faux.
UCLASS(ClassGroup = (ToitsMorts), meta = (BlueprintSpawnableComponent))
class TMMOUVEMENTS_API UTMParkourComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UTMParkourComponent();

	// ---------- rebords (cm, au-dessus des pieds) ----------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Rebords") float MantleMinHeight = 45.f;
	// depuis le sol, en appuyant sur Saut (saut + traction)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Rebords") float MantleMaxHeightGround = 230.f;
	// en l'air, par rapport à la position des pieds à cet instant (bras tendus)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Rebords") float MantleMaxHeightAir = 190.f;
	// en l'air, attrape les rebords sans appuyer sur Saut quand on avance vers le mur
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Rebords") bool bAutoMantle = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Rebords") float MantleSpeed = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Rebords") float MantleStamina = 0.07f;

	// ---------- franchissement ----------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Franchissement") bool bAutoVault = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Franchissement") float VaultMinHeight = 40.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Franchissement") float VaultMaxHeight = 130.f;
	// épaisseur maximale de l'obstacle (une voiture fait 170 cm de large)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Franchissement") float VaultMaxDepth = 190.f;
	// vitesse minimale (cm/s) : le franchissement se fait en courant
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Franchissement") float VaultMinSpeed = 330.f;

	// ---------- échelles ----------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Echelles") FName LadderTag = FName(TEXT("TM_Echelle"));
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parkour|Echelles") float ClimbSpeed = 170.f;

	// ---------- événements ----------
	UPROPERTY(BlueprintAssignable, Category = "Parkour") FTMParkourSignal OnParkourStarted;
	UPROPERTY(BlueprintAssignable, Category = "Parkour") FTMParkourSignal OnParkourEnded;

	// à appeler sur l'appui de Saut ; renvoie vrai si une figure de parkour a commencé (ne pas sauter alors)
	UFUNCTION(BlueprintCallable, Category = "Parkour") bool TryParkour();
	UFUNCTION(BlueprintPure, Category = "Parkour") ETMParkourState GetState() const { return State; }
	UFUNCTION(BlueprintPure, Category = "Parkour") bool IsBusy() const { return State != ETMParkourState::None; }

protected:
	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	bool Trace(const FVector& A, const FVector& B, FHitResult& Hit) const;
	bool Sweep(const FVector& A, const FVector& B, float Radius, FHitResult& Hit) const;
	bool CapsuleFits(const FVector& Center) const;
	FVector Facing() const;
	bool FindLedge(float MaxHeight, bool bCheckHeadroom, FVector& OutTarget, float& OutHeight) const;
	bool FindVault(FVector& OutOver, FVector& OutLanding) const;
	bool FindLadder(FHitResult& OutHit) const;
	void StartMove(ETMParkourState NewState, const TArray<FVector>& Points, float Duration, const FVector& ExitVelocity);
	void TickMove(float Dt);
	void EnterLadder(const FHitResult& Hit);
	void TickLadder(float Dt);
	void EndState(bool bWalking, const FVector& ExitVelocity);

	UPROPERTY() TObjectPtr<ACharacter> Character;
	UPROPERTY() TObjectPtr<UCharacterMovementComponent> Move;
	UPROPERTY() TObjectPtr<UTMMovementComponent> TMMove;

	ETMParkourState State = ETMParkourState::None;
	TArray<FVector> Path;
	TArray<float> PathT;
	float MoveT = 0.f;
	float MoveDur = 0.f;
	FVector MoveExitVelocity = FVector::ZeroVector;
	FVector LadderNormal = FVector::ZeroVector;
	FVector LadderAnchor = FVector::ZeroVector;
	float Cooldown = 0.f;
};
