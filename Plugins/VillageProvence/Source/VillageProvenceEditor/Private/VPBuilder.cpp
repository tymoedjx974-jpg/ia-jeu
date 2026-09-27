#include "VPBuilder.h"
#include "VPReader.h"

#include "Dom/JsonObject.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "FileHelpers.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Interfaces/IPluginManager.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "Misc/Compression.h"
#include "Misc/FileHelper.h"
#include "Misc/MessageDialog.h"
#include "Misc/Paths.h"
#include "Misc/ScopedSlowTask.h"
#include "Modules/ModuleManager.h"
#include "PhysicsEngine/BodySetup.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "StaticMeshAttributes.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY(LogVillageProvence);

#define LOCTEXT_NAMESPACE "VillageProvence"

namespace
{
	// Réglages Nanite par réflexion : le champ NaniteSettings a changé d'accès selon les versions 5.x
	void SetNanite(UStaticMesh* Mesh, bool bEnable)
	{
		FStructProperty* Prop = FindFProperty<FStructProperty>(UStaticMesh::StaticClass(), TEXT("NaniteSettings"));
		if (!Prop)
		{
			return;
		}
		void* Settings = Prop->ContainerPtrToValuePtr<void>(Mesh);
		UScriptStruct* Struct = Prop->Struct;
		if (FBoolProperty* Enabled = FindFProperty<FBoolProperty>(Struct, TEXT("bEnabled")))
		{
			Enabled->SetPropertyValue_InContainer(Settings, bEnable);
		}
		// maillage de repli complet : collisions et ombres exactes
		if (FFloatProperty* Percent = FindFProperty<FFloatProperty>(Struct, TEXT("FallbackPercentTriangles")))
		{
			Percent->SetPropertyValue_InContainer(Settings, 1.0f);
		}
		if (FFloatProperty* RelError = FindFProperty<FFloatProperty>(Struct, TEXT("FallbackRelativeError")))
		{
			RelError->SetPropertyValue_InContainer(Settings, 0.0f);
		}
		if (FEnumProperty* Target = FindFProperty<FEnumProperty>(Struct, TEXT("FallbackTarget")))
		{
			if (UEnum* Enum = Target->GetEnum())
			{
				const int64 Value = Enum->GetValueByNameString(TEXT("PercentTriangles"));
				if (Value != INDEX_NONE)
				{
					Target->GetUnderlyingProperty()->SetIntPropertyValue(Target->ContainerPtrToValuePtr<void>(Settings), Value);
				}
			}
		}
	}

	void SetBoolByName(UObject* Object, const TCHAR* Name, bool bValue)
	{
		if (!Object)
		{
			return;
		}
		if (FBoolProperty* Prop = FindFProperty<FBoolProperty>(Object->GetClass(), Name))
		{
			Prop->SetPropertyValue_InContainer(Object, bValue);
		}
	}

	FVector4f ToVertexColor(const FColor& C)
	{
		// la construction du maillage convertit en sRGB : on donne la valeur linéaire correspondante
		// pour que les octets du fichier arrivent tels quels dans le shader
		const FLinearColor L = FLinearColor::FromSRGBColor(C);
		return FVector4f(L.R, L.G, L.B, C.A / 255.f);
	}
}

FVPBuilder::FVPBuilder(EMode InMode)
	: Mode(InMode)
{
	TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("VillageProvence"));
	if (Plugin.IsValid())
	{
		DataDir = FPaths::Combine(Plugin->GetBaseDir(), TEXT("Data"));
	}
}

FString FVPBuilder::DataFile(const FString& Relative) const
{
	return FPaths::Combine(DataDir, Relative);
}

bool FVPBuilder::LoadManifest()
{
	FString Json;
	if (DataDir.IsEmpty() || !FFileHelper::LoadFileToString(Json, *DataFile(TEXT("Village.json"))))
	{
		return false;
	}
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Manifest) || !Manifest.IsValid())
	{
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Value : Manifest->GetArrayField(TEXT("meshes")))
	{
		const TSharedPtr<FJsonObject> Obj = Value->AsObject();
		MeshInfo.Add(Obj->GetStringField(TEXT("name")), Obj);
	}
	for (const TSharedPtr<FJsonValue>& Value : Manifest->GetArrayField(TEXT("materials")))
	{
		const TSharedPtr<FJsonObject> Obj = Value->AsObject();
		MaterialInfo.Add(Obj->GetStringField(TEXT("name")), Obj);
	}
	return true;
}

bool FVPBuilder::ReadCompressed(const TArray<uint8>& File, int32 PayloadOffset, int32 RawSize, int32 CompressedSize, TArray<uint8>& Out)
{
	if (PayloadOffset + CompressedSize > File.Num() || RawSize <= 0)
	{
		return false;
	}
	Out.SetNumUninitialized(RawSize);
	return FCompression::UncompressMemory(NAME_Zlib, Out.GetData(), RawSize, File.GetData() + PayloadOffset, CompressedSize);
}

