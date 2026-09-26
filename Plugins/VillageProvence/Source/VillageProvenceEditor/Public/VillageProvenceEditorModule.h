#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"

class FVillageProvenceEditorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

private:
	void RegisterMenus();
	static void BuildAll();
	static void BuildActorsOnly();
	static void RemoveVillage();
};
