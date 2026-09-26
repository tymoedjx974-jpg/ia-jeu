#include "VPBuilder.h"

#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "MaterialEditingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/MaterialExpressionAdd.h"
#include "Materials/MaterialExpressionAppendVector.h"
#include "Materials/MaterialExpressionComponentMask.h"
#include "Materials/MaterialExpressionConstant.h"
#include "Materials/MaterialExpressionConstant3Vector.h"
#include "Materials/MaterialExpressionLinearInterpolate.h"
#include "Materials/MaterialExpressionMultiply.h"
#include "Materials/MaterialExpressionPanner.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionSine.h"
#include "Materials/MaterialExpressionTextureCoordinate.h"
#include "Materials/MaterialExpressionTextureSampleParameter2D.h"
#include "Materials/MaterialExpressionTime.h"
#include "Materials/MaterialExpressionVectorParameter.h"
#include "Materials/MaterialExpressionVertexColor.h"
#include "Materials/MaterialExpressionPerInstanceRandom.h"
#include "Misc/ScopedSlowTask.h"
#include "Runtime/Launch/Resources/Version.h"
#include "UObject/UnrealType.h"

#define LOCTEXT_NAMESPACE "VillageProvence"

// Entrées du matériau : déplacées dans UMaterialEditorOnlyData à partir de la 5.1
#if ENGINE_MAJOR_VERSION > 5 || (ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 1)
#define VP_INPUT(Mat, Prop) (Mat)->GetEditorOnlyData()->Prop
#else
#define VP_INPUT(Mat, Prop) (Mat)->Prop
#endif

namespace
{
	// sorties des nœuds de texture / couleur de sommet / vecteur : 0 = RGB, 1 = R, 2 = G, 3 = B, 4 = A
	constexpr int32 OutRGB = 0, OutR = 1, OutG = 2, OutB = 3, OutA = 4;

	template <class T>
	T* Node(UMaterial* M, int32 X, int32 Y)
	{
		return Cast<T>(UMaterialEditingLibrary::CreateMaterialExpression(M, T::StaticClass(), X, Y));
	}

	UMaterialExpressionTextureSampleParameter2D* TexParam(UMaterial* M, const TCHAR* Name, UTexture* Default, EMaterialSamplerType Type,
		UMaterialExpression* UV, int32 X, int32 Y, bool bShared = false)
	{
		UMaterialExpressionTextureSampleParameter2D* T = Node<UMaterialExpressionTextureSampleParameter2D>(M, X, Y);
		T->ParameterName = FName(Name);
		T->Texture = Default;
		T->SamplerType = Type;
		if (bShared)
		{
			T->SamplerSource = SSM_Wrap_WorldGroupSettings;
		}
		if (UV)
		{
			T->Coordinates.Connect(0, UV);
		}
		return T;
	}

	UMaterialExpressionScalarParameter* Scalar(UMaterial* M, const TCHAR* Name, float Default, int32 X, int32 Y)
	{
		UMaterialExpressionScalarParameter* P = Node<UMaterialExpressionScalarParameter>(M, X, Y);
		P->ParameterName = FName(Name);
		P->DefaultValue = Default;
		return P;
	}

	UMaterialExpressionVectorParameter* Vector(UMaterial* M, const TCHAR* Name, FLinearColor Default, int32 X, int32 Y)
	{
		UMaterialExpressionVectorParameter* P = Node<UMaterialExpressionVectorParameter>(M, X, Y);
		P->ParameterName = FName(Name);
		P->DefaultValue = Default;
		return P;
	}

	UMaterialExpressionConstant* Const(UMaterial* M, float Value, int32 X, int32 Y)
	{
		UMaterialExpressionConstant* C = Node<UMaterialExpressionConstant>(M, X, Y);
		C->R = Value;
		return C;
	}