bool FVPBuilder::ReadPVM(const FString& File, TArray<FVPLod>& OutLods) const
{
	TArray<uint8> Data;
	if (!FFileHelper::LoadFileToArray(Data, *File) || Data.Num() < 12 || FMemory::Memcmp(Data.GetData(), "PVM2", 4) != 0)
	{
		UE_LOG(LogVillageProvence, Warning, TEXT("Fichier de maillage illisible : %s"), *File);
		return false;
	}
	TArray<uint8> Payload;
	if (!ReadCompressed(Data, 12, (int32)VP::ReadU32(Data, 4), (int32)VP::ReadU32(Data, 8), Payload))
	{
		UE_LOG(LogVillageProvence, Warning, TEXT("Décompression impossible : %s"), *File);
		return false;
	}
	VP::FReader R(Payload);
	const uint32 NumLods = R.Get<uint32>();
	OutLods.SetNum(NumLods);
	for (uint32 L = 0; L < NumLods && !R.bError; ++L)
	{
		const uint32 NumSections = R.Get<uint32>();
		for (uint32 S = 0; S < NumSections && !R.bError; ++S)
		{
			FVPSection& Sec = OutLods[L].AddDefaulted_GetRef();
			Sec.Material = R.String16();
			const uint32 NV = R.Get<uint32>();
			const uint32 NT = R.Get<uint32>();
			Sec.NumUV = FMath::Max<int32>(1, R.Get<uint8>());
			Sec.Positions.SetNumUninitialized(NV);
			R.Bytes(Sec.Positions.GetData(), (int64)NV * 12);
			TArray<int16> N16;
			N16.SetNumUninitialized(NV * 3);
			R.Bytes(N16.GetData(), (int64)NV * 6);
			Sec.Normals.SetNumUninitialized(NV);
			for (uint32 V = 0; V < NV; ++V)
			{
				Sec.Normals[V] = FVector3f(N16[V * 3] / 32767.f, N16[V * 3 + 1] / 32767.f, N16[V * 3 + 2] / 32767.f).GetSafeNormal();
			}
			Sec.UVs.SetNumUninitialized(NV * Sec.NumUV);
			R.Bytes(Sec.UVs.GetData(), (int64)NV * Sec.NumUV * 8);
			TArray<uint8> Rgba;
			Rgba.SetNumUninitialized(NV * 4);
			R.Bytes(Rgba.GetData(), (int64)NV * 4);
			Sec.Colors.SetNumUninitialized(NV);
			for (uint32 V = 0; V < NV; ++V)
			{
				Sec.Colors[V] = FColor(Rgba[V * 4], Rgba[V * 4 + 1], Rgba[V * 4 + 2], Rgba[V * 4 + 3]);
			}
			Sec.Indices.SetNumUninitialized(NT * 3);
			R.Bytes(Sec.Indices.GetData(), (int64)NT * 12);
		}
	}
	if (R.bError)
	{
		UE_LOG(LogVillageProvence, Warning, TEXT("Fichier de maillage tronqué : %s"), *File);
		return false;
	}
	return true;
}

// ------------------------------------------------------------------ textures

UTexture2D* FVPBuilder::MakeTextureFromPixels(const FString& Name, int32 Width, int32 Height, const TArray64<uint8>& BGRA, const FString& Kind, bool bSRGB)
{
	UTexture2D* Tex = FindOrCreate<UTexture2D>(TEXT("Textures"), Name);
	Tex->PreEditChange(nullptr);
	Tex->Source.Init(Width, Height, 1, 1, TSF_BGRA8, BGRA.GetData());
	Tex->SRGB = bSRGB;
	if (Kind == TEXT("normal"))
	{
		Tex->CompressionSettings = TC_Normalmap;
		Tex->SRGB = false;
		Tex->LODGroup = TEXTUREGROUP_WorldNormalMap;
	}
	else if (Kind == TEXT("masks"))
	{
		Tex->CompressionSettings = TC_Masks;
		Tex->SRGB = false;
	}
	else
	{
		Tex->CompressionSettings = TC_Default;
		// feuillages découpés : conserve la densité des feuilles dans les mipmaps (sinon les arbres « fondent » au loin)
		static const TCHAR* Foliage[] = { TEXT("Feuilles"), TEXT("Aiguilles"), TEXT("Lavande"), TEXT("Herbe"), TEXT("Fleurs"), TEXT("Glycine") };
		bool bFoliage = false;
		for (const TCHAR* Key : Foliage)
		{
			bFoliage |= Name.Contains(Key);
		}
		if (bFoliage)
		{
			SetBoolByName(Tex, TEXT("bDoScaleMipsForAlphaCoverage"), true);
			if (FStructProperty* Thresholds = FindFProperty<FStructProperty>(UTexture::StaticClass(), TEXT("AlphaCoverageThresholds")))
			{
				if (Thresholds->Struct && Thresholds->Struct->GetFName() == FName(TEXT("Vector4")))
				{
					*Thresholds->ContainerPtrToValuePtr<FVector4>(Tex) = FVector4(0.0, 0.0, 0.0, 0.4);
				}
			}
		}
	}
	Tex->PostEditChange();
	Tex->MarkPackageDirty();
	Textures.Add(Name, Tex);
	return Tex;
}

