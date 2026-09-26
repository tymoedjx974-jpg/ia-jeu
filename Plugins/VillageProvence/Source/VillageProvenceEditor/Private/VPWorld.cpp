#include "VPBuilder.h"
#include "VPReader.h"

#include "AssetImportTask.h"
#include "AssetToolsModule.h"
#include "Components/AudioComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Editor.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerStart.h"
#include "IAssetTools.h"
#include "Misc/FileHelper.h"
#include "Misc/ScopedSlowTask.h"
#include "Modules/ModuleManager.h"
#include "Sound/AmbientSound.h"
#include "Sound/SoundWave.h"
#include "UObject/UnrealType.h"
#include "VPVegetationShared.h"
#include "VPVent.h"

#define LOCTEXT_NAMESPACE "VillageProvence"

namespace
{
	const FName VillageTag(TEXT("VillageProvence"));

	bool HasActorOfClass(UWorld* World, UClass* Class)
	{
		if (!Class)
		{
			return true;
		}
		for (TActorIterator<AActor> It(World, Class); It; ++It)
		{
			return true;
		}
		return false;
	}

	FVector JsonVector(const TSharedPtr<FJsonValue>& Value)
	{
		const TArray<TSharedPtr<FJsonValue>>& A = Value->AsArray();
		return A.Num() >= 3 ? FVector(A[0]->AsNumber(), A[1]->AsNumber(), A[2]->AsNumber()) : FVector::ZeroVector;
	}
}

void FVPBuilder::RemoveVillageActors()
{
	TArray<AActor*> ToRemove;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (It->ActorHasTag(VillageTag))
		{
			ToRemove.Add(*It);
		}
	}
	for (AActor* Actor : ToRemove)
	{
		World->EditorDestroyActor(Actor, true);
	}
}

AActor* FVPBuilder::Tag(AActor* Actor, const FString& Label, const FString& Folder, bool bAlwaysLoaded) const
{
	if (!Actor)
	{
		return nullptr;
	}
	Actor->Tags.AddUnique(VillageTag);
	Actor->SetActorLabel(Label);
	Actor->SetFolderPath(FName(*Folder));
	if (bAlwaysLoaded)
	{
		// monde ouvert (World Partition) : le terrain et l'horizon restent toujours chargés
		if (FBoolProperty* Prop = FindFProperty<FBoolProperty>(AActor::StaticClass(), TEXT("bIsSpatiallyLoaded")))
		{
			Prop->SetPropertyValue_InContainer(Actor, false);
		}
	}
	return Actor;
}

void FVPBuilder::SpawnMeshActors(FScopedSlowTask& Task)
{
	Task.EnterProgressFrame(4.f, LOCTEXT("Actors", "Placement du terrain, du bâti et de la voirie..."));
	auto Spawn = [this](const FString& MeshName, const FVector& Location, float Yaw, const FString& Folder, bool bAlwaysLoaded)
	{
		UStaticMesh* Mesh = Meshes.FindRef(MeshName);
		if (!Mesh)
		{
			UE_LOG(LogVillageProvence, Warning, TEXT("Maillage manquant : %s"), *MeshName);
			++Warnings;
			return;
		}
		AStaticMeshActor* Actor = World->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), FTransform(FRotator(0.f, Yaw, 0.f), Location));
		if (!Actor)
		{
			++Warnings;
			return;
		}
		UStaticMeshComponent* Component = Actor->GetStaticMeshComponent();
		Component->SetMobility(EComponentMobility::Static);
		Component->SetStaticMesh(Mesh);
		const TSharedPtr<FJsonObject>* Info = MeshInfo.Find(MeshName);
		if (Info && (*Info)->GetStringField(TEXT("collision")) == TEXT("none"))
		{
			Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		}
		Tag(Actor, TEXT("VP_") + MeshName, Folder, bAlwaysLoaded);
	};

	for (const FTerrainTile& Tile : TerrainTiles)
	{
		Spawn(Tile.Mesh, Tile.Location, 0.f, TEXT("VillageProvence/Terrain"), true);
	}
	for (const TSharedPtr<FJsonValue>& Value : Manifest->GetArrayField(TEXT("actors")))
	{
		const TSharedPtr<FJsonObject> A = Value->AsObject();
		Spawn(A->GetStringField(TEXT("mesh")), JsonVector(A->GetField<EJson::Array>(TEXT("loc"))), (float)A->GetNumberField(TEXT("yaw")),
			A->GetStringField(TEXT("folder")), A->GetBoolField(TEXT("always_loaded")));
	}
}

