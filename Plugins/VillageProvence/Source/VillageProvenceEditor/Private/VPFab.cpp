#include "VPFab.h"
#include "VPBuilder.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "FileHelpers.h"
#include "Interfaces/IPluginManager.h"
#include "MaterialEditingLibrary.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	const FString Root = TEXT("/Game/VillageProvence");

	// un jeu de textures d'une même surface (couleur, normale, occlusion-rugosité-déplacement)
	struct FTexSet
	{
		FString Name;
		UTexture2D* BaseColor = nullptr;
		UTexture2D* Normal = nullptr;
		UTexture2D* Packed = nullptr;
		UTexture2D* Roughness = nullptr;
	};

	FString DataDir()
	{
		TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("VillageProvence"));
		return Plugin.IsValid() ? Plugin->GetBaseDir() / TEXT("Data") : FString();
	}

	TSharedPtr<FJsonObject> LoadJson(const FString& File)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *File))
		{
			return nullptr;
		}
		TSharedPtr<FJsonObject> Obj;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
		return FJsonSerializer::Deserialize(Reader, Obj) ? Obj : nullptr;
	}

	// type de carte d'après le suffixe (T_Surface_xyz_2K_D, ..._BaseColor, ..._N, ..._Normal, ..._ORDp, ..._ORM, ..._ARM, ..._Roughness)
	int32 MapKind(const FString& Token)
	{
		const FString T = Token.ToLower();
		if (T == TEXT("d") || T == TEXT("bc") || T == TEXT("basecolor") || T == TEXT("albedo") || T == TEXT("diffuse") || T == TEXT("color") || T == TEXT("col"))
		{
			return 0;
		}
		if (T == TEXT("n") || T == TEXT("normal") || T == TEXT("nrm") || T == TEXT("normaldx") || T == TEXT("normalgl"))
		{
			return 1;
		}
		if (T == TEXT("ordp") || T == TEXT("ord") || T == TEXT("orm") || T == TEXT("arm") || T == TEXT("ords"))
		{
			return 2;
		}
		if (T == TEXT("r") || T == TEXT("roughness") || T == TEXT("rough"))
		{
			return 3;
		}
		return -1;
	}

	bool IsResolution(const FString& Token)
	{
		const FString T = Token.ToLower();
		return T == TEXT("1k") || T == TEXT("2k") || T == TEXT("4k") || T == TEXT("8k") || T == TEXT("512") || T == TEXT("1024") || T == TEXT("2048") || T == TEXT("4096");
	}

	// toutes les textures du projet hors du village et du moteur, regroupées par surface
	TMap<FString, FTexSet> ScanProject()
	{
		TMap<FString, FTexSet> Sets;
		IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
		FARFilter Filter;
		Filter.ClassPaths.Add(UTexture2D::StaticClass()->GetClassPathName());
		Filter.bRecursiveClasses = true;
		Filter.PackagePaths.Add(FName(TEXT("/Game")));
		Filter.bRecursivePaths = true;
		TArray<FAssetData> Assets;
		Registry.GetAssets(Filter, Assets);
		for (const FAssetData& Asset : Assets)
		{
			const FString Path = Asset.PackageName.ToString();
			if (Path.StartsWith(Root))
			{
				continue;
			}
			TArray<FString> Tokens;
			Asset.AssetName.ToString().ParseIntoArray(Tokens, TEXT("_"));
			if (Tokens.Num() < 2)
			{
				continue;
			}
			const int32 Kind = MapKind(Tokens.Last());
			if (Kind < 0)
			{
				continue;
			}
			Tokens.Pop();
			while (Tokens.Num() > 1 && IsResolution(Tokens.Last()))
			{
				Tokens.Pop();
			}
			if (Tokens.Num() > 0 && Tokens[0].Equals(TEXT("T"), ESearchCase::IgnoreCase))
			{
				Tokens.RemoveAt(0);
			}
			const FString Base = FString::Join(Tokens, TEXT(" "));
			FTexSet& Set = Sets.FindOrAdd(Asset.PackagePath.ToString() / Base);
			Set.Name = Base;
			UTexture2D* Tex = Cast<UTexture2D>(Asset.GetAsset());
			switch (Kind)
			{
			case 0: Set.BaseColor = Tex; break;
			case 1: Set.Normal = Tex; break;
			case 2: Set.Packed = Tex; break;
			default: Set.Roughness = Tex; break;
			}
		}
		return Sets;
	}

	// meilleure surface pour une liste de mots-clés (le premier mot-clé trouvé l'emporte, puis la surface la plus complète)
	const FTexSet* Pick(const TMap<FString, FTexSet>& Sets, const TArray<TSharedPtr<FJsonValue>>& Keywords)
	{
		const FTexSet* Best = nullptr;
		int32 BestScore = MAX_int32;
		for (const TPair<FString, FTexSet>& Pair : Sets)
		{
			const FTexSet& S = Pair.Value;
			if (!S.BaseColor)
			{
				continue;
			}
			const FString Name = S.Name.ToLower();
			for (int32 K = 0; K < Keywords.Num(); ++K)
			{
				if (Name.Contains(Keywords[K]->AsString().ToLower()))
				{
					const int32 Score = K * 1000 + (S.Normal ? 0 : 200) + (S.Packed ? 0 : 100) + Name.Len();
					if (Score < BestScore)
					{
						BestScore = Score;
						Best = &S;
					}
					break;
				}
			}
		}
		return Best;
	}

	UMaterialInstanceConstant* FindMI(const FString& Name)
	{
		const FString Path = Root / TEXT("Materials") / TEXT("MI_") + Name + TEXT(".MI_") + Name;
		return LoadObject<UMaterialInstanceConstant>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
	}

	UTexture2D* FindVillageTexture(const FString& Name)
	{
		const FString Path = Root / TEXT("Textures") / Name + TEXT(".") + Name;
		return LoadObject<UTexture2D>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
	}

	void SetTex(UMaterialInstanceConstant* MI, const TCHAR* Param, UTexture2D* Tex)
	{
		if (Tex)
		{
			UMaterialEditingLibrary::SetMaterialInstanceTextureParameterValue(MI, FName(Param), Tex);
		}
	}

	void SetScalar(UMaterialInstanceConstant* MI, const TCHAR* Param, float Value)
	{
		UMaterialEditingLibrary::SetMaterialInstanceScalarParameterValue(MI, FName(Param), Value);
	}

	void Finish(UMaterialInstanceConstant* MI)
	{
		UMaterialEditingLibrary::UpdateMaterialInstance(MI);
		MI->PostEditChange();
		MI->MarkPackageDirty();
	}

	// taille réelle couverte par une répétition des textures d'origine (UV des maillages = mètres / taille)
	TMap<FString, float> OriginalTiles(const TSharedPtr<FJsonObject>& Manifest)
	{
		TMap<FString, float> Out;
		for (const TSharedPtr<FJsonValue>& V : Manifest->GetArrayField(TEXT("materials")))
		{
			const TSharedPtr<FJsonObject> M = V->AsObject();
			double Tile = 1.0;
			M->TryGetNumberField(TEXT("tile_m"), Tile);
			Out.Add(M->GetStringField(TEXT("name")), (float)Tile);
		}
		return Out;
	}
}