UTexture2D* FVPBuilder::MakeTexture(const FString& Name, const FString& File, const FString& Kind, bool bSRGB)
{
	TArray<uint8> Data;
	if (!FFileHelper::LoadFileToArray(Data, *File))
	{
		UE_LOG(LogVillageProvence, Warning, TEXT("Texture introuvable : %s"), *File);
		++Warnings;
		return nullptr;
	}
	IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(FName("ImageWrapper"));
	const EImageFormat Format = ImageWrapperModule.DetectImageFormat(Data.GetData(), Data.Num());
	if (Format == EImageFormat::Invalid)
	{
		++Warnings;
		return nullptr;
	}
	TSharedPtr<IImageWrapper> Wrapper = ImageWrapperModule.CreateImageWrapper(Format);
	TArray64<uint8> Raw;
	if (!Wrapper.IsValid() || !Wrapper->SetCompressed(Data.GetData(), Data.Num()) || !Wrapper->GetRaw(ERGBFormat::BGRA, 8, Raw))
	{
		UE_LOG(LogVillageProvence, Warning, TEXT("Image illisible : %s"), *File);
		++Warnings;
		return nullptr;
	}
	return MakeTextureFromPixels(Name, (int32)Wrapper->GetWidth(), (int32)Wrapper->GetHeight(), Raw, Kind, bSRGB);
}

UTexture2D* FVPBuilder::MakeSolidTexture(const FString& Name, FColor Color, const FString& Kind)
{
	const int32 Size = 4;
	TArray64<uint8> Pixels;
	Pixels.SetNumUninitialized(Size * Size * 4);
	for (int32 I = 0; I < Size * Size; ++I)
	{
		Pixels[I * 4 + 0] = Color.B;
		Pixels[I * 4 + 1] = Color.G;
		Pixels[I * 4 + 2] = Color.R;
		Pixels[I * 4 + 3] = Color.A;
	}
	return MakeTextureFromPixels(Name, Size, Size, Pixels, Kind, Kind == TEXT("color"));
}

void FVPBuilder::BuildTextures(FScopedSlowTask& Task)
{
	// textures par défaut des paramètres des matériaux maîtres
	MakeSolidTexture(TEXT("T_VP_DefautBlanc"), FColor(255, 255, 255, 255), TEXT("color"));
	MakeSolidTexture(TEXT("T_VP_DefautNormale"), FColor(128, 128, 255, 255), TEXT("normal"));
	MakeSolidTexture(TEXT("T_VP_DefautMasques"), FColor(255, 204, 0, 255), TEXT("masks"));

	const TArray<TSharedPtr<FJsonValue>>& List = Manifest->GetArrayField(TEXT("textures"));
	const float Step = 15.f / FMath::Max(1, List.Num());
	for (const TSharedPtr<FJsonValue>& Value : List)
	{
		const TSharedPtr<FJsonObject> T = Value->AsObject();
		const FString Name = T->GetStringField(TEXT("name"));
		Task.EnterProgressFrame(Step, FText::Format(LOCTEXT("Tex", "Texture {0}"), FText::FromString(Name)));
		MakeTexture(Name, DataFile(T->GetStringField(TEXT("file"))), T->GetStringField(TEXT("kind")), T->GetBoolField(TEXT("srgb")));
	}
}

// ------------------------------------------------------------------ maillages statiques

