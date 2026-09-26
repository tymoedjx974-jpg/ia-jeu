#pragma once

#include "CoreMinimal.h"

class AActor;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UMaterialInterface;

// Pièces visibles construites à partir des formes de base du moteur (cube, cylindre, sphère de 100 cm) :
// le projet n'a besoin d'aucun fichier binaire.
namespace TMMShapes
{
	UStaticMesh* Cube();
	UStaticMesh* Cylinder();
	UStaticMesh* Sphere();

	UMaterialInterface* Mat(UObject* Outer, const FLinearColor& Color);

	USceneComponent* Pivot(AActor* Owner, USceneComponent* Parent, const FVector& Loc, const FRotator& Rot = FRotator::ZeroRotator);

	// SizeCm : dimensions finales en centimètres (le cylindre est orienté selon Z)
	UStaticMeshComponent* Add(AActor* Owner, USceneComponent* Parent, UStaticMesh* Mesh, const FVector& Loc, const FVector& SizeCm, UMaterialInterface* Material, const FRotator& Rot = FRotator::ZeroRotator);

	// cylindre tendu entre deux points (repère du parent)
	UStaticMeshComponent* Limb(AActor* Owner, USceneComponent* Parent, const FVector& From, const FVector& To, float Diameter, UMaterialInterface* Material);
}
