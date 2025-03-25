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
- [Pull Requests](#pull-requests)
- [Acknowledgements](#acknowledgements)


## Description

This Blender addon is a bridge between Garry's Mod (GMod) Stop Motion Helper (SMH) and Blender; it can generate an SMH 4.0 animation file from a Blender action and vice versa, given that we tell Blender how GMod defines the collision model and bone hierarchy of its entities.

### Requirements
- [Script](https://gist.github.com/vlazed/51a624b3e02ca90b7eaf9ea72c919ceb) to help with obtaining physics maps and bone maps
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
- This addon works the best when a majority of the ragdoll's bones have physics objects. More physics objects improve the accuracy of the animation between Blender and SMH. See this [GMod addon](https://steamcommunity.com/sharedfiles/filedetails/?id=3315493382) for an example that adds more physics objects to a group of ragdolls.
  - This is mostly an issue when nonphysical bones (bones without a physics object) have a physical bone as its descendant (such as `bip_spine_3` and `bip_head`)
- Blender's Euler angles are susceptible to gimbal locks. This affects imported SMH animations (most noticeable when animating with IK), and animations re-exported from Blender will not result in the original animation.
  - The animator can preserve the look of their animation as seen in GMod by converting every pose bone to the quaternion rotation mode before re-exporting.
  - In addition, the animator can use `Discontinuity (Euler) Filter` (accessible from Graph Editor) to fix jumps between 180 and -180 degrees. This doesn't affect the animation in SMH, as SMH uses quaternions in the `LerpAngle` method

## Tutorials
To learn how to use this addon, click [here](./docs/TUTORIAL.md).

## Pull Requests
Please format your files to conform to the pep8 guidelines, and ensure you have performed multiple test cases.

## Acknowledgements

- Spike from Peak Inc. for the idea