UStaticMesh* FVPBuilder::BuildStaticMesh(const FString& Name, const FString& Folder, const TArray<FVPLod>& Lods, bool bNanite,
	const FString& Collision, const TArray<float>& CollisionDims, const TArray<float>& LodScreenSizes, bool bFoliage)
{
	if (Lods.Num() == 0)
	{
		return nullptr;
	}
	TArray<FString> Slots;
	for (const FVPLod& Lod : Lods)
	{
		for (const FVPSection& Sec : Lod)
		{
			if (Sec.Indices.Num() > 0)
			{
				Slots.AddUnique(Sec.Material);
			}
		}
	}
	if (Slots.Num() == 0)
	{
		return nullptr;
	}

	UStaticMesh* Mesh = FindOrCreate<UStaticMesh>(FString(TEXT("Meshes")) / Folder, TEXT("SM_") + Name);
	Mesh->PreEditChange(nullptr);
	Mesh->SetNumSourceModels(Lods.Num());
	Mesh->GetStaticMaterials().Reset();
	for (const FString& Slot : Slots)
	{
		Mesh->GetStaticMaterials().Add(FStaticMaterial(GetMaterial(Slot), FName(*Slot), FName(*Slot)));
	}

	for (int32 L = 0; L < Lods.Num(); ++L)
	{
		FStaticMeshSourceModel& Source = Mesh->GetSourceModel(L);
		Source.BuildSettings.bRecomputeNormals = false;
		Source.BuildSettings.bRecomputeTangents = true;
		Source.BuildSettings.bUseMikkTSpace = true;
		Source.BuildSettings.bRemoveDegenerates = true;
		Source.BuildSettings.bUseFullPrecisionUVs = true;
		Source.BuildSettings.bGenerateLightmapUVs = false;
		Source.BuildSettings.bGenerateDistanceFieldAsIfTwoSided = bFoliage;
		Source.BuildSettings.DistanceFieldResolutionScale = bFoliage ? 0.5f : 1.0f;
		if (LodScreenSizes.IsValidIndex(L))
		{
			Source.ScreenSize.Default = LodScreenSizes[L];
		}

		const FVPLod& Lod = Lods[L];
		FMeshDescription Description;
		FStaticMeshAttributes Attributes(Description);
		Attributes.Register();
		TVertexAttributesRef<FVector3f> Positions = Attributes.GetVertexPositions();
		TVertexInstanceAttributesRef<FVector3f> Normals = Attributes.GetVertexInstanceNormals();
		TVertexInstanceAttributesRef<FVector2f> UVs = Attributes.GetVertexInstanceUVs();
		TVertexInstanceAttributesRef<FVector4f> Colors = Attributes.GetVertexInstanceColors();
		TPolygonGroupAttributesRef<FName> SlotNames = Attributes.GetPolygonGroupMaterialSlotNames();

		int32 MaxUV = 1;
		int32 TotalVertices = 0;
		int32 TotalTriangles = 0;
		for (const FVPSection& Sec : Lod)
		{
			MaxUV = FMath::Max(MaxUV, Sec.NumUV);
			TotalVertices += Sec.Positions.Num();
			TotalTriangles += Sec.Indices.Num() / 3;
		}
		UVs.SetNumChannels(MaxUV);
		Description.ReserveNewVertices(TotalVertices);
		Description.ReserveNewVertexInstances(TotalVertices);
		Description.ReserveNewTriangles(TotalTriangles);
		Description.ReserveNewPolygonGroups(Lod.Num());

		TArray<int32> SectionSlots;
		for (const FVPSection& Sec : Lod)
		{
			if (Sec.Indices.Num() == 0)
			{
				continue;
			}
			const FPolygonGroupID Group = Description.CreatePolygonGroup();
			SlotNames[Group] = FName(*Sec.Material);
			SectionSlots.Add(Slots.IndexOfByKey(Sec.Material));

			const int32 NV = Sec.Positions.Num();
			TArray<FVertexInstanceID> Instances;
			Instances.SetNumUninitialized(NV);
			for (int32 V = 0; V < NV; ++V)
			{
				const FVertexID Vertex = Description.CreateVertex();
				Positions[Vertex] = Sec.Positions[V];
				const FVertexInstanceID Instance = Description.CreateVertexInstance(Vertex);
				Normals[Instance] = Sec.Normals[V];
				for (int32 C = 0; C < MaxUV; ++C)
				{
					UVs.Set(Instance, C, C < Sec.NumUV ? Sec.UVs[V * Sec.NumUV + C] : FVector2f::ZeroVector);
				}
				Colors[Instance] = ToVertexColor(Sec.Colors[V]);
				Instances[V] = Instance;
			}
			for (int32 T = 0; T + 2 < Sec.Indices.Num(); T += 3)
			{
				const uint32 A = Sec.Indices[T], B = Sec.Indices[T + 1], C = Sec.Indices[T + 2];
				if (A == B || B == C || A == C || (int32)FMath::Max3(A, B, C) >= NV)
				{
					continue;
				}
				FVertexInstanceID Tri[3] = { Instances[A], Instances[B], Instances[C] };
				Description.CreateTriangle(Group, MakeArrayView(Tri, 3));
			}
		}
		Mesh->CreateMeshDescription(L, MoveTemp(Description));
		Mesh->CommitMeshDescription(L);
		for (int32 S = 0; S < SectionSlots.Num(); ++S)
		{
			FMeshSectionInfo Info(SectionSlots[S]);
			Info.bCastShadow = true;
			Info.bEnableCollision = true;
			Mesh->GetSectionInfoMap().Set(L, S, Info);
		}
	}
	Mesh->GetOriginalSectionInfoMap().CopyFrom(Mesh->GetSectionInfoMap());
	SetBoolByName(Mesh, TEXT("bAutoComputeLODScreenSize"), Lods.Num() == 1);

	// collisions
	Mesh->CreateBodySetup();
	if (UBodySetup* Body = Mesh->GetBodySetup())
	{
		Body->AggGeom.EmptyElements();
		if (Collision == TEXT("complex"))
		{
			Body->CollisionTraceFlag = CTF_UseComplexAsSimple;
		}
		else if (Collision == TEXT("capsule") && CollisionDims.Num() >= 2)
		{
			const float Radius = CollisionDims[0] * 100.f;
			const float Height = CollisionDims[1] * 100.f;
			FKSphylElem Capsule(Radius, FMath::Max(0.f, Height - 2.f * Radius));
			Capsule.Center = FVector(0.f, 0.f, Height * 0.5f);
			Body->AggGeom.SphylElems.Add(Capsule);
			Body->CollisionTraceFlag = CTF_UseSimpleAsComplex;
		}
		else if (Collision == TEXT("boxes") && CollisionDims.Num() >= 6)
		{
			// plusieurs boîtes décentrées : centre (x, y, z) puis taille (x, y, z), en mètres, repère Unreal
			for (int32 K = 0; K + 5 < CollisionDims.Num(); K += 6)
			{
				FKBoxElem Box(CollisionDims[K + 3] * 100.f, CollisionDims[K + 4] * 100.f, CollisionDims[K + 5] * 100.f);
				Box.Center = FVector(CollisionDims[K] * 100.f, CollisionDims[K + 1] * 100.f, CollisionDims[K + 2] * 100.f);
				Body->AggGeom.BoxElems.Add(Box);
			}
			Body->CollisionTraceFlag = CTF_UseSimpleAsComplex;
		}
		else if (Collision == TEXT("box") && CollisionDims.Num() >= 3)
		{
			FKBoxElem Box(CollisionDims[0] * 100.f, CollisionDims[1] * 100.f, CollisionDims[2] * 100.f);
			Box.Center = FVector(0.f, 0.f, CollisionDims[2] * 50.f);
			Body->AggGeom.BoxElems.Add(Box);
			Body->CollisionTraceFlag = CTF_UseSimpleAsComplex;
		}
		else
		{
			Body->CollisionTraceFlag = CTF_UseSimpleAsComplex;
			Body->DefaultInstance.SetCollisionEnabled(ECollisionEnabled::NoCollision);
		}
		Body->InvalidatePhysicsData();
	}

	SetNanite(Mesh, bNanite);
	Mesh->Build(true);
	Mesh->PostEditChange();
	Mesh->MarkPackageDirty();
	Meshes.Add(Name, Mesh);
	return Mesh;
}