	UMaterialExpressionMultiply* Mul(UMaterial* M, UMaterialExpression* EA, int32 OA, UMaterialExpression* EB, int32 OB, int32 X, int32 Y, float ConstB = 1.f)
	{
		UMaterialExpressionMultiply* N = Node<UMaterialExpressionMultiply>(M, X, Y);
		N->A.Connect(OA, EA);
		if (EB)
		{
			N->B.Connect(OB, EB);
		}
		else
		{
			N->ConstB = ConstB;
		}
		return N;
	}

	UMaterialExpressionAdd* Add(UMaterial* M, UMaterialExpression* EA, int32 OA, UMaterialExpression* EB, int32 OB, int32 X, int32 Y)
	{
		UMaterialExpressionAdd* N = Node<UMaterialExpressionAdd>(M, X, Y);
		N->A.Connect(OA, EA);
		N->B.Connect(OB, EB);
		return N;
	}

	UMaterialExpressionComponentMask* Mask(UMaterial* M, UMaterialExpression* In, int32 Out, bool bR, bool bG, bool bB, bool bA, int32 X, int32 Y)
	{
		UMaterialExpressionComponentMask* N = Node<UMaterialExpressionComponentMask>(M, X, Y);
		N->Input.Connect(Out, In);
		N->R = bR;
		N->G = bG;
		N->B = bB;
		N->A = bA;
		return N;
	}

	// propriétés booléennes du matériau réglées par réflexion (accès C++ variable selon les versions)
	void SetFlag(UMaterial* M, const TCHAR* Name, bool bValue)
	{
		if (FBoolProperty* Prop = FindFProperty<FBoolProperty>(UMaterial::StaticClass(), Name))
		{
			Prop->SetPropertyValue_InContainer(M, bValue);
		}
	}

	void Finish(UMaterial* M)
	{
		SetFlag(M, TEXT("bUsedWithInstancedStaticMeshes"), true);
		SetFlag(M, TEXT("bUsedWithNanite"), true);
		UMaterialEditingLibrary::RecompileMaterial(M);
		M->MarkPackageDirty();
	}
}