FString FVPFab::Apply()
{
	const TSharedPtr<FJsonObject> Config = LoadJson(DataDir() / TEXT("TexturesFab.json"));
	const TSharedPtr<FJsonObject> Manifest = LoadJson(DataDir() / TEXT("Village.json"));
	if (!Config || !Manifest)
	{
		return TEXT("Fichiers Data/TexturesFab.json ou Data/Village.json introuvables ou illisibles.");
	}
	const TMap<FString, FTexSet> Sets = ScanProject();
	if (Sets.Num() == 0)
	{
		return TEXT("Aucune texture Fab / Megascans trouvée dans le projet.\n\nAjoute d'abord des surfaces depuis Fab (fenêtre Fab dans l'éditeur, bouton Add to Project), puis relance la commande.");
	}
	const TMap<FString, float> Tiles = OriginalTiles(Manifest);
	TArray<FString> Report;
	int32 Done = 0;

	for (const TSharedPtr<FJsonValue>& V : Config->GetArrayField(TEXT("materiaux")))
	{
		const TSharedPtr<FJsonObject> Entry = V->AsObject();
		const FString Name = Entry->GetStringField(TEXT("materiau"));
		const FTexSet* Set = Pick(Sets, Entry->GetArrayField(TEXT("mots_cles")));
		UMaterialInstanceConstant* MI = FindMI(Name);
		if (!MI)
		{
			continue;
		}
		if (!Set)
		{
			Report.Add(FString::Printf(TEXT("  %s : aucune surface trouvée"), *Name));
			continue;
		}
		MI->PreEditChange(nullptr);
		SetTex(MI, TEXT("BaseColor"), Set->BaseColor);
		SetTex(MI, TEXT("Normal"), Set->Normal);
		// canal R = occlusion, G = rugosité ; à défaut, la rugosité seule
		SetTex(MI, TEXT("ORM"), Set->Packed ? Set->Packed : Set->Roughness);
		const double Size = Entry->HasField(TEXT("taille_m")) ? Entry->GetNumberField(TEXT("taille_m")) : 2.0;
		SetScalar(MI, TEXT("Tiling"), Tiles.FindRef(Name) > 0.f ? Tiles.FindRef(Name) / (float)FMath::Max(0.1, Size) : 1.f);
		const FString Tint = Entry->HasField(TEXT("teinte")) ? Entry->GetStringField(TEXT("teinte")) : TEXT("coupee");
		SetScalar(MI, TEXT("TeinteForcee"), Tint == TEXT("forcee") ? 1.f : 0.f);
		SetScalar(MI, TEXT("TeinteCoupee"), Tint == TEXT("coupee") ? 1.f : 0.f);
		Finish(MI);
		Report.Add(FString::Printf(TEXT("  %s  <-  %s"), *Name, *Set->Name));
		++Done;
	}

	// couches du terrain
	if (UMaterialInstanceConstant* Terrain = FindMI(TEXT("Terrain")))
	{
		TArray<FString> Layers;
		for (const TSharedPtr<FJsonValue>& L : Manifest->GetObjectField(TEXT("terrain"))->GetArrayField(TEXT("layer_names")))
		{
			Layers.Add(L->AsString());
		}
		const TSharedPtr<FJsonObject>* TerrainCfg = nullptr;
		if (Config->TryGetObjectField(TEXT("terrain"), TerrainCfg))
		{
			Terrain->PreEditChange(nullptr);
			bool bAny = false;
			for (int32 K = 0; K < Layers.Num(); ++K)
			{
				const TArray<TSharedPtr<FJsonValue>>* Keywords = nullptr;
				if (!(*TerrainCfg)->TryGetArrayField(Layers[K], Keywords))
				{
					continue;
				}
				if (const FTexSet* Set = Pick(Sets, *Keywords))
				{
					SetTex(Terrain, *FString::Printf(TEXT("BC%d"), K), Set->BaseColor);
					SetTex(Terrain, *FString::Printf(TEXT("N%d"), K), Set->Normal);
					SetTex(Terrain, *FString::Printf(TEXT("ORM%d"), K), Set->Packed ? Set->Packed : Set->Roughness);
					Report.Add(FString::Printf(TEXT("  Terrain / %s  <-  %s"), *Layers[K], *Set->Name));
					bAny = true;
					++Done;
				}
			}
			if (bAny)
			{
				double Size = 2.0;
				Config->TryGetNumberField(TEXT("terrain_taille_m"), Size);
				SetScalar(Terrain, TEXT("Tiling"), Tiles.FindRef(TEXT("Terrain")) > 0.f ? Tiles.FindRef(TEXT("Terrain")) / (float)FMath::Max(0.1, Size) : 1.f);
			}
			Finish(Terrain);
		}
	}
	UEditorLoadingAndSavingUtils::SaveDirtyPackages(false, true);
	return FString::Printf(TEXT("%d matériaux utilisent maintenant des textures Fab / Megascans :\n\n%s"), Done, *FString::Join(Report, TEXT("\n")));
}