void FVPBuilder::BuildMeshes(FScopedSlowTask& Task)
{
	const TArray<TSharedPtr<FJsonValue>>& List = Manifest->GetArrayField(TEXT("meshes"));
	const float Step = 40.f / FMath::Max(1, List.Num());
	for (const TSharedPtr<FJsonValue>& Value : List)
	{
		const TSharedPtr<FJsonObject> M = Value->AsObject();
		const FString Name = M->GetStringField(TEXT("name"));
		Task.EnterProgressFrame(Step, FText::Format(LOCTEXT("Mesh", "Maillage {0}"), FText::FromString(Name)));
		if (Task.ShouldCancel())
		{
			break;
		}
		TArray<FVPLod> Lods;
		if (!ReadPVM(DataFile(M->GetStringField(TEXT("file"))), Lods))
		{
			++Warnings;
			continue;
		}
		TArray<float> Dims;
		const TArray<TSharedPtr<FJsonValue>>* DimValues = nullptr;
		if (M->TryGetArrayField(TEXT("collision_dims"), DimValues))
		{
			for (const TSharedPtr<FJsonValue>& D : *DimValues)
			{
				Dims.Add((float)D->AsNumber());
			}
		}
		TArray<float> Sizes;
		const TArray<TSharedPtr<FJsonValue>>* SizeValues = nullptr;
		if (M->TryGetArrayField(TEXT("lod_screen_sizes"), SizeValues))
		{
			for (const TSharedPtr<FJsonValue>& D : *SizeValues)
			{
				Sizes.Add((float)D->AsNumber());
			}
		}
		bool bWind = false;
		M->TryGetBoolField(TEXT("wind"), bWind);
		BuildStaticMesh(Name, M->GetStringField(TEXT("folder")), Lods, M->GetBoolField(TEXT("nanite")), M->GetStringField(TEXT("collision")), Dims, Sizes, bWind);
	}
}