UMaterial* FVPBuilder::BuildMaster(const FString& Type)
{
	UMaterial* M = FindOrCreate<UMaterial>(TEXT("Materials/Maitres"), TEXT("M_VP_") + Type);
	M->PreEditChange(nullptr);
	UMaterialEditingLibrary::DeleteAllMaterialExpressions(M);

	UTexture* White = Textures.FindRef(TEXT("T_VP_DefautBlanc"));
	UTexture* Flat = Textures.FindRef(TEXT("T_VP_DefautNormale"));
	UTexture* Masks = Textures.FindRef(TEXT("T_VP_DefautMasques"));

	M->BlendMode = BLEND_Opaque;
	SetFlag(M, TEXT("TwoSided"), false);
	M->SetShadingModel(MSM_DefaultLit);

	if (Type == TEXT("Base"))
	{
		// couleur = texture x mélange(1, couleur de sommet² x teinte, masque de teinte) ; ORM = occlusion, rugosité, masque
		UMaterialExpressionTextureCoordinate* UV0 = Node<UMaterialExpressionTextureCoordinate>(M, -1600, 0);
		UMaterialExpressionMultiply* UV = Mul(M, UV0, 0, Scalar(M, TEXT("Tiling"), 1.f, -1600, 150), 0, -1400, 0);
		UMaterialExpressionTextureSampleParameter2D* BC = TexParam(M, TEXT("BaseColor"), White, SAMPLERTYPE_Color, UV, -1100, -300);
		UMaterialExpressionTextureSampleParameter2D* NM = TexParam(M, TEXT("Normal"), Flat, SAMPLERTYPE_Normal, UV, -1100, 300);
		UMaterialExpressionTextureSampleParameter2D* ORM = TexParam(M, TEXT("ORM"), Masks, SAMPLERTYPE_Masks, UV, -1100, 0);
		UMaterialExpressionVertexColor* VC = Node<UMaterialExpressionVertexColor>(M, -1100, -600);
		UMaterialExpressionMultiply* VC2 = Mul(M, VC, OutRGB, VC, OutRGB, -850, -600);
		UMaterialExpressionMultiply* Tint = Mul(M, VC2, 0, Vector(M, TEXT("Teinte"), FLinearColor::White, -850, -450), OutRGB, -650, -550);
		UMaterialExpressionConstant3Vector* One = Node<UMaterialExpressionConstant3Vector>(M, -650, -700);
		One->Constant = FLinearColor::White;
		UMaterialExpressionLinearInterpolate* TintMix = Node<UMaterialExpressionLinearInterpolate>(M, -450, -550);
		TintMix->A.Connect(0, One);
		TintMix->B.Connect(0, Tint);
		TintMix->Alpha.Connect(OutB, ORM);
		UMaterialExpressionMultiply* Color = Mul(M, BC, OutRGB, TintMix, 0, -250, -400);
		UMaterialExpressionMultiply* Rough = Mul(M, ORM, OutG, Scalar(M, TEXT("EchelleRugosite"), 1.f, -850, 100), 0, -450, 50);
		VP_INPUT(M, BaseColor).Connect(0, Color);
		VP_INPUT(M, Normal).Connect(OutRGB, NM);
		VP_INPUT(M, Roughness).Connect(0, Rough);
		VP_INPUT(M, AmbientOcclusion).Connect(OutR, ORM);
		VP_INPUT(M, Metallic).Connect(0, Scalar(M, TEXT("Metal"), 0.f, -450, 200));
		VP_INPUT(M, Specular).Connect(0, Scalar(M, TEXT("Speculaire"), 0.5f, -450, 300));
	}
	else if (Type == TEXT("Feuillage"))
	{
		// feuillage : découpe alpha, deux faces, translucidité des feuilles, vent (alpha des sommets)
		M->BlendMode = BLEND_Masked;
		SetFlag(M, TEXT("TwoSided"), true);
		M->SetShadingModel(MSM_TwoSidedFoliage);
		M->OpacityMaskClipValue = 0.4f;
		UMaterialExpressionTextureCoordinate* UV0 = Node<UMaterialExpressionTextureCoordinate>(M, -1600, 0);
		UMaterialExpressionTextureSampleParameter2D* BC = TexParam(M, TEXT("BaseColor"), White, SAMPLERTYPE_Color, UV0, -1200, -300);
		UMaterialExpressionTextureSampleParameter2D* NM = TexParam(M, TEXT("Normal"), Flat, SAMPLERTYPE_Normal, UV0, -1200, 200);
		UMaterialExpressionVertexColor* VC = Node<UMaterialExpressionVertexColor>(M, -1200, -700);
		UMaterialExpressionMultiply* VC2 = Mul(M, VC, OutRGB, VC, OutRGB, -950, -700);
		UMaterialExpressionMultiply* C1 = Mul(M, BC, OutRGB, VC2, 0, -750, -500);
		UMaterialExpressionMultiply* Color = Mul(M, C1, 0, Vector(M, TEXT("Teinte"), FLinearColor::White, -950, -400), OutRGB, -550, -450);
		VP_INPUT(M, BaseColor).Connect(0, Color);
		VP_INPUT(M, OpacityMask).Connect(OutA, BC);
		VP_INPUT(M, Normal).Connect(OutRGB, NM);
		VP_INPUT(M, Roughness).Connect(0, Scalar(M, TEXT("Rugosite"), 0.6f, -550, 0));
		VP_INPUT(M, SubsurfaceColor).Connect(0, Mul(M, Color, 0, nullptr, 0, -350, -300, 0.7f));
		// vent : décalage sinusoïdal proportionnel à l'alpha du sommet, phase selon la position dans le monde
		// phase propre à chaque instance (PerInstanceRandom) : pas de position monde, donc pas de souci de précision
		UMaterialExpressionTime* Time = Node<UMaterialExpressionTime>(M, -1500, 600);
		UMaterialExpressionPerInstanceRandom* Random = Node<UMaterialExpressionPerInstanceRandom>(M, -1500, 750);
		UMaterialExpressionMultiply* Speed = Mul(M, Time, 0, nullptr, 0, -1300, 600, 0.28f);
		UMaterialExpressionSine* Sine = Node<UMaterialExpressionSine>(M, -850, 650);
		Sine->Input.Connect(0, Add(M, Speed, 0, Random, 0, -1000, 650));
		UMaterialExpressionMultiply* Amp = Mul(M, VC, OutA, Scalar(M, TEXT("Vent"), 1.f, -850, 850), 0, -700, 800);
		UMaterialExpressionMultiply* Off = Mul(M, Sine, 0, Amp, 0, -550, 700);
		UMaterialExpressionAppendVector* XY = Node<UMaterialExpressionAppendVector>(M, -350, 700);
		XY->A.Connect(0, Mul(M, Off, 0, nullptr, 0, -450, 650, 7.f));
		XY->B.Connect(0, Mul(M, Off, 0, nullptr, 0, -450, 750, 4.5f));
		UMaterialExpressionAppendVector* XYZ = Node<UMaterialExpressionAppendVector>(M, -200, 700);
		XYZ->A.Connect(0, XY);
		XYZ->B.Connect(0, Const(M, 0.f, -350, 800));
		VP_INPUT(M, WorldPositionOffset).Connect(0, XYZ);
	}
	else if (Type == TEXT("Enseigne"))
	{
		M->BlendMode = BLEND_Masked;
		M->OpacityMaskClipValue = 0.5f;
		UMaterialExpressionTextureCoordinate* UV0 = Node<UMaterialExpressionTextureCoordinate>(M, -900, 0);
		UMaterialExpressionTextureSampleParameter2D* BC = TexParam(M, TEXT("BaseColor"), White, SAMPLERTYPE_Color, UV0, -600, 0);
		VP_INPUT(M, BaseColor).Connect(OutRGB, BC);
		VP_INPUT(M, OpacityMask).Connect(OutA, BC);
		VP_INPUT(M, Roughness).Connect(0, Scalar(M, TEXT("Rugosite"), 0.55f, -300, 200));
	}
	else if (Type == TEXT("Couleur"))
	{
		VP_INPUT(M, BaseColor).Connect(OutRGB, Vector(M, TEXT("Couleur"), FLinearColor(0.5f, 0.5f, 0.5f), -500, 0));
		VP_INPUT(M, Roughness).Connect(0, Scalar(M, TEXT("Rugosite"), 0.5f, -500, 200));
		VP_INPUT(M, Metallic).Connect(0, Scalar(M, TEXT("Metal"), 0.f, -500, 300));
		VP_INPUT(M, Specular).Connect(0, Scalar(M, TEXT("Speculaire"), 0.6f, -500, 400));
	}
	else if (Type == TEXT("Eau"))
	{
		// eau : deux normales qui défilent en sens contraires
		UMaterialExpressionTextureCoordinate* UV0 = Node<UMaterialExpressionTextureCoordinate>(M, -1300, 0);
		UMaterialExpressionPanner* P1 = Node<UMaterialExpressionPanner>(M, -1000, -100);
		P1->Coordinate.Connect(0, Mul(M, UV0, 0, nullptr, 0, -1150, -100, 0.5f));
		P1->SpeedX = 0.03f;
		P1->SpeedY = 0.015f;
		UMaterialExpressionPanner* P2 = Node<UMaterialExpressionPanner>(M, -1000, 150);
		P2->Coordinate.Connect(0, Mul(M, UV0, 0, nullptr, 0, -1150, 150, 0.33f));
		P2->SpeedX = -0.02f;
		P2->SpeedY = 0.025f;
		UMaterialExpressionTextureSampleParameter2D* N1 = TexParam(M, TEXT("Normal"), Flat, SAMPLERTYPE_Normal, P1, -750, -100);
		UMaterialExpressionTextureSampleParameter2D* N2 = TexParam(M, TEXT("Normal"), Flat, SAMPLERTYPE_Normal, P2, -750, 150);
		UMaterialExpressionLinearInterpolate* NMix = Node<UMaterialExpressionLinearInterpolate>(M, -450, 0);
		NMix->A.Connect(OutRGB, N1);
		NMix->B.Connect(OutRGB, N2);
		NMix->ConstAlpha = 0.5f;
		VP_INPUT(M, BaseColor).Connect(OutRGB, Vector(M, TEXT("Couleur"), FLinearColor(0.05f, 0.12f, 0.13f), -450, -300));
		VP_INPUT(M, Roughness).Connect(0, Scalar(M, TEXT("Rugosite"), 0.03f, -450, 250));
		VP_INPUT(M, Specular).Connect(0, Scalar(M, TEXT("Speculaire"), 0.7f, -450, 350));
		VP_INPUT(M, Normal).Connect(0, NMix);
	}
	else if (Type == TEXT("Lanterne"))
	{
		UMaterialExpressionVectorParameter* Col = Vector(M, TEXT("Couleur"), FLinearColor(1.f, 0.78f, 0.45f), -600, 0);
		VP_INPUT(M, BaseColor).Connect(OutRGB, Col);
		VP_INPUT(M, Roughness).Connect(0, Scalar(M, TEXT("Rugosite"), 0.2f, -600, 200));
		VP_INPUT(M, EmissiveColor).Connect(0, Mul(M, Col, OutRGB, Scalar(M, TEXT("Emission"), 0.f, -600, 300), 0, -300, 100));
	}
	else if (Type == TEXT("Terrain"))
	{
		// terrain : 8 couches mélangées par la couleur de sommet (couches 0-3) et les canaux UV 1 et 2 (couches 4-7)
		UMaterialExpressionTextureCoordinate* UV0 = Node<UMaterialExpressionTextureCoordinate>(M, -3000, 0);
		UMaterialExpressionTextureCoordinate* UV1 = Node<UMaterialExpressionTextureCoordinate>(M, -3000, 400);
		UV1->CoordinateIndex = 1;
		UMaterialExpressionTextureCoordinate* UV2 = Node<UMaterialExpressionTextureCoordinate>(M, -3000, 600);
		UV2->CoordinateIndex = 2;
		UMaterialExpressionVertexColor* VC = Node<UMaterialExpressionVertexColor>(M, -3000, -400);
		struct FWeight
		{
			UMaterialExpression* Expr;
			int32 Out;
		};
		TArray<FWeight> Weights = {
			{ VC, OutR }, { VC, OutG }, { VC, OutB }, { VC, OutA },
			{ Mask(M, UV1, 0, true, false, false, false, -2800, 350), 0 }, { Mask(M, UV1, 0, false, true, false, false, -2800, 450), 0 },
			{ Mask(M, UV2, 0, true, false, false, false, -2800, 550), 0 }, { Mask(M, UV2, 0, false, true, false, false, -2800, 650), 0 }
		};
		UMaterialExpression* AccC = nullptr;
		UMaterialExpression* AccN = nullptr;
		UMaterialExpression* AccR = nullptr;
		UMaterialExpression* AccO = nullptr;
		for (int32 L = 0; L < 8; ++L)
		{
			const int32 Y = -1600 + L * 450;
			UMaterialExpressionTextureSampleParameter2D* BC = TexParam(M, *FString::Printf(TEXT("BC%d"), L), White, SAMPLERTYPE_Color, UV0, -2400, Y, true);
			UMaterialExpressionTextureSampleParameter2D* NM = TexParam(M, *FString::Printf(TEXT("N%d"), L), Flat, SAMPLERTYPE_Normal, UV0, -2400, Y + 150, true);
			UMaterialExpressionTextureSampleParameter2D* ORM = TexParam(M, *FString::Printf(TEXT("ORM%d"), L), Masks, SAMPLERTYPE_Masks, UV0, -2400, Y + 300, true);
			UMaterialExpressionMultiply* WC = Mul(M, BC, OutRGB, Weights[L].Expr, Weights[L].Out, -2000, Y);
			UMaterialExpressionMultiply* WN = Mul(M, NM, OutRGB, Weights[L].Expr, Weights[L].Out, -2000, Y + 150);
			UMaterialExpressionMultiply* WR = Mul(M, ORM, OutG, Weights[L].Expr, Weights[L].Out, -2000, Y + 250);
			UMaterialExpressionMultiply* WO = Mul(M, ORM, OutR, Weights[L].Expr, Weights[L].Out, -2000, Y + 350);
			AccC = AccC ? static_cast<UMaterialExpression*>(Add(M, AccC, 0, WC, 0, -1700, Y)) : static_cast<UMaterialExpression*>(WC);
			AccN = AccN ? static_cast<UMaterialExpression*>(Add(M, AccN, 0, WN, 0, -1700, Y + 150)) : static_cast<UMaterialExpression*>(WN);
			AccR = AccR ? static_cast<UMaterialExpression*>(Add(M, AccR, 0, WR, 0, -1700, Y + 250)) : static_cast<UMaterialExpression*>(WR);
			AccO = AccO ? static_cast<UMaterialExpression*>(Add(M, AccO, 0, WO, 0, -1700, Y + 350)) : static_cast<UMaterialExpression*>(WO);
		}
		// variation à grande échelle (casse la répétition des textures)
		UMaterialExpressionTextureSampleParameter2D* Macro = TexParam(M, TEXT("Macro"), White, SAMPLERTYPE_Color, Mul(M, UV0, 0, nullptr, 0, -2600, -800, 0.02f), -2400, -800, true);
		UMaterialExpressionLinearInterpolate* MacroF = Node<UMaterialExpressionLinearInterpolate>(M, -1500, -800);
		MacroF->ConstA = 0.8f;
		MacroF->ConstB = 1.12f;
		MacroF->Alpha.Connect(OutR, Macro);
		VP_INPUT(M, BaseColor).Connect(0, Mul(M, AccC, 0, MacroF, 0, -1300, -600));
		VP_INPUT(M, Normal).Connect(0, AccN);
		VP_INPUT(M, Roughness).Connect(0, AccR);
		VP_INPUT(M, AmbientOcclusion).Connect(0, AccO);
		VP_INPUT(M, Specular).Connect(0, Scalar(M, TEXT("Speculaire"), 0.35f, -1300, 400));
	}
	Finish(M);
	M->PostEditChange();
	Masters.Add(Type, M);
	return M;
}