void FVPBuilder::SpawnInstances(FScopedSlowTask& Task)
{
	TArray<uint8> File;
	if (!FFileHelper::LoadFileToArray(File, *DataFile(TEXT("Instances.pvi"))) || File.Num() < 16 || FMemory::Memcmp(File.GetData(), "PVI2", 4) != 0)
	{
		UE_LOG(LogVillageProvence, Error, TEXT("Fichier d'instances illisible"));
		++Warnings;
		return;
	}
	TArray<uint8> Payload;
	if (!ReadCompressed(File, 16, (int32)VP::ReadU32(File, 4), (int32)VP::ReadU32(File, 8), Payload))
	{
		++Warnings;
		return;
	}
	const uint32 NumGroups = VP::ReadU32(File, 12);
	VP::FReader R(Payload);
	TMap<FString, AActor*> CellActors;
	const float Step = 12.f / FMath::Max<uint32>(1, NumGroups);
	int64 Total = 0;

	for (uint32 G = 0; G < NumGroups && !R.bError; ++G)
	{
		const FString MeshName = R.String16();
		const uint8 ColR = R.Get<uint8>();
		const uint8 ColG = R.Get<uint8>();
		const uint8 ColB = R.Get<uint8>();
		const int16 CX = R.Get<int16>();
		const int16 CY = R.Get<int16>();
		const uint32 Count = R.Get<uint32>();
		TArray<int32> Positions;
		Positions.SetNumUninitialized(Count * 3);
		R.Bytes(Positions.GetData(), (int64)Count * 12);
		TArray<uint16> Yaws;
		Yaws.SetNumUninitialized(Count);
		R.Bytes(Yaws.GetData(), (int64)Count * 2);
		TArray<uint16> Scales;
		Scales.SetNumUninitialized(Count * 3);
		R.Bytes(Scales.GetData(), (int64)Count * 6);
		Task.EnterProgressFrame(Step, FText::Format(LOCTEXT("Inst", "Instances {0}"), FText::FromString(MeshName)));

		UStaticMesh* Mesh = Meshes.FindRef(MeshName);
		const TSharedPtr<FJsonObject>* Info = MeshInfo.Find(MeshName);
		if (!Mesh || !Info || Count == 0)
		{
			++Warnings;
			continue;
		}
		const bool bVegetation = MeshName.StartsWith(TEXT("Veg_"));
		const bool bNanite = (*Info)->GetBoolField(TEXT("nanite"));
		const FString Key = FString::Printf(TEXT("%s_%d_%d"), bVegetation ? TEXT("Vegetation") : TEXT("Details"), (int32)CX, (int32)CY);
		AActor* Owner = CellActors.FindRef(Key);
		if (!Owner)
		{
			const FVector Center((CX + 0.5f) * 102400.f, -(CY + 0.5f) * 102400.f, 0.f);
			Owner = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(Center));
			if (!Owner)
			{
				++Warnings;
				continue;
			}
			USceneComponent* RootComponent = NewObject<USceneComponent>(Owner, TEXT("Racine"), RF_Transactional);
			RootComponent->SetMobility(EComponentMobility::Static);
			Owner->SetRootComponent(RootComponent);
			Owner->AddInstanceComponent(RootComponent);
			RootComponent->RegisterComponent();
			Owner->SetActorLocation(Center);
			Tag(Owner, TEXT("VP_") + Key, bVegetation ? TEXT("VillageProvence/Vegetation") : TEXT("VillageProvence/Details"), true);
			CellActors.Add(Key, Owner);
		}

		const FName ComponentName = MakeUniqueObjectName(Owner, UInstancedStaticMeshComponent::StaticClass(), FName(*MeshName));
		UInstancedStaticMeshComponent* Component = bNanite
			? NewObject<UInstancedStaticMeshComponent>(Owner, ComponentName, RF_Transactional)
			: NewObject<UHierarchicalInstancedStaticMeshComponent>(Owner, ComponentName, RF_Transactional);
		Component->SetMobility(EComponentMobility::Static);
		Component->SetStaticMesh(Mesh);
		Component->SetupAttachment(Owner->GetRootComponent());
		Owner->AddInstanceComponent(Component);
		Component->RegisterComponent();

		if ((*Info)->GetStringField(TEXT("collision")) == TEXT("none"))
		{
			Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		}
		double Cull = 0.0;
		if ((*Info)->TryGetNumberField(TEXT("cull_distance"), Cull) && Cull > 0.0)
		{
			Component->SetCullDistances((int32)(Cull * 0.85), (int32)Cull);
		}
		if (MeshName.Contains(TEXT("Herbe")))
		{
			Component->SetCastShadow(false);
		}
		if (bVegetation)
		{
			// la végétation bouge (vent, passage des personnages) : bornes élargies pour ne pas disparaître en pliant
			const bool bSoft = MeshName.Contains(TEXT("Herbe")) || MeshName.Contains(TEXT("Lavande")) || MeshName.Contains(TEXT("Buisson")) || MeshName.Contains(TEXT("Vigne"));
			Component->SetBoundsScale(bSoft ? 1.6f : 1.15f);
			if (bSoft)
			{
				// herbes, lavande, buissons et vigne : froissement quand le joueur les traverse
				Component->ComponentTags.AddUnique(VPVegetation::TagSouple());
				// au loin, le mouvement des petites plantes ne se voit plus : on l'arrête pour économiser le processeur graphique
				if (FIntProperty* Prop = FindFProperty<FIntProperty>(UPrimitiveComponent::StaticClass(), TEXT("WorldPositionOffsetDisableDistance")))
				{
					Prop->SetPropertyValue_InContainer(Component, MeshName.Contains(TEXT("Herbe")) ? 6000 : 9000);
				}
			}
		}
		if (ColR != 255 || ColG != 255 || ColB != 255)
		{
			for (const TCHAR* Slot : { TEXT("BoisPeint"), TEXT("Toile") })
			{
				const int32 Index = Mesh->GetMaterialIndex(FName(Slot));
				if (Index != INDEX_NONE)
				{
					if (UMaterialInterface* Mat = GetTinted(Slot, FColor(ColR, ColG, ColB)))
					{
						Component->SetMaterial(Index, Mat);
					}
				}
			}
		}

		TArray<FTransform> Transforms;
		Transforms.Reserve(Count);
		for (uint32 I = 0; I < Count; ++I)
		{
			const FVector Location(Positions[I * 3], Positions[I * 3 + 1], Positions[I * 3 + 2]);
			const float Yaw = Yaws[I] / 65535.f * 360.f;
			const FVector Scale(Scales[I * 3] / 1000.f, Scales[I * 3 + 1] / 1000.f, Scales[I * 3 + 2] / 1000.f);
			Transforms.Emplace(FRotator(0.f, Yaw, 0.f), Location, Scale);
		}
		Component->AddInstances(Transforms, false, true);
		Total += Count;
	}
	UE_LOG(LogVillageProvence, Log, TEXT("%lld instances placées dans %d acteurs"), Total, CellActors.Num());
}

