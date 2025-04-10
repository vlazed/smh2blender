# Tutorials

> [!IMPORTANT]
> For some of these tutorials, knowledge on decompiling models with Crowbar is required. Learn how to decompile models and import them into Blender before proceeding to the following tutorials.

## Requirements

- [Script](https://gist.github.com/vlazed/51a624b3e02ca90b7eaf9ea72c919ceb) to help with obtaining physics maps and bone maps
- Blender 2.8 and up
- Some knowledge with using [Crowbar](https://steamcommunity.com/groups/CrowbarTool) to decompile models

## Configuration Walkthrough

![blender-to-smh-configuration](/media//blender-to-smh-configuration.png)

**Bone map** and **Physics map** refer to the maps obtained in the [Obtaining maps](#obtaining-maps) tutorial. In addition to these is **Reference**, which is a SMH animation file of a model in reference pose. **Ref Name** refers to the name of the entity in the Reference file (usually, the model name). To obtain this, read the [Stop Motion Helper to Blender](#stop-motion-helper-to-blender) tutorial.

## Obtaining maps

> [!IMPORTANT]
> Make sure that the script in the [requirements](#requirements) is installed before proceeding.

Maps are simple `.txt` files which define the order of bones or physics objects of a certain model. Their contents look like this:

```lua
bip_pelvis
bip_spine_0
bip_spine_1
...
bip_hip_R
bip_knee_R
bip_foot_R
```

We have maps so Blender can properly distinguish ragdoll animations. Maps can be obtained from the GMod command console.

To obtain a **physics object map** and **bone map** in GMod, open the spawnmenu (by default, hold `Q` or press `F1`), and navigate to `Utilities > vlazed > SMH Importer/Exporter`. Make sure to look at a ragdoll or prop, and press the corresponding buttons to get the maps from view.

If done correctly, a list of bone names, which correspond to the list shown earlier in this tutorial, will appear. Copy and paste these bone names into a separate text file and name them (for example, `heavy_physmap.txt` and `heavy_bonemap.txt`).

These maps allow the animator to proceed to the next steps of exchanging animations between GMod and Blender.

## Blender to Stop Motion Helper

> [!NOTE]
> This tutorial assumes that you have followed the [Obtaining maps](#obtaining-maps) tutorial.

For animations to properly show undistorted on a model in Stop Motion Helper, the following prerequisites must be met:

- The skeleton (and, in general, its model) in Blender and Stop Motion Helper **must be the same!**
  - This means same bone orientation, same bone positions local to their parent bone, and (optionally) same bone scale. However, if the models are similar, Ragdoll Puppeteer, which can import Stop Motion Helper animations, can attempt to retarget the animation, given that the model exists in GMod.
  - To ensure that animations appear the way they should between Blender and SMH, the model must be decompiled with Crowbar and then loaded into Blender (how to find the model is beyond the scope of this tutorial), with the skeleton standing up along the z-axis.
- All pose bones in the Blender armature must be in the **XYZ or QUATERNION** rotation modes.
- **Manual Frame Range** must be checked, or else the animation will be stuck on the first frame.

Once the model is in Blender, the animator can follow their usual animation workflow (using Blender, or other tools that interface with it) to author an animation for model.

In between now and when the animation is complete, one can attempt to export their animation and load it, either with Stop Motion Helper or Ragdoll Puppeteer, through the following UI.

![blender-to-smh-export](/media//blender-to-smh-export.png)

The save path can be set to any location, but the preferred location is in a subdirectory of `garrysmod/data/smh`.

If used with Ragdoll Puppeteer, the animator can choose any map. If the map is also loaded in Blender, it is recommended to use the same map.

To obtain the model path, one can search for the model in the GMod spawnmenu. Right-click the spawn icon and click "Copy to clipboard". Alternatively, if the model is in the GMod world, one can also run the command `trace` while looking at it, and getting its model path from the trace info.

If a name is not supplied, the model filename (without the path) will be used. For class, this depends on the target model. It is recommended to closely align the class with the target model. For instance, a camera is a `gmod_cameraprop` entity, but it acts like a `Physics` prop.

When these forms are filled, click on `Export SMH File`. There are additional settings to configure the exported file. Hover over each setting to see what they do.

Click `OK`, and one should expect the following message.

![blender-to-smh-ui](/media//blender-to-smh-save-success.png)

Notice that the name of the file is the name of the action.

## Stop Motion Helper to Blender

> [!NOTE]
> This tutorial assumes that you have followed the [Obtaining maps](#obtaining-maps) tutorial.

For animations to properly show undistorted on a model in Blender, the following prerequisites must be met:

- The skeleton (and, in general, its model) in Blender and SMH **must be the same!**
  - This means same bone orientation, same bone positions local to their parent bone, and (optionally) same bone scale.
  - To ensure that animations appear the way they should between Blender and SMH, the model must be decompiled with Crowbar and then loaded into Blender (how to find the model is beyond the scope of this tutorial), with the skeleton standing up along the z-axis.
- All pose bones in the Blender armature must be in the **XYZ or QUATERNION** rotation modes.

Importing animations from SMH is much more restrictive than exporting them. For one, Blender armature animations are defined in the pose space, but SMH exports its animations in the world space, with additional information about the bones in its local to parent space. To ensure animations are imported correctly, we now require a **Reference** animation file, which is a SMH animation file of the model in its reference pose sequence. This reference pose must match the one seen in Blender (a zombie's "stand pose" is not the same as its reference pose).

To generate a reference animation file,

1. Put the model in reference pose (use Stand Poser or Ragdoll Puppeteer, which ever puts it to the correct reference pose),
2. Select the entity with SMH, and record one keyframe in any frame position.
3. Save the animation file, and load it in the Configurations menu.
4. Provide the name of the entity from the reference file (typically the model name, unless the animator gave it a different name).

Load the bone map and physics map of the model. Once the configurations menu is filled, the animator can proceed in importing the animation file, using the following UI.

![blender-to-smh-import](/media//blender-to-smh-import.png)

To import the correct animation, Blender uses the selected armature, the name of the entity in SMH, and the name of the entity in the reference file. SMH always provides a unique name for each entity, even if they have the same model. The animator must input the name of the entity from SMH that they wish to import into Blender; for instance, if the animator named an entity "Bob" in SMH, the name in the Import Settings must be "Bob" in Blender.

The load path is the location of the animation file, which is typically in a `garrysmod/data/smh` subdirectory.

Not all models export from the same 3d modeling software, which explains the existence of certain commands like `$upaxis` or `$definebone`. GMod and Blender also differ in how they define Euler angles. To safe guard and correct against these cases, the addon also provides ways to offset the entity's angle.

Click `Import SMH File`. There are additional settings to configure how the addon will import the file. Hover over each setting to see what they do.

If everything has been set up correctly, the following message should be displayed (corresponding to the specific, loaded animation file). If not, the addon will display an error message that will inform the animator what needs to be corrected.

![blender-to-smh-load-success](/media//blender-to-smh-load-success.png)

Play back the animation to ensure everything is in place. If necessary, export the animation into SMH, and then reimport the animation back into Blender. After these checks, the animator can begin to use Blender's extensive animation tooling to polish up or even author their animations.

## Batch Importing/Exporting

Starting in 0.5.1, this addon can import multiple animations defined in a SMH animation file into multiple armatures and export multiple animations defined from multiple armatures into a single, SMH animation file. To enable batch importing/exporting, select the checkbox.

To ensure a batch import/export is successful, the requirements for importing/exporting animations for a single armature must be met. The animator can satisfy these requirements by following the [SMH to Blender](#stop-motion-helper-to-blender) and [Blender to SMH](#blender-to-stop-motion-helper) tutorials. In short, all of the import/export settings, except for the load/save paths, must be filled.

When importing into multiple armatures, the armature will have an action named in the following manner: `{smh_filename}_{armature.name}`, where `smh_filename` is the name of the animation file for the selected armature, and `armature.name` is the name of the armature (not the name defined in the Import/Export Settings).

Note that the importing and exporting properties (such as the SMH version, frame step, etc.) will act upon all armatures.