void FVPBuilder::BuildMaterials(FScopedSlowTask& Task)
{
	Task.EnterProgressFrame(2.f, LOCTEXT("Masters", "Matériaux maîtres..."));
	for (const TCHAR* Type : { TEXT("Base"), TEXT("Feuillage"), TEXT("Enseigne"), TEXT("Couleur"), TEXT("Eau"), TEXT("Lanterne"), TEXT("Terrain") })
	{
		BuildMaster(Type);
	}
	const TArray<TSharedPtr<FJsonValue>>& List = Manifest->GetArrayField(TEXT("materials"));
	const float Step = 3.f / FMath::Max(1, List.Num());
	for (const TSharedPtr<FJsonValue>& Value : List)
	{
		const TSharedPtr<FJsonObject> Info = Value->AsObject();
		const FString Name = Info->GetStringField(TEXT("name"));
		Task.EnterProgressFrame(Step, FText::Format(LOCTEXT("Mat", "Matériau {0}"), FText::FromString(Name)));
		UMaterial* Parent = Masters.FindRef(Info->GetStringField(TEXT("master")));
		if (!Parent)
		{
			++Warnings;
			continue;
		}
		UMaterialInstanceConstant* MI = FindOrCreate<UMaterialInstanceConstant>(TEXT("Materials"), TEXT("MI_") + Name);
		MI->PreEditChange(nullptr);
		MI->SetParentEditorOnly(Parent);
		auto SetTex = [&](const TCHAR* Field, const TCHAR* Param)
		{
			FString TexName;
			if (Info->TryGetStringField(Field, TexName))
			{
				if (UTexture2D* Tex = Textures.FindRef(TexName))
				{
					UMaterialEditingLibrary::SetMaterialInstanceTextureParameterValue(MI, FName(Param), Tex);
				}
			}
		};
		SetTex(TEXT("BC"), TEXT("BaseColor"));
		SetTex(TEXT("N"), TEXT("Normal"));
		SetTex(TEXT("ORM"), TEXT("ORM"));
		const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
		if (Info->TryGetArrayField(TEXT("layers"), Layers))
		{
			for (int32 L = 0; L < Layers->Num(); ++L)
			{
				const TSharedPtr<FJsonObject> Layer = (*Layers)[L]->AsObject();
				for (const TCHAR* Kind : { TEXT("BC"), TEXT("N"), TEXT("ORM") })
				{
					if (UTexture2D* Tex = Textures.FindRef(Layer->GetStringField(Kind)))
					{
						UMaterialEditingLibrary::SetMaterialInstanceTextureParameterValue(MI, FName(*FString::Printf(TEXT("%s%d"), Kind, L)), Tex);
					}
				}
			}
			FString MacroName;
			if (Info->TryGetStringField(TEXT("macro"), MacroName))
			{
				if (UTexture2D* Tex = Textures.FindRef(MacroName))
				{
					UMaterialEditingLibrary::SetMaterialInstanceTextureParameterValue(MI, FName(TEXT("Macro")), Tex);
				}
			}
		}
		const TSharedPtr<FJsonObject>* Params = nullptr;
		if (Info->TryGetObjectField(TEXT("params"), Params))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& P : (*Params)->Values)
			{
				if (P.Value->Type == EJson::Array)
				{
					const TArray<TSharedPtr<FJsonValue>>& C = P.Value->AsArray();
					if (C.Num() >= 3)
					{
						const FLinearColor Color((float)C[0]->AsNumber(), (float)C[1]->AsNumber(), (float)C[2]->AsNumber(), C.Num() > 3 ? (float)C[3]->AsNumber() : 1.f);
						UMaterialEditingLibrary::SetMaterialInstanceVectorParameterValue(MI, FName(*P.Key), Color);
					}
				}
				else
				{
					UMaterialEditingLibrary::SetMaterialInstanceScalarParameterValue(MI, FName(*P.Key), (float)P.Value->AsNumber());
				}
			}
		}
		UMaterialEditingLibrary::UpdateMaterialInstance(MI);
		MI->PostEditChange();
		MI->MarkPackageDirty();
		Materials.Add(Name, MI);
	}
}