void FVPBuilder::SetupAmbiance()
{
	const TSharedPtr<FJsonObject> Amb = Manifest->GetObjectField(TEXT("ambiance"));
	const float Elevation = FMath::DegreesToRadians((float)Amb->GetNumberField(TEXT("sun_elevation")));
	const float Azimuth = FMath::DegreesToRadians((float)Amb->GetNumberField(TEXT("sun_azimuth")));
	// direction vers le soleil (azimut depuis le nord, sens horaire) ; l'axe Y d'Unreal pointe vers le sud
	const FVector ToSun(FMath::Sin(Azimuth) * FMath::Cos(Elevation), -FMath::Cos(Azimuth) * FMath::Cos(Elevation), FMath::Sin(Elevation));
	const FRotator SunRotation = (-ToSun).Rotation();
	const FString Folder = TEXT("VillageProvence/Ambiance");

	if (!HasActorOfClass(World, ADirectionalLight::StaticClass()))
	{
		ADirectionalLight* Sun = World->SpawnActor<ADirectionalLight>(ADirectionalLight::StaticClass(), FTransform(SunRotation, FVector(0.f, 0.f, 20000.f)));
		if (Sun)
		{
			if (UDirectionalLightComponent* Light = Cast<UDirectionalLightComponent>(Sun->GetLightComponent()))
			{
				Light->SetMobility(EComponentMobility::Movable);
				Light->SetIntensity((float)Amb->GetNumberField(TEXT("sun_lux")));
				Light->SetUseTemperature(true);
				Light->SetTemperature((float)Amb->GetNumberField(TEXT("sun_temperature")));
				Light->SetAtmosphereSunLight(true);
			}
			Tag(Sun, TEXT("VP_Soleil"), Folder, true);
		}
	}
	if (UClass* SkyAtmosphereClass = LoadClass<AActor>(nullptr, TEXT("/Script/Engine.SkyAtmosphere")))
	{
		if (!HasActorOfClass(World, SkyAtmosphereClass))
		{
			Tag(World->SpawnActor<AActor>(SkyAtmosphereClass, FTransform::Identity), TEXT("VP_Atmosphere"), Folder, true);
		}
	}
	if (UClass* CloudClass = LoadClass<AActor>(nullptr, TEXT("/Script/Engine.VolumetricCloud")))
	{
		if (!HasActorOfClass(World, CloudClass))
		{
			Tag(World->SpawnActor<AActor>(CloudClass, FTransform::Identity), TEXT("VP_Nuages"), Folder, true);
		}
	}
	if (!HasActorOfClass(World, ASkyLight::StaticClass()))
	{
		ASkyLight* Sky = World->SpawnActor<ASkyLight>(ASkyLight::StaticClass(), FTransform(FVector(0.f, 0.f, 15000.f)));
		if (Sky)
		{
			if (USkyLightComponent* SkyComponent = Sky->GetLightComponent())
			{
				SkyComponent->SetMobility(EComponentMobility::Movable);
				if (FBoolProperty* Prop = FindFProperty<FBoolProperty>(USkyLightComponent::StaticClass(), TEXT("bRealTimeCapture")))
				{
					Prop->SetPropertyValue_InContainer(SkyComponent, true);
				}
				SkyComponent->MarkRenderStateDirty();
			}
			Tag(Sky, TEXT("VP_LumiereCiel"), Folder, true);
		}
	}
	if (!HasActorOfClass(World, AExponentialHeightFog::StaticClass()))
	{
		AExponentialHeightFog* Fog = World->SpawnActor<AExponentialHeightFog>(AExponentialHeightFog::StaticClass(), FTransform(FVector(0.f, 0.f, 0.f)));
		if (Fog)
		{
			if (UExponentialHeightFogComponent* FogComponent = Fog->GetComponent())
			{
				FogComponent->SetFogDensity((float)Amb->GetNumberField(TEXT("fog_density")));
				FogComponent->SetFogHeightFalloff((float)Amb->GetNumberField(TEXT("fog_falloff")));
				FogComponent->SetVolumetricFog(Amb->GetBoolField(TEXT("volumetric_fog")));
			}
			Tag(Fog, TEXT("VP_Brume"), Folder, true);
		}
	}
	// réglages d'image : Lumen, teinte chaude de fin d'après-midi, légère saturation
	APostProcessVolume* Post = World->SpawnActor<APostProcessVolume>(APostProcessVolume::StaticClass(), FTransform::Identity);
	if (Post)
	{
		Post->bUnbound = true;
		Post->Priority = 1.f;
		FPostProcessSettings& S = Post->Settings;
		S.bOverride_DynamicGlobalIlluminationMethod = true;
		S.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::Lumen;
		S.bOverride_ReflectionMethod = true;
		S.ReflectionMethod = EReflectionMethod::Lumen;
		S.bOverride_WhiteTemp = true;
		S.WhiteTemp = (float)Amb->GetNumberField(TEXT("white_temp"));
		const float Saturation = (float)Amb->GetNumberField(TEXT("saturation"));
		S.bOverride_ColorSaturation = true;
		S.ColorSaturation = FVector4(Saturation, Saturation, Saturation, 1.f);
		S.bOverride_BloomIntensity = true;
		S.BloomIntensity = (float)Amb->GetNumberField(TEXT("bloom"));
		S.bOverride_AutoExposureBias = true;
		S.AutoExposureBias = (float)Amb->GetNumberField(TEXT("exposure_bias"));
		S.bOverride_VignetteIntensity = true;
		S.VignetteIntensity = 0.3f;
		Tag(Post, TEXT("VP_Image"), Folder, true);
	}
	if (!HasActorOfClass(World, APlayerStart::StaticClass()))
	{
		const FVector Start = JsonVector(Amb->GetField<EJson::Array>(TEXT("player_start")));
		Tag(World->SpawnActor<APlayerStart>(APlayerStart::StaticClass(), FTransform(FRotator(0.f, 90.f, 0.f), Start + FVector(0.f, 0.f, 100.f))), TEXT("VP_Depart"), Folder, false);
	}
}

