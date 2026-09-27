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
#include "Materials/MaterialExpressionCollectionParameter.h"
#include "Materials/MaterialExpressionCustom.h"
#include "Materials/MaterialExpressionPreSkinnedPosition.h"
#include "Materials/MaterialExpressionSubtract.h"
#include "Materials/MaterialExpressionTransform.h"
#include "Materials/MaterialExpressionWorldPosition.h"
#include "Materials/MaterialParameterCollection.h"
#include "VPVegetationShared.h"
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

	void SetFloat(UMaterial* M, const TCHAR* Name, float Value)
	{
		if (FFloatProperty* Prop = FindFProperty<FFloatProperty>(UMaterial::StaticClass(), Name))
		{
			Prop->SetPropertyValue_InContainer(M, Value);
		}
	}

	UMaterialExpressionCollectionParameter* CollectionParam(UMaterial* M, UMaterialParameterCollection* Collection, FName Name, int32 X, int32 Y)
	{
		UMaterialExpressionCollectionParameter* P = Node<UMaterialExpressionCollectionParameter>(M, X, Y);
		P->Collection = Collection;
		P->ParameterName = Name;
		P->ParameterId = Collection->GetParameterId(Name);
		return P;
	}

	// Mouvement de la végétation (HLSL) : flexion du tronc et vagues selon le vent, frémissement des feuilles,
	// plantes écartées par les personnages. Entrées en cm ; P = position du sommet, B = pied de l'instance,
	// H = hauteur du sommet au-dessus du pied, A = alpha du sommet (0 à la base, 1 aux extrémités).
	FString WindCode()
	{
		FString Code = TEXT(R"HLSL(
float2 wd = float2(DX, DY);
wd = wd / max(length(wd), 0.001);
float2 wp = float2(-wd.y, wd.x);
float h = max(H, 0.0);
float hm = h * 0.01;
float3 o = float3(0.0, 0.0, 0.0);
// gusts sweeping the landscape downwind
float gb = sin(dot(B.xy, wd) * 0.0008 - T * 1.1) * sin(dot(B.xy, wp) * 0.0005 + T * 0.23);
float f = F * (0.8 + 0.35 * gb);
// trunk bend: identical for bark and leaves of the same tree
float s = Fl * f * 1.2 * pow(hm, 1.5) * (0.75 + 0.25 * sin(T * 4.0 / sqrt(max(hm, 1.0)) + R * 6.2832));
o.xy += wd * s;
o.z -= s * s / max(2.0 * h, 1.0);
// grass and lavender: waves running across the fields
float gp = dot(P.xy, wd) * 0.01;
float wave = 0.55 + 0.45 * sin(gp * 0.45 - T * 2.4 + 0.8 * sin(dot(P.xy, wp) * 0.004));
o.xy += wd * (On * A * f * wave);
// leaf flutter
float ph = dot(P, float3(0.031, 0.027, 0.043)) + R * 6.2832;
float fr = Fr * A * (0.3 + f);
o += fr * float3(sin(T * 6.3 + ph) * 0.6, cos(T * 5.1 + ph * 1.3) * 0.6, sin(T * 7.7 + ph * 0.7) * 0.8);
// characters: xyz = feet, w = radius (integer part) + strength (fraction)
float3 push = float3(0.0, 0.0, 0.0);
)HLSL");
		for (int32 I = 0; I < VPVegetation::NumInteracteurs; ++I)
		{
			Code += FString::Printf(TEXT("{ float4 I = I%d; float r = max(floor(I.w), 1.0); float st = frac(I.w); float2 d = P.xy - I.xy; float dl = length(d); ")
				TEXT("float fo = saturate(1.0 - dl / r); fo = fo * (2.0 - fo); float dz = P.z - I.z; ")
				TEXT("fo *= st * saturate((dz + 80.0) / 40.0) * saturate((260.0 - dz) / 60.0); push.xy += d / max(dl, 1.0) * fo; push.z = max(push.z, fo); }\n"), I);
		}
		Code += TEXT(R"HLSL(
float pl = length(push.xy);
float k = saturate(push.z) * So * saturate(h / 60.0) * (1.0 - saturate((h - 170.0) / 90.0));
o.xy += push.xy / max(pl, 0.001) * k * min(h, 100.0) * 0.85 * saturate(pl * 4.0);
o.z -= k * h * 0.4;
return o;
)HLSL");
		return Code;
	}

	// Décalage de position (World Position Offset) de la végétation. bFoliage = feuillage (tous les effets), sinon écorce (flexion seule).
	UMaterialExpression* WindOffset(UMaterial* M, UMaterialParameterCollection* Collection, UMaterialExpression* Alpha, int32 AlphaOut, bool bFoliage)
	{
		if (!Collection)
		{
			return nullptr;
		}
		const int32 X = -1400, Y = 900;
		UMaterialExpressionWorldPosition* WorldPos = Node<UMaterialExpressionWorldPosition>(M, X - 600, Y);
		UMaterialExpressionPreSkinnedPosition* Local = Node<UMaterialExpressionPreSkinnedPosition>(M, X - 800, Y + 150);
		UMaterialExpressionTransform* LocalToWorld = Node<UMaterialExpressionTransform>(M, X - 600, Y + 150);
		LocalToWorld->Input.Connect(0, Local);
		LocalToWorld->TransformSourceType = TRANSFORMSOURCE_Local;
		LocalToWorld->TransformType = TRANSFORM_World;
		UMaterialExpressionSubtract* Base = Node<UMaterialExpressionSubtract>(M, X - 400, Y + 100);
		Base->A.Connect(0, WorldPos);
		Base->B.Connect(0, LocalToWorld);

		UMaterialExpressionCustom* Custom = Node<UMaterialExpressionCustom>(M, X, Y);
		Custom->Description = TEXT("Vent et passage des personnages");
		Custom->OutputType = CMOT_Float3;
		Custom->Code = WindCode();
		Custom->Inputs.Reset();
		auto In = [Custom](const TCHAR* Name, UMaterialExpression* Expr, int32 Out)
		{
			FCustomInput& Input = Custom->Inputs.AddDefaulted_GetRef();
			Input.InputName = FName(Name);
			Input.Input.Connect(Out, Expr);
		};
		In(TEXT("P"), WorldPos, 0);
		In(TEXT("B"), Base, 0);
		In(TEXT("H"), Mask(M, Local, 0, false, false, true, false, X - 600, Y + 300), 0);
		if (Alpha)
		{
			In(TEXT("A"), Alpha, AlphaOut);
		}
		else
		{
			In(TEXT("A"), Const(M, 0.f, X - 300, Y + 350), 0);
		}
		In(TEXT("R"), Node<UMaterialExpressionPerInstanceRandom>(M, X - 300, Y + 400), 0);
		In(TEXT("T"), Node<UMaterialExpressionTime>(M, X - 300, Y + 450), 0);
		In(TEXT("F"), CollectionParam(M, Collection, VPVegetation::ForceVent(), X - 300, Y + 500), 0);
		In(TEXT("DX"), CollectionParam(M, Collection, VPVegetation::DirectionVentX(), X - 300, Y + 550), 0);
		In(TEXT("DY"), CollectionParam(M, Collection, VPVegetation::DirectionVentY(), X - 300, Y + 600), 0);
		// réglages par matériau (instances) : Souplesse = passage, Ondulation = vagues (cm), Frisson = feuilles (cm), Flexibilite = tronc
		In(TEXT("So"), bFoliage ? static_cast<UMaterialExpression*>(Scalar(M, TEXT("Souplesse"), 0.f, X - 300, Y + 650)) : Const(M, 0.f, X - 300, Y + 650), 0);
		In(TEXT("On"), bFoliage ? static_cast<UMaterialExpression*>(Scalar(M, TEXT("Ondulation"), 0.f, X - 300, Y + 700)) : Const(M, 0.f, X - 300, Y + 700), 0);
		In(TEXT("Fr"), bFoliage ? static_cast<UMaterialExpression*>(Scalar(M, TEXT("Frisson"), 4.f, X - 300, Y + 750)) : Const(M, 0.f, X - 300, Y + 750), 0);
		In(TEXT("Fl"), Scalar(M, TEXT("Flexibilite"), 1.f, X - 300, Y + 800), 0);
		for (int32 I = 0; I < VPVegetation::NumInteracteurs; ++I)
		{
			In(*FString::Printf(TEXT("I%d"), I), CollectionParam(M, Collection, VPVegetation::Interacteur(I), X - 600, Y + 500 + I * 60), 0);
		}
		// déplacement borné : évite que les plantes sortent de leurs limites de visibilité
		SetFloat(M, TEXT("MaxWorldPositionOffsetDisplacement"), 150.f);
		return Custom;
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

	if (Type == TEXT("Base") || Type == TEXT("Ecorce"))
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
		// masque de teinte = canal bleu de l'ORM ; avec des textures Megascans (bleu = déplacement), on le force à 1 ou à 0
		UMaterialExpressionLinearInterpolate* Forced = Node<UMaterialExpressionLinearInterpolate>(M, -850, -250);
		Forced->A.Connect(OutB, ORM);
		Forced->ConstB = 1.f;
		Forced->Alpha.Connect(0, Scalar(M, TEXT("TeinteForcee"), 0.f, -1050, -250));
		UMaterialExpressionLinearInterpolate* Cut = Node<UMaterialExpressionLinearInterpolate>(M, -650, -250);
		Cut->A.Connect(0, Forced);
		Cut->ConstB = 0.f;
		Cut->Alpha.Connect(0, Scalar(M, TEXT("TeinteCoupee"), 0.f, -850, -150));
		TintMix->Alpha.Connect(0, Cut);
		UMaterialExpressionMultiply* Color = Mul(M, BC, OutRGB, TintMix, 0, -250, -400);
		UMaterialExpressionMultiply* Rough = Mul(M, ORM, OutG, Scalar(M, TEXT("EchelleRugosite"), 1.f, -850, 100), 0, -450, 50);
		VP_INPUT(M, BaseColor).Connect(0, Color);
		VP_INPUT(M, Normal).Connect(OutRGB, NM);
		VP_INPUT(M, Roughness).Connect(0, Rough);
		VP_INPUT(M, AmbientOcclusion).Connect(OutR, ORM);
		VP_INPUT(M, Metallic).Connect(0, Scalar(M, TEXT("Metal"), 0.f, -450, 200));
		VP_INPUT(M, Specular).Connect(0, Scalar(M, TEXT("Speculaire"), 0.5f, -450, 300));
		if (Type == TEXT("Ecorce"))
		{
			// écorce des arbres : même flexion au vent que le feuillage, pour que les feuilles restent sur les branches
			if (UMaterialExpression* Wind = WindOffset(M, WindCollection, nullptr, 0, false))
			{
				VP_INPUT(M, WorldPositionOffset).Connect(0, Wind);
			}
		}
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
		// vent (flexion, vagues, frémissement) et passage des personnages, réglés par MPC_VP_Vent
		if (UMaterialExpression* Wind = WindOffset(M, WindCollection, VC, OutA, true))
		{
			VP_INPUT(M, WorldPositionOffset).Connect(0, Wind);
		}
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
		UMaterialExpressionTextureCoordinate* UVBase = Node<UMaterialExpressionTextureCoordinate>(M, -3200, 0);
		UMaterialExpressionMultiply* UV0 = Mul(M, UVBase, 0, Scalar(M, TEXT("Tiling"), 1.f, -3200, 150), 0, -3000, 0);
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
		UMaterialExpressionTextureSampleParameter2D* Macro = TexParam(M, TEXT("Macro"), White, SAMPLERTYPE_Color, Mul(M, UVBase, 0, nullptr, 0, -2600, -800, 0.02f), -2400, -800, true);
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

void FVPBuilder::BuildWindCollection()
{
	// collection de paramètres mise à jour chaque image par UVPVegetationSubsystem (module VillageProvence)
	WindCollection = FindOrCreate<UMaterialParameterCollection>(TEXT("Materials"), TEXT("MPC_VP_Vent"));
	WindCollection->PreEditChange(nullptr);
	auto AddScalar = [this](FName Name, float Default)
	{
		for (const FCollectionScalarParameter& P : WindCollection->ScalarParameters)
		{
			if (P.ParameterName == Name)
			{
				return;
			}
		}
		FCollectionScalarParameter P;
		P.ParameterName = Name;
		P.DefaultValue = Default;
		WindCollection->ScalarParameters.Add(P);
	};
	auto AddVector = [this](FName Name, FLinearColor Default)
	{
		for (const FCollectionVectorParameter& P : WindCollection->VectorParameters)
		{
			if (P.ParameterName == Name)
			{
				return;
			}
		}
		FCollectionVectorParameter P;
		P.ParameterName = Name;
		P.DefaultValue = Default;
		WindCollection->VectorParameters.Add(P);
	};
	// mistral léger de nord-nord-ouest par défaut (il pousse vers le sud-sud-est)
	AddScalar(VPVegetation::ForceVent(), 0.45f);
	AddScalar(VPVegetation::DirectionVentX(), 0.5f);
	AddScalar(VPVegetation::DirectionVentY(), 0.866f);
	for (int32 I = 0; I < VPVegetation::NumInteracteurs; ++I)
	{
		AddVector(VPVegetation::Interacteur(I), VPVegetation::InteracteurVide());
	}
	WindCollection->PostEditChange();
	WindCollection->MarkPackageDirty();
}

void FVPBuilder::BuildMaterials(FScopedSlowTask& Task)
{
	Task.EnterProgressFrame(2.f, LOCTEXT("Masters", "Matériaux maîtres..."));
	BuildWindCollection();
	for (const TCHAR* Type : { TEXT("Base"), TEXT("Ecorce"), TEXT("Feuillage"), TEXT("Enseigne"), TEXT("Couleur"), TEXT("Eau"), TEXT("Lanterne"), TEXT("Terrain") })
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