FString FVPFab::Restore()
{
	const TSharedPtr<FJsonObject> Manifest = LoadJson(DataDir() / TEXT("Village.json"));
	if (!Manifest)
	{
		return TEXT("Fichier Data/Village.json introuvable.");
	}
	int32 Done = 0;
	for (const TSharedPtr<FJsonValue>& V : Manifest->GetArrayField(TEXT("materials")))
	{
		const TSharedPtr<FJsonObject> Info = V->AsObject();
		const FString Name = Info->GetStringField(TEXT("name"));
		UMaterialInstanceConstant* MI = FindMI(Name);
		if (!MI)
		{
			continue;
		}
		MI->PreEditChange(nullptr);
		FString TexName;
		if (Info->TryGetStringField(TEXT("BC"), TexName))
		{
			SetTex(MI, TEXT("BaseColor"), FindVillageTexture(TexName));
		}
		if (Info->TryGetStringField(TEXT("N"), TexName))
		{
			SetTex(MI, TEXT("Normal"), FindVillageTexture(TexName));
		}
		if (Info->TryGetStringField(TEXT("ORM"), TexName))
		{
			SetTex(MI, TEXT("ORM"), FindVillageTexture(TexName));
		}
		const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
		if (Info->TryGetArrayField(TEXT("layers"), Layers))
		{
			for (int32 L = 0; L < Layers->Num(); ++L)
			{
				const TSharedPtr<FJsonObject> Layer = (*Layers)[L]->AsObject();
				for (const TCHAR* Kind : { TEXT("BC"), TEXT("N"), TEXT("ORM") })
				{
					SetTex(MI, *FString::Printf(TEXT("%s%d"), Kind, L), FindVillageTexture(Layer->GetStringField(Kind)));
				}
			}
		}
		SetScalar(MI, TEXT("Tiling"), 1.f);
		SetScalar(MI, TEXT("TeinteForcee"), 0.f);
		SetScalar(MI, TEXT("TeinteCoupee"), 0.f);
		Finish(MI);
		++Done;
	}
	UEditorLoadingAndSavingUtils::SaveDirtyPackages(false, true);
	return FString::Printf(TEXT("%d matériaux ont retrouvé les textures d'origine du village."), Done);
}