void FVPBuilder::SetupSounds()
{
	TMap<FString, USoundWave*> Loaded;
	for (const TSharedPtr<FJsonValue>& Value : Manifest->GetArrayField(TEXT("sounds")))
	{
		const TSharedPtr<FJsonObject> S = Value->AsObject();
		const FString Name = S->GetStringField(TEXT("name"));
		USoundWave* Wave = Loaded.FindRef(Name);
		if (!Wave)
		{
			Wave = FindExisting<USoundWave>(TEXT("Sons"), Name);
			if (!Wave || Mode == EMode::Full)
			{
				UAssetImportTask* Import = NewObject<UAssetImportTask>();
				Import->Filename = DataFile(S->GetStringField(TEXT("file")));
				Import->DestinationPath = Root / TEXT("Sons");
				Import->DestinationName = Name;
				Import->bAutomated = true;
				Import->bReplaceExisting = true;
				Import->bSave = false;
				FAssetToolsModule& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
				AssetTools.Get().ImportAssetTasks({ Import });
				Wave = FindExisting<USoundWave>(TEXT("Sons"), Name);
			}
			if (!Wave)
			{
				UE_LOG(LogVillageProvence, Warning, TEXT("Son non importé : %s"), *Name);
				++Warnings;
				continue;
			}
			bool bLoop = true;
			S->TryGetBoolField(TEXT("loop"), bLoop);
			Wave->bLooping = bLoop;
			Wave->MarkPackageDirty();
			Loaded.Add(Name, Wave);
		}
		const bool bSpatial = S->GetBoolField(TEXT("spatial"));
		const float Volume = (float)S->GetNumberField(TEXT("volume"));
		double Radius = 2000.0;
		S->TryGetNumberField(TEXT("radius_cm"), Radius);
		int32 Index = 0;
		for (const TSharedPtr<FJsonValue>& Loc : S->GetArrayField(TEXT("locations")))
		{
			AAmbientSound* Emitter = World->SpawnActor<AAmbientSound>(AAmbientSound::StaticClass(), FTransform(JsonVector(Loc)));
			if (!Emitter)
			{
				continue;
			}
			UAudioComponent* Audio = Emitter->GetAudioComponent();
			Audio->SetSound(Wave);
			Audio->SetVolumeMultiplier(Volume);
			Audio->bAllowSpatialization = bSpatial;
			if (bSpatial)
			{
				Audio->bOverrideAttenuation = true;
				Audio->AttenuationOverrides.bAttenuate = true;
				Audio->AttenuationOverrides.bSpatialize = true;
				Audio->AttenuationOverrides.AttenuationShapeExtents = FVector((float)Radius * 0.25f, 0.f, 0.f);
				Audio->AttenuationOverrides.FalloffDistance = (float)Radius;
			}
			Tag(Emitter, FString::Printf(TEXT("VP_%s_%d"), *Name, Index++), TEXT("VillageProvence/Sons"), true);
		}
	}

	// réglages du vent (lus par UVPVegetationSubsystem en jeu) avec le souffle et les froissements
	AVPVent* Vent = nullptr;
	for (TActorIterator<AVPVent> It(World); It; ++It)
	{
		Vent = *It;
		break;
	}
	if (!Vent)
	{
		Vent = World->SpawnActor<AVPVent>(AVPVent::StaticClass(), FTransform(FVector(0.f, 0.f, 45000.f)));
		Tag(Vent, TEXT("VP_Vent"), TEXT("VillageProvence/Ambiance"), true);
	}
	if (Vent)
	{
		Vent->Modify();
		Vent->SonVent = Loaded.FindRef(TEXT("S_Vent"));
		Vent->SonsFroissement.Reset();
		for (int32 I = 0; I < VPVegetation::NumFroissements; ++I)
		{
			if (USoundWave* Wave = Loaded.FindRef(FString::Printf(TEXT("S_Froissement_%d"), I)))
			{
				Vent->SonsFroissement.Add(Wave);
			}
		}
	}
}

#undef LOCTEXT_NAMESPACE
