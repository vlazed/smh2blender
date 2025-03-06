# SMH 2 Blender <!-- omit from toc -->

Exchange animations between Garry's Mod Stop Motion Helper and Blender

## Table of Contents <!-- omit from toc -->
- [SMH 2 Blender](#smh-2-blender)
  - [Features](#features)
  - [Remarks](#remarks)
- [Tutorials](#tutorials)
  - [Obtaining maps](#obtaining-maps)
  - [Blender to Stop Motion Helper](#blender-to-stop-motion-helper)
  - [Stop Motion Helper to Blender](#stop-motion-helper-to-blender)


## SMH 2 Blender

This Blender addon is a bridge between Garry's Mod (GMod) Stop Motion Helper (SMH) and Blender; it can generate an SMH 4.0 animation file from a Blender action and vice versa, given that we tell Blender how GMod defines the collision model and bone hierarchy of its entities.

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

## Tutorials

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

Keep the number in mind, `N = 79`. Next, run the following commands:
```
clear
lua_run local entity = Entity(N) for i = 0, entity:GetPhysicsObjectCount() - 1 do print(entity:GetBoneName(entity:TranslatePhysBoneToBone(i))) end
```
`N` is the **entity index**. This must be set to that number (e.g. `79`), or else the command will get an error. Make sure to run the `clear` command when making corrections to the `lua_run` command. 

The first command `clear` removes excessive information on the console, and the `lua_run ...` command prints the name of the bone that corresponds to a physics object. The reason for `clear` is to make it easier for the user to copy and paste the names of the bones. This is done by `Ctrl+A` or `Cmd+A`, and then attempting to copy the contents of the console.

Paste the console contents into a text file and remove excessive information (such as the `lua_run` statement). The mapping should look like the one shown in the [beginning of this tutorial](#obtaining-maps). Save the text file somewhere convenient. This text file is the physics object map.

The steps are almost the same for the **bone map**, but the command is different. Remember the entity index `N`, and run the following commands:
```
clear
lua_run local entity = Entity(N) for i = 0, entity:GetBoneCount() - 1 do print(entity:GetBoneName(i)) end
```
This will print more bone names to the console than the previous step. Copy everything from the console, paste into a text file, remove excessive information, and save the text file next to the physics object map. This new text file is the bone map.

These maps allow the animator to proceed to the next steps of exchanging animations between GMod and Blender.

### Blender to Stop Motion Helper
> [!NOTE] 
> This tutorial assumes that you have followed the [Obtaining maps](#obtaining-maps) tutorial.

> [!IMPORTANT] 
> Some knowledge on decompiling models with Crowbar is required.

For animations to properly show undistorted on a model in Stop Motion Helper, the following prerequisites must be met:
- The skeleton (and, in general, its model) in Blender and Stop Motion Helper **must be the same!** 
  - This means same bone orientation, same bone positions local to their parent bone, and (optionally) same bone scale. However, if the models are similar, Ragdoll Puppeteer, which can import Stop Motion Helper animations, can attempt to retarget the animation, given that the model exists in GMod.
- All pose bones in the Blender armature must be in the XYZ Rotation Mode
  - (TODO: make this optional).

To ensure that animations appear the way they should between Blender and SMH, the model must be decompiled with Crowbar and then loaded into Blender (how to find the model is beyond the scope of this tutorial), with the skeleton standing up along the z-axis. 

Once the model is in Blender, the animator can follow their usual animation workflow (using Blender, or other tools that interface with it) to author an animation for model. 

In between now and when the animation is complete, one can attempt to import their animation, either by loading it with Stop Motion Helper or previewing it with Ragdoll Puppeteer, through the following UI.

![blender-to-smh-ui](/media//blender-to-smh-ui.png)

The bone map and physics map are obtained in the prior tutorials. The save path can be set to any location, but the preferred location is in a subdirectory of `garrysmod/data/smh`.

If used with Ragdoll Puppeteer, the animator can choose any map. If the map is also loaded in Blender, it is recommended to use the same map. 

To obtain the model path, one can search for the model in the GMod spawnmenu. Right-click the spawn icon and click "Copy to clipboard". Alternatively, if the model is in the GMod world, one can also run the command `trace` while looking at it, and getting its model path from the trace info.

If a name is not supplied, the model filename (without the path) will be used. For class, this depends on the target model. It is recommended to closely align the class with the target model. For instance, a camera is a `gmod_cameraprop` entity, but it acts like a `Physics` prop.

When these forms are filled, click on the `To SMH` button, and one should expect the following message.

![blender-to-smh-ui](/media//blender-to-smh-save-success.png)

Notice that the name of the file is the name of the action.

### Stop Motion Helper to Blender
(TODO)