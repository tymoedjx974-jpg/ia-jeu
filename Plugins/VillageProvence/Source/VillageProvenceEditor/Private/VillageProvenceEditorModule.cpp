#include "VillageProvenceEditorModule.h"
#include "VPBuilder.h"
#include "ToolMenus.h"
#include "Misc/MessageDialog.h"
#include "Modules/ModuleManager.h"

#define LOCTEXT_NAMESPACE "VillageProvence"

void FVillageProvenceEditorModule::StartupModule()
{
	UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FVillageProvenceEditorModule::RegisterMenus));
}

void FVillageProvenceEditorModule::ShutdownModule()
{
	if (UObjectInitialized())
	{
		UToolMenus::UnRegisterStartupCallback(this);
		UToolMenus::UnregisterOwner(this);
	}
}

void FVillageProvenceEditorModule::RegisterMenus()
{
	FToolMenuOwnerScoped OwnerScoped(this);
	UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Tools");
	if (!Menu)
	{
		return;
	}
	FToolMenuSection& Section = Menu->FindOrAddSection("VillageProvence", LOCTEXT("Section", "Village provençal"));
	Section.AddMenuEntry("VP_BuildAll",
		LOCTEXT("BuildAll", "Construire le village provençal"),
		LOCTEXT("BuildAllTip", "Crée les textures, matériaux et maillages dans /Game/VillageProvence puis place tout le village dans le niveau ouvert (plusieurs minutes)."),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateStatic(&FVillageProvenceEditorModule::BuildAll)));
	Section.AddMenuEntry("VP_BuildActors",
		LOCTEXT("BuildActors", "Replacer le village (sans recréer les assets)"),
		LOCTEXT("BuildActorsTip", "Réutilise les assets déjà créés et replace le village dans le niveau ouvert (par exemple dans un autre niveau)."),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateStatic(&FVillageProvenceEditorModule::BuildActorsOnly)));
	Section.AddMenuEntry("VP_Remove",
		LOCTEXT("Remove", "Retirer le village du niveau"),
		LOCTEXT("RemoveTip", "Supprime du niveau ouvert tous les acteurs créés par le plugin (les assets restent dans le Content Browser)."),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateStatic(&FVillageProvenceEditorModule::RemoveVillage)));
}

void FVillageProvenceEditorModule::BuildAll()
{
	const EAppReturnType::Type Answer = FMessageDialog::Open(EAppMsgType::OkCancel,
		LOCTEXT("Confirm", "Le village va être construit dans le niveau ouvert : 4 x 4 km, environ 900 000 plantes et 2 000 bâtiments.\n\nLa première construction prend plusieurs minutes (textures, matériaux, maillages Nanite), puis Unreal compile les shaders.\n\nContinuer ?"));
	if (Answer != EAppReturnType::Ok)
	{
		return;
	}
	FVPBuilder Builder(FVPBuilder::EMode::Full);
	Builder.Run();
}

void FVillageProvenceEditorModule::BuildActorsOnly()
{
	FVPBuilder Builder(FVPBuilder::EMode::ActorsOnly);
	Builder.Run();
}

void FVillageProvenceEditorModule::RemoveVillage()
{
	FVPBuilder Builder(FVPBuilder::EMode::Remove);
	Builder.Run();
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FVillageProvenceEditorModule, VillageProvenceEditor)
