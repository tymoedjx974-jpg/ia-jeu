#include "TMMShapes.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

namespace TMMShapes
{
	static UStaticMesh* LoadMesh(const TCHAR* Path)
	{
		return LoadObject<UStaticMesh>(nullptr, Path);
	}

	UStaticMesh* Cube() { static TWeakObjectPtr<UStaticMesh> M; if (!M.IsValid()) M = LoadMesh(TEXT("/Engine/BasicShapes/Cube.Cube")); return M.Get(); }
	UStaticMesh* Cylinder() { static TWeakObjectPtr<UStaticMesh> M; if (!M.IsValid()) M = LoadMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder")); return M.Get(); }
	UStaticMesh* Sphere() { static TWeakObjectPtr<UStaticMesh> M; if (!M.IsValid()) M = LoadMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere")); return M.Get(); }

	UMaterialInterface* Mat(UObject* Outer, const FLinearColor& Color)
	{
		UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
		if (!Base) return nullptr;
		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Base, Outer);
		MID->SetVectorParameterValue(TEXT("Color"), Color);
		return MID;
	}

	USceneComponent* Pivot(AActor* Owner, USceneComponent* Parent, const FVector& Loc, const FRotator& Rot)
	{
		USceneComponent* C = NewObject<USceneComponent>(Owner);
		C->SetupAttachment(Parent);
		C->SetRelativeLocationAndRotation(Loc, Rot);
		C->RegisterComponent();
		Owner->AddInstanceComponent(C);
		return C;
	}

	UStaticMeshComponent* Add(AActor* Owner, USceneComponent* Parent, UStaticMesh* Mesh, const FVector& Loc, const FVector& SizeCm, UMaterialInterface* Material, const FRotator& Rot)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(Owner);
		C->SetupAttachment(Parent);
		C->SetStaticMesh(Mesh);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetGenerateOverlapEvents(false);
		C->SetRelativeLocationAndRotation(Loc, Rot);
		C->SetRelativeScale3D(SizeCm / 100.f);
		if (Material) C->SetMaterial(0, Material);
		C->RegisterComponent();
		Owner->AddInstanceComponent(C);
		return C;
	}

	UStaticMeshComponent* Limb(AActor* Owner, USceneComponent* Parent, const FVector& From, const FVector& To, float Diameter, UMaterialInterface* Material)
	{
		const FVector D = To - From;
		const FRotator Rot = FRotationMatrix::MakeFromZ(D.GetSafeNormal()).Rotator();
		return Add(Owner, Parent, Cylinder(), (From + To) * 0.5f, FVector(Diameter, Diameter, D.Size()), Material, Rot);
	}
}
