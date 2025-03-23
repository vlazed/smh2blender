# SMH Importer and Exporter <!-- omit from toc -->

Exchange animations between Garry's Mod Stop Motion Helper and Blender

## Table of Contents <!-- omit from toc -->
- [Description](#description)
  - [Requirements](#requirements)
  - [Features](#features)
  - [Remarks](#remarks)
  - [Issues](#issues)
- [Gotchas](#gotchas)
- [Tutorials](#tutorials)
  - [Configuration Walkthrough](#configuration-walkthrough)
  - [Obtaining maps](#obtaining-maps)
  - [Blender to Stop Motion Helper](#blender-to-stop-motion-helper)
  - [Stop Motion Helper to Blender](#stop-motion-helper-to-blender)
- [Pull Requests](#pull-requests)
- [Acknowledgements](#acknowledgements)


## Description

This Blender addon is a bridge between Garry's Mod (GMod) Stop Motion Helper (SMH) and Blender; it can generate an SMH 4.0 animation file from a Blender action and vice versa, given that we tell Blender how GMod defines the collision model and bone hierarchy of its entities.

### Requirements
- Blender 2.8 and up
- Some knowledge with using [Crowbar](https://steamcommunity.com/groups/CrowbarTool) to decompile models

### Features
- Animation translations between SMH and Blender. This allows the animator to work with Blender and its (extensible) animation libraries, which the user can import their animations from Blender into Garry's Mod. Conversely, the user can also animate in Stop Motion Helper and bring their work over to Blender for polishing or other work.
- (TODO) Support for multiple entities,
  - SMH to Blender: The addon will search for armatures with the same name and correspond with an SMH animation file, which will attempt to retarget its animations using a bone and collision model mapping.
  - Blender to SMH: The addon will collect all armatures and assign a name, a model path, and a bone and collision model mapping, and it will attempt to reconstruct the animation in an SMH animation file 

### Remarks

1. *Bone mappings* are required because for a model with a similar skeletal structure, not all bones have a surjective mapping. 
   - Some bones in Blender do not exist in Source Engine, or vice versa. This is due to the modeller's intent to allow certain bones via the `$definebone` `.qc` command. I intend that animators use this addon for animations in Garry's Mod (with some compatibility for workflows involving SMH animations into Blender); hence, the Source Engine (GMod) model acts as the source of truth for bone structures and collision models.

2. Similarly, *collision model (or physics object) mappings* are required because in Stop Motion Helper, animations are performed on ragdolls. 
   - GMod distinguishes collision (physical) bones (e.g. head, arms, legs) and regular (nonphysical) bones (fingers, toes, helmets) for ragdolls. Blender lacks this knowledge since it treats all (pose) bones in an armature the same; thus, we must supply that information to allow Blender to distinguish between motions with physical bones and motions with nonphysical bones.

3. Because this addon strictly works with a Blender armature, using the collision model and bone mappings to inform the translation, an SMH animation translated into Blender will distort the Blender armature, and a Blender animation translated into SMH will distort the ragdoll (seen if the ragdoll has stretching applied through the Ragdoll Stretch tool). 
   - The distortion appears as a translation offset in the position of the physics objects on the ragdoll in GMod, or a translation offset in the position of the bones on the armature in Blender. Without ragdoll stretch, these effects are not noticeable on the GMod ragdoll at first. 
   - This happens because SMH uses the position of a ragdoll's physics object to save and load physical bone data, instead of the bone position corresponding to the physics object. There is a difference between the position of the physics object (which may be the geometric center of the physics object) and the position of the bone that the physics object corresponds to, and this results in a distortion in the armature and in the ragdoll. **It is recommended to not make modifications to the Blender armature if translating the animation back into SMH**; it is fine if the animation is intended as a new sequence for the model.

### Issues
If you have found a bug, or you have a suggestion to improve this tool, please report it in the [issue tracker](https://github.com/vlazed/smh2blender/issues). This is the best way for me to act on them.

## Gotchas
- Starting from Blender 4.4, actions are slotted. This can be confusing when importing SMH animations, compared to earlier versions of Blender. Make sure to select `Legacy Slot` to see the SMH animation.

## Tutorials
> [!IMPORTANT] 
> For some of these tutorials, knowledge on decompiling models with Crowbar is required. Learn how to decompile models and import them into Blender before proceeding to the following tutorials.

### Configuration Walkthrough
![blender-to-smh-configuration](/media//blender-to-smh-configuration.png)

**Bone map** and **Physics map** refer to the maps obtained in the [Obtaining maps](#obtaining-maps) tutorial. In addition to these is **Reference**, which is a SMH animation file of a model in reference pose. **Ref Name** refers to the name of the entity in the Reference file (usually, the model name). To obtain this, read the [Stop Motion Helper to Blender](#stop-motion-helper-to-blender) tutorial.

### Obtaining maps
Maps are simple `.txt` files which define the order of bones or physics objects of a certain model. They look like this:
```
bip_pelvis
bip_spine_0
bip_spine_1
...
bip_hip_R
bip_knee_R
bip_foot_R
```
We have maps so Blender can properly distinguish ragdoll animations. Maps can be obtained from the GMod command console.

To obtain a **physics object map**, look at the ragdoll of interest, open the command console, and run
```
trace
```
This runs a ray that starts at the player's eyes and ends at where the player is looking. This will produce some trace information in the console. Find the following information:
```
...
Model: models/player/soldier.mdl
Entity [79][prop_ragdoll]
```
The number is important: `79` is the **entity index**, which corresponds to a `prop_ragdoll`. The `Model` is also important. In the sane case, if a player is looking at a TF2 Soldier, its model path should correspond to `models/player/soldier.mdl`, or similar.

Keep the number in mind, `N = 79`. Next, run `clear` and the following command:
```
lua_run local entity = Entity(N) for i = 0, entity:GetPhysicsObjectCount() - 1 do print(entity:GetBoneName(entity:TranslatePhysBoneToBone(i))) end
```
`N` is the **entity index**. This must be set to that number (e.g. `79`), or else the command will get an error. Make sure to run the `clear` command when making corrections to the `lua_run` command. 

The first command `clear` removes excessive information on the console, and the `lua_run ...` command prints the name of the bone that corresponds to a physics object. The reason for `clear` is to make it easier for the user to copy and paste the names of the bones. This is done by `Ctrl+A` or `Cmd+A`, and then attempting to copy the contents of the console.

Paste the console contents into a text file and remove excessive information (such as the `lua_run` statement). The mapping should look like the one shown in the [beginning of this tutorial](#obtaining-maps). Save the text file somewhere convenient. This text file is the physics object map.

The steps are almost the same for the **bone map**, but the command is different. Remember the entity index `N`, run `clear`, and then the following command:
```
lua_run local entity = Entity(N) for i = 0, entity:GetBoneCount() - 1 do print(entity:GetBoneName(i)) end
```
This will print more bone names to the console than the previous step. Copy everything from the console, paste into a text file, remove excessive information, and save the text file next to the physics object map. This new text file is the bone map.

These maps allow the animator to proceed to the next steps of exchanging animations between GMod and Blender.

### Blender to Stop Motion Helper
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

When these forms are filled, click on the `Export SMH File` button, and one should expect the following message.

![blender-to-smh-ui](/media//blender-to-smh-save-success.png)

Notice that the name of the file is the name of the action.

### Stop Motion Helper to Blender
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
4. Provide the name of the entity from the reference file (typically the model name, unless the user gave it a different name).

Load the bone map and physics map of the model. Once the configurations menu is filled, the user can proceed in importing the animation file, using the following UI.

![blender-to-smh-import](/media//blender-to-smh-import.png)

To import the correct animation, Blender uses the selected armature, the name of the entity in SMH, and the name of the entity in the reference file. SMH always provides a unique name for each entity, even if they have the same model. The user must input the name of the entity from SMH that they wish to import into Blender; for instance, if the user named an entity "Bob" in SMH, the name in the Import Settings must be "Bob" in Blender.

The load path is the location of the animation file, which is typically in a `garrysmod/data/smh` subdirectory.

Not all models export from the same 3d modeling software, which explains the existence of certain commands like `$upaxis` or `$definebone`. GMod and Blender also differ in how they define Euler angles. To safe guard and correct against these cases, the addon also provides ways to offset the entity's angle.

Click the `Import SMH File`. If everything has been set up correctly, the following message should be displayed (corresponding to the specific, loaded animation file). If not, the addon will display an error message that will inform the user what needs to be corrected.

![blender-to-smh-load-success](/media//blender-to-smh-load-success.png)

Play back the animation to ensure everything is in place. If necessary, export the animation into SMH, and then reimport the animation back into Blender. After these checks, the user can begin to use Blender's extensive animation tooling to polish up or even author their animations.

## Pull Requests
Please format your files to conform to the pep8 guidelines, and ensure you have performed multiple test cases.

## Acknowledgements

- Spike from Peak Inc. for the idea