// ------------------------------------------------------------------ terrain (tuiles construites depuis la carte des hauteurs)

void FVPBuilder::BuildTerrain(FScopedSlowTask& Task)
{
	const TSharedPtr<FJsonObject> TerrainInfo = Manifest->GetObjectField(TEXT("terrain"));
	TArray<uint8> HFile, SFile;
	if (!FFileHelper::LoadFileToArray(HFile, *DataFile(TerrainInfo->GetStringField(TEXT("heights")))) ||
		!FFileHelper::LoadFileToArray(SFile, *DataFile(TerrainInfo->GetStringField(TEXT("layers")))) ||
		HFile.Num() < 44 || SFile.Num() < 20 || FMemory::Memcmp(HFile.GetData(), "PVH1", 4) != 0 || FMemory::Memcmp(SFile.GetData(), "PVS1", 4) != 0)
	{
		UE_LOG(LogVillageProvence, Error, TEXT("Terrain illisible"));
		++Warnings;
		return;
	}
	const int32 NX = (int32)VP::ReadU32(HFile, 4);
	const int32 NY = (int32)VP::ReadU32(HFile, 8);
	const float XMin = VP::ReadF32(HFile, 12);
	const float YMin = VP::ReadF32(HFile, 16);
	const float Res = VP::ReadF32(HFile, 20);
	const int32 HRaw = (int32)VP::ReadU32(HFile, 28);
	const int32 HComp = (int32)VP::ReadU32(HFile, 32);
	const float ZMin = VP::ReadF32(HFile, 36);
	const float ZMax = VP::ReadF32(HFile, 40);
	TArray<uint8> HeightBytes, LayerBytes;
	const int32 Channels = (int32)VP::ReadU32(SFile, 12);
	if (!ReadCompressed(HFile, 44, HRaw, HComp, HeightBytes) ||
		!ReadCompressed(SFile, 20, NX * NY * Channels, (int32)VP::ReadU32(SFile, 16), LayerBytes) || Channels < 8)
	{
		UE_LOG(LogVillageProvence, Error, TEXT("Terrain : décompression impossible"));
		++Warnings;
		return;
	}
	const uint16* H = reinterpret_cast<const uint16*>(HeightBytes.GetData());
	auto Height = [&](int32 I, int32 J) -> float
	{
		I = FMath::Clamp(I, 0, NX - 1);
		J = FMath::Clamp(J, 0, NY - 1);
		return ZMin + (ZMax - ZMin) * (H[J * NX + I] / 65535.f);
	};
	auto Layer = [&](int32 I, int32 J, int32 C) -> uint8
	{
		return LayerBytes[(J * NX + I) * Channels + C];
	};

	const int32 Q = (int32)TerrainInfo->GetNumberField(TEXT("tile_quads"));
	const float UVTile = (float)TerrainInfo->GetNumberField(TEXT("uv_tile_m"));
	const float Skirt = (float)TerrainInfo->GetNumberField(TEXT("skirt_m"));
	const int32 TilesX = (NX - 1) / Q;
	const int32 TilesY = (NY - 1) / Q;
	const float Step = 20.f / FMath::Max(1, TilesX * TilesY);

	for (int32 TY = 0; TY < TilesY; ++TY)
	{
		for (int32 TX = 0; TX < TilesX; ++TX)
		{
			const FString Name = FString::Printf(TEXT("Terrain_%02d_%02d"), TX, TY);
			Task.EnterProgressFrame(Step, FText::Format(LOCTEXT("Terrain", "Terrain {0}"), FText::FromString(Name)));
			const int32 I0 = TX * Q, J0 = TY * Q;
			float TileZMin = TNumericLimits<float>::Max();
			for (int32 J = J0; J <= J0 + Q; ++J)
			{
				for (int32 I = I0; I <= I0 + Q; ++I)
				{
					TileZMin = FMath::Min(TileZMin, Height(I, J));
				}
			}
			TileZMin -= Skirt;
			const float CX = XMin + (I0 + Q * 0.5f) * Res;
			const float CY = YMin + (J0 + Q * 0.5f) * Res;
			const float OffU = FMath::FloorToFloat(CX / UVTile);
			const float OffV = FMath::FloorToFloat(-CY / UVTile);

			TArray<FVPLod> Lods;
			Lods.SetNum(1);
			FVPSection& Sec = Lods[0].AddDefaulted_GetRef();
			Sec.Material = TerrainInfo->GetStringField(TEXT("material"));
			Sec.NumUV = 3;
			const int32 Side = Q + 1;
			auto AddVertex = [&](int32 I, int32 J, float ZOffset) -> uint32
			{
				const float X = XMin + I * Res;
				const float Y = YMin + J * Res;
				const float Z = Height(I, J) + ZOffset;
				const float DZX = (Height(I + 1, J) - Height(I - 1, J)) / (2.f * Res);
				const float DZY = (Height(I, J + 1) - Height(I, J - 1)) / (2.f * Res);
				const FVector3f NLocal = FVector3f(-DZX, -DZY, 1.f).GetSafeNormal();
				Sec.Positions.Add(FVector3f((X - CX) * 100.f, -(Y - CY) * 100.f, (Z - TileZMin) * 100.f));
				Sec.Normals.Add(FVector3f(NLocal.X, -NLocal.Y, NLocal.Z));
				Sec.UVs.Add(FVector2f(X / UVTile - OffU, -Y / UVTile - OffV));
				Sec.UVs.Add(FVector2f(Layer(I, J, 4) / 255.f, Layer(I, J, 5) / 255.f));
				Sec.UVs.Add(FVector2f(Layer(I, J, 6) / 255.f, Layer(I, J, 7) / 255.f));
				Sec.Colors.Add(FColor(Layer(I, J, 0), Layer(I, J, 1), Layer(I, J, 2), Layer(I, J, 3)));
				return (uint32)(Sec.Positions.Num() - 1);
			};
			for (int32 J = 0; J < Side; ++J)
			{
				for (int32 I = 0; I < Side; ++I)
				{
					AddVertex(I0 + I, J0 + J, 0.f);
				}
			}
			for (int32 J = 0; J < Q; ++J)
			{
				for (int32 I = 0; I < Q; ++I)
				{
					const uint32 A = J * Side + I, B = A + 1, C = A + Side + 1, D = A + Side;
					Sec.Indices.Append({ A, B, C, A, C, D });
				}
			}
			// jupe verticale sur le pourtour de la zone (masque le raccord avec l'horizon)
			auto AddSkirt = [&](int32 IA, int32 JA, int32 IB, int32 JB)
			{
				const uint32 P = (uint32)((JA - J0) * Side + (IA - I0));
				const uint32 Qv = (uint32)((JB - J0) * Side + (IB - I0));
				const uint32 P2 = AddVertex(IA, JA, -Skirt);
				const uint32 Q2 = AddVertex(IB, JB, -Skirt);
				Sec.Indices.Append({ P2, Q2, Qv, P2, Qv, P });
			};
			for (int32 K = 0; K < Q; ++K)
			{
				if (TY == 0)
				{
					AddSkirt(I0 + K, J0, I0 + K + 1, J0);
				}
				if (TX == TilesX - 1)
				{
					AddSkirt(I0 + Q, J0 + K, I0 + Q, J0 + K + 1);
				}
				if (TY == TilesY - 1)
				{
					AddSkirt(I0 + Q - K, J0 + Q, I0 + Q - K - 1, J0 + Q);
				}
				if (TX == 0)
				{
					AddSkirt(I0, J0 + Q - K, I0, J0 + Q - K - 1);
				}
			}
			if (UStaticMesh* Mesh = BuildStaticMesh(Name, TEXT("Terrain"), Lods, true, TEXT("complex"), {}, {}, false))
			{
				TerrainTiles.Add({ Name, FVector(CX * 100.f, -CY * 100.f, TileZMin * 100.f) });
			}
		}
	}
}

