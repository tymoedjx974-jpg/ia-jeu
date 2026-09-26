using UnrealBuildTool;

public class VillageProvenceEditor : ModuleRules
{
	public VillageProvenceEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"UnrealEd",
			"Slate",
			"SlateCore",
			"ToolMenus",
			"AssetTools",
			"AssetRegistry",
			"MaterialEditor",
			"MeshDescription",
			"StaticMeshDescription",
			"ImageWrapper",
			"Json",
			"Projects"
		});
	}
}
