#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VPPorte.generated.h"

class UBoxComponent;
class USceneComponent;
class USoundBase;
class UStaticMeshComponent;

/**
 * Porte d'entrée d'une maison visitable, placée par « Construire le village provençal ».
 * Le vantail pivote autour de sa charnière (l'origine de l'acteur) : il s'ouvre vers l'intérieur de la maison.
 *
 * - Ouverture automatique quand le joueur s'approche (bOuvertureAuto), sans fermeture automatique par défaut.
 * - Ouvrir / Fermer / Basculer depuis un Blueprint, ou BasculerPorteProche() branché sur une touche « Interagir ».
 * - Verrouillée : la porte ne s'ouvre plus (maison barricadée, objectif de mission...).
 * Pendant le mouvement, le vantail ne bloque pas les personnages (pas de joueur coincé contre la porte).
 */
UCLASS(HideCategories = (Replication, Input, LOD, Cooking, Networking, HLOD))
class VILLAGEPROVENCE_API AVPPorte : public AActor
{
	GENERATED_BODY()

public:
	AVPPorte();

	/** Charnière (origine de l'acteur). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Porte")
	TObjectPtr<USceneComponent> Charniere;

	/** Vantail : pivote autour de la charnière. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Porte")
	TObjectPtr<UStaticMeshComponent> Vantail;

	/** Zone de détection devant et derrière la porte (ouverture automatique). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Porte")
	TObjectPtr<UBoxComponent> Detection;

	/** Angle d'ouverture (degrés, autour de la verticale ; négatif = vers l'intérieur pour les portes du village). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte")
	float AngleOuverture = -100.f;

	/** Vitesse d'ouverture (degrés par seconde). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte", meta = (ClampMin = "10"))
	float Vitesse = 160.f;

	/** La porte s'ouvre quand un joueur entre dans la zone de détection. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte")
	bool bOuvertureAuto = true;

	/** Les personnages non joueurs (zombies, survivants) ouvrent aussi la porte en s'approchant. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte")
	bool bOuvertureParIA = false;

	/** La porte se referme toute seule quand plus personne n'est à proximité. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte")
	bool bFermetureAuto = false;

	/** Délai avant la fermeture automatique (secondes). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte", meta = (EditCondition = "bFermetureAuto"))
	float DelaiFermeture = 3.f;

	/** Porte verrouillée : Ouvrir() et l'ouverture automatique sont sans effet. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte")
	bool bVerrouillee = false;

	/** État au lancement du jeu. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte")
	bool bOuverteAuDepart = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte|Sons")
	TObjectPtr<USoundBase> SonOuverture;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Porte|Sons")
	TObjectPtr<USoundBase> SonFermeture;

	/** Maison à laquelle appartient la porte (identifiant du bâtiment). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Porte")
	FString Maison;

	UFUNCTION(BlueprintCallable, Category = "Village provençal|Porte")
	void Ouvrir();

	UFUNCTION(BlueprintCallable, Category = "Village provençal|Porte")
	void Fermer();

	UFUNCTION(BlueprintCallable, Category = "Village provençal|Porte")
	void Basculer();

	/** Vrai si la porte est ouverte ou en train de s'ouvrir. */
	UFUNCTION(BlueprintPure, Category = "Village provençal|Porte")
	bool EstOuverte() const { return bCibleOuverte; }

	/** Change l'état sans animation (placement dans l'éditeur, chargement d'une sauvegarde). */
	UFUNCTION(BlueprintCallable, Category = "Village provençal|Porte")
	void DefinirEtat(bool bOuverte);

	/**
	 * Ouvre ou ferme la porte la plus proche de Qui (dans le rayon, en cm), par exemple sur une touche « Interagir ».
	 * Renvoie la porte actionnée, ou nul s'il n'y en a pas.
	 */
	UFUNCTION(BlueprintCallable, Category = "Village provençal|Porte", meta = (DefaultToSelf = "Qui"))
	static AVPPorte* BasculerPorteProche(AActor* Qui, float Rayon = 220.f);

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;
	virtual void OnConstruction(const FTransform& Transform) override;

private:
	UFUNCTION()
	void OnDetectionDebut(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index, bool bFromSweep, const FHitResult& Hit);

	UFUNCTION()
	void OnDetectionFin(UPrimitiveComponent* Comp, AActor* Autre, UPrimitiveComponent* AutreComp, int32 Index);

	bool Declenche(const AActor* Autre) const;
	void AppliquerAngle(float Angle);
	void DebutMouvement();
	void FinMouvement();

	float Angle = 0.f;
	bool bCibleOuverte = false;
	bool bEnMouvement = false;
	float TempsSansPresence = 0.f;
	int32 Presents = 0;
};
