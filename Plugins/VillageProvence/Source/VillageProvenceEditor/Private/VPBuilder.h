#pragma once

#include "CoreMinimal.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

class AActor;
class FJsonObject;
class UMaterial;
class UMaterialInterface;
class UMaterialParameterCollection;
class UStaticMesh;
class UTexture2D;
class UWorld;
struct FScopedSlowTask;

DECLARE_LOG_CATEGORY_EXTERN(LogVillageProvence, Log, All);

// Une section de maillage (un matériau) lue dans un fichier .pvm
struct FVPSection
{
	FString Material;
	int32 NumUV = 1;
	TArray<FVector3f> Positions;
	TArray<FVector3f> Normals;
	TArray<FVector2f> UVs; // NumVertices * NumUV, rangés par sommet
	TArray<FColor> Colors;
	TArray<uint32> Indices;
};

using FVPLod = TArray<FVPSection>;

// Construit le village dans le niveau ouvert à partir des données du dossier Data du plugin
class FVPBuilder
{
public:
	enum class EMode : uint8
	{
		Full,
		ActorsOnly,
		Remove
	};

	explicit FVPBuilder(EMode InMode);
	bool Run();

private:
	// lecture des données
	bool LoadManifest();
	FString DataFile(const FString& Relative) const;
	static bool ReadCompressed(const TArray<uint8>& File, int32 PayloadOffset, int32 RawSize, int32 CompressedSize, TArray<uint8>& Out);
	bool ReadPVM(const FString& File, TArray<FVPLod>& OutLods) const;

	// assets
	template <class T>
	T* FindOrCreate(const FString& Folder, const FString& Name);
	template <class T>
	T* FindExisting(const FString& Folder, const FString& Name) const;
	UTexture2D* MakeTextureFromPixels(const FString& Name, int32 Width, int32 Height, const TArray64<uint8>& BGRA, const FString& Kind, bool bSRGB);
	UTexture2D* MakeTexture(const FString& Name, const FString& File, const FString& Kind, bool bSRGB);
	UTexture2D* MakeSolidTexture(const FString& Name, FColor Color, const FString& Kind);
	void BuildTextures(FScopedSlowTask& Task);
	void BuildWindCollection();
	void BuildMaterials(FScopedSlowTask& Task);
	UMaterial* BuildMaster(const FString& Type);
	UMaterialInterface* GetMaterial(const FString& Name) const;
	UMaterialInterface* GetTinted(const FString& Base, FColor Color);
	UStaticMesh* BuildStaticMesh(const FString& Name, const FString& Folder, const TArray<FVPLod>& Lods, bool bNanite,
		const FString& Collision, const TArray<float>& CollisionDims, const TArray<float>& LodScreenSizes, bool bFoliage);
	void BuildMeshes(FScopedSlowTask& Task);
	void BuildTerrain(FScopedSlowTask& Task);
	void LoadExistingAssets();

	// niveau
	void RemoveVillageActors();
	AActor* Tag(AActor* Actor, const FString& Label, const FString& Folder, bool bAlwaysLoaded) const;
	void SpawnMeshActors(FScopedSlowTask& Task);
	void SpawnInstances(FScopedSlowTask& Task);
	void SetupAmbiance();
	void SetupSounds();

	EMode Mode;
	FString DataDir;
	FString Root = TEXT("/Game/VillageProvence");
	TSharedPtr<FJsonObject> Manifest;
	UWorld* World = nullptr;

	TMap<FString, UTexture2D*> Textures;
	TMap<FString, UMaterial*> Masters;
	UMaterialParameterCollection* WindCollection = nullptr;
	TMap<FString, UMaterialInterface*> Materials;
	TMap<FString, TSharedPtr<FJsonObject>> MaterialInfo;
	TMap<FString, UMaterialInterface*> Tinted;
	TMap<FString, UStaticMesh*> Meshes;
	TMap<FString, TSharedPtr<FJsonObject>> MeshInfo;

	struct FTerrainTile
	{
		FString Mesh;
		FVector Location;
	};
	TArray<FTerrainTile> TerrainTiles;
	int32 Warnings = 0;
};

template <class T>
T* FVPBuilder::FindExisting(const FString& Folder, const FString& Name) const
{
	const FString ObjectPath = Root / Folder / Name + TEXT(".") + Name;
	return LoadObject<T>(nullptr, *ObjectPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
}

template <class T>
T* FVPBuilder::FindOrCreate(const FString& Folder, const FString& Name)
{
	if (T* Existing = FindExisting<T>(Folder, Name))
	{
		return Existing;
	}
	const FString PackageName = Root / Folder / Name;
	UPackage* Package = CreatePackage(*PackageName);
	T* Object = NewObject<T>(Package, T::StaticClass(), FName(*Name), RF_Public | RF_Standalone | RF_Transactional);
	FAssetRegistryModule::AssetCreated(Object);
	Package->MarkPackageDirty();
	return Object;
}