void FVPBuilder::LoadExistingAssets()
{
	for (const TPair<FString, TSharedPtr<FJsonObject>>& Pair : MeshInfo)
	{
		const FString Folder = FString(TEXT("Meshes")) / Pair.Value->GetStringField(TEXT("folder"));
		if (UStaticMesh* Mesh = FindExisting<UStaticMesh>(Folder, TEXT("SM_") + Pair.Key))
		{
			Meshes.Add(Pair.Key, Mesh);
		}
	}
	for (const TPair<FString, TSharedPtr<FJsonObject>>& Pair : MaterialInfo)
	{
		if (UMaterialInterface* Mat = FindExisting<UMaterialInterface>(TEXT("Materials"), TEXT("MI_") + Pair.Key))
		{
			Materials.Add(Pair.Key, Mat);
		}
	}
	// tuiles de terrain déjà construites : leur position est recalculée depuis la carte des hauteurs
	const TSharedPtr<FJsonObject> TerrainInfo = Manifest->GetObjectField(TEXT("terrain"));
	TArray<uint8> HFile;
	if (FFileHelper::LoadFileToArray(HFile, *DataFile(TerrainInfo->GetStringField(TEXT("heights")))) && HFile.Num() >= 44)
	{
		const int32 NX = (int32)VP::ReadU32(HFile, 4);
		const int32 NY = (int32)VP::ReadU32(HFile, 8);
		const float XMin = VP::ReadF32(HFile, 12);
		const float YMin = VP::ReadF32(HFile, 16);
		const float Res = VP::ReadF32(HFile, 20);
		const int32 HRaw = (int32)VP::ReadU32(HFile, 28);
		const int32 HComp = (int32)VP::ReadU32(HFile, 32);
		const float ZMin = VP::ReadF32(HFile, 36);
		const float ZMax = VP::ReadF32(HFile, 40);
		TArray<uint8> HeightBytes;
		const int32 Q = (int32)TerrainInfo->GetNumberField(TEXT("tile_quads"));
		const float Skirt = (float)TerrainInfo->GetNumberField(TEXT("skirt_m"));
		if (ReadCompressed(HFile, 44, HRaw, HComp, HeightBytes))
		{
			const uint16* H = reinterpret_cast<const uint16*>(HeightBytes.GetData());
			for (int32 TY = 0; TY < (NY - 1) / Q; ++TY)
			{
				for (int32 TX = 0; TX < (NX - 1) / Q; ++TX)
				{
					const FString Name = FString::Printf(TEXT("Terrain_%02d_%02d"), TX, TY);
					UStaticMesh* Mesh = FindExisting<UStaticMesh>(TEXT("Meshes/Terrain"), TEXT("SM_") + Name);
					if (!Mesh)
					{
						continue;
					}
					float TileZMin = TNumericLimits<float>::Max();
					for (int32 J = TY * Q; J <= TY * Q + Q; ++J)
					{
						for (int32 I = TX * Q; I <= TX * Q + Q; ++I)
						{
							TileZMin = FMath::Min(TileZMin, ZMin + (ZMax - ZMin) * (H[J * NX + I] / 65535.f));
						}
					}
					TileZMin -= Skirt;
					const float CX = XMin + (TX * Q + Q * 0.5f) * Res;
					const float CY = YMin + (TY * Q + Q * 0.5f) * Res;
					Meshes.Add(Name, Mesh);
					TerrainTiles.Add({ Name, FVector(CX * 100.f, -CY * 100.f, TileZMin * 100.f) });
				}
			}
		}
	}
}