UMaterialInterface* FVPBuilder::GetMaterial(const FString& Name) const
{
	if (UMaterialInterface* const* Found = Materials.Find(Name))
	{
		return *Found;
	}
	return nullptr;
}

UMaterialInterface* FVPBuilder::GetTinted(const FString& Base, FColor Color)
{
	const FString Key = FString::Printf(TEXT("%s_%02X%02X%02X"), *Base, Color.R, Color.G, Color.B);
	if (UMaterialInterface** Found = Tinted.Find(Key))
	{
		return *Found;
	}
	UMaterialInterface* BaseMaterial = GetMaterial(Base);
	if (!BaseMaterial)
	{
		return nullptr;
	}
	UMaterialInstanceConstant* MI = FindExisting<UMaterialInstanceConstant>(TEXT("Materials/Teintes"), TEXT("MI_") + Key);
	if (!MI || Mode == EMode::Full)
	{
		MI = FindOrCreate<UMaterialInstanceConstant>(TEXT("Materials/Teintes"), TEXT("MI_") + Key);
		MI->PreEditChange(nullptr);
		MI->SetParentEditorOnly(BaseMaterial);
		UMaterialEditingLibrary::SetMaterialInstanceVectorParameterValue(MI, FName(TEXT("Teinte")), FLinearColor::FromSRGBColor(Color));
		UMaterialEditingLibrary::UpdateMaterialInstance(MI);
		MI->PostEditChange();
		MI->MarkPackageDirty();
	}
	Tinted.Add(Key, MI);
	return MI;
}

#undef LOCTEXT_NAMESPACE