// ------------------------------------------------------------------ déroulement

bool FVPBuilder::Run()
{
	World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World)
	{
		return false;
	}
	if (Mode == EMode::Remove)
	{
		RemoveVillageActors();
		GEditor->RedrawAllViewports();
		return true;
	}
	if (!LoadManifest())
	{
		FMessageDialog::Open(EAppMsgType::Ok, FText::Format(LOCTEXT("NoData", "Données du village introuvables dans :\n{0}\n\nVérifie que le dossier Data du plugin a bien été copié."), FText::FromString(DataDir)));
		return false;
	}
	const double Start = FPlatformTime::Seconds();
	FScopedSlowTask Task(100.f, LOCTEXT("Building", "Construction du village provençal..."));
	Task.MakeDialog(true);

	if (Mode == EMode::Full)
	{
		BuildTextures(Task);
		BuildMaterials(Task);
		BuildMeshes(Task);
		BuildTerrain(Task);
	}
	else
	{
		Task.EnterProgressFrame(10.f, LOCTEXT("Loading", "Chargement des assets existants..."));
		LoadExistingAssets();
		if (Meshes.Num() == 0)
		{
			FMessageDialog::Open(EAppMsgType::Ok, LOCTEXT("NoAssets", "Aucun asset trouvé dans /Game/VillageProvence. Lance d'abord « Construire le village provençal »."));
			return false;
		}
	}

	Task.EnterProgressFrame(2.f, LOCTEXT("Cleaning", "Nettoyage du niveau..."));
	RemoveVillageActors();
	SpawnMeshActors(Task);
	SpawnInstances(Task);
	Task.EnterProgressFrame(2.f, LOCTEXT("Ambiance", "Lumière, ciel et sons..."));
	SetupAmbiance();
	SetupSounds();
	SetupZombies();
	Task.EnterProgressFrame(3.f, LOCTEXT("Saving", "Enregistrement des assets..."));
	UEditorLoadingAndSavingUtils::SaveDirtyPackages(false, true);
	GEditor->RedrawAllViewports();

	const int32 Minutes = FMath::RoundToInt((FPlatformTime::Seconds() - Start) / 60.0);
	FMessageDialog::Open(EAppMsgType::Ok, FText::Format(
		LOCTEXT("Done", "Village construit en {0} min ({1} avertissements, voir le journal « LogVillageProvence »).\n\nPense à enregistrer le niveau (Ctrl+S). Le point de départ du joueur est sur la place de la mairie."),
		FText::AsNumber(Minutes), FText::AsNumber(Warnings)));
	return true;
}

#undef LOCTEXT_NAMESPACE
