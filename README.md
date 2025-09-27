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

- **Animation translations between SMH and Blender:** the animator can work with Blender and its (extensible) animation libraries and export their animations from Blender into GMod. Conversely, the SMH animator can bring their work over to Blender for polishing or other work.
- **SMH Modifiers as custom, animatable properties:** the user can change how SMH modifiers propagate over time (e.g. using Bezier splines or f-curve modifiers).
  - For live feedback, these custom SMH Modifier properties can drive shapekey or camera values, or vice versa!
- **Batch importing/exporting capabilities:**
  - Importing: The selected armature's animation file will be used to import its animations to any armature whose name in the import settings matches the name defined in SMH.
  - Exporting: The actions of all armatures in the scene will be collected into an SMH animation file, using the selected armature's action name as the SMH animation file name.

### Remarks

1. *Bone mappings* are required because for a model with a similar skeletal structure, not all bones have a surjective mapping.
   - Some bones in Blender do not exist in Source Engine, or vice versa. This is due to the modeller's intent to allow certain bones via the `$definebone` `.qc` command. I intend that animators use this addon for animations in Garry's Mod (with some compatibility for workflows involving SMH animations into Blender); hence, for bone structures and collision models, the Source Engine (GMod) model acts as the source of truth.

2. Similarly, *collision model (or physics object) mappings* are required because in Stop Motion Helper, animations are performed on ragdolls.
   - GMod distinguishes collision (physical) bones (e.g. head, arms, legs) and regular (nonphysical) bones (fingers, toes, helmets) for ragdolls. Blender lacks this knowledge since it treats all (pose) bones in an armature the same; thus, we must supply that information to allow Blender to distinguish between motions with physical bones and motions with nonphysical bones.

3. When importing into Blender, the addon requires a **reference file**, which is an SMH animation file of the model in a reference pose (A-Pose or T-Pose).
   - SMH reports the pose of a physics bone by the position and angles of the physics object corresponding to this bone. Blender cannot distinguish between the position of bones and the position of a physics object (which is the geometric center of the physics object). The reference file exists to correct this.
   - Blender reports the pose of its bones in a similar way to how Source Engine reports the pose of its bones (see ManipulateBoneAngles or ManipulateBonePosition on GMod wiki). To make this distinction, the reference file is used to determine the offset that the animated bone has from the bone's reference pose.

### Issues

If you have found a bug, or you have a suggestion to improve this tool, please report it in the [issue tracker](https://github.com/vlazed/smh2blender/issues). This is the best way for me to act on them.

## Gotchas

- This addon works the best when a majority of the ragdoll's bones have physics objects. More physics objects improve the accuracy of the animation between Blender and SMH. See this [GMod addon](https://steamcommunity.com/sharedfiles/filedetails/?id=3315493382) for an example that adds more physics objects to a group of ragdolls.
  - This is mostly an issue when nonphysical bones (bones without a physics object) have a physical bone as its descendant (such as `bip_spine_3` and `bip_head`)
- Blender's Euler angles are susceptible to gimbal locks. This affects imported SMH animations (most noticeable when animating with IK), and animations re-exported from Blender will not result in the original animation.
  - The animator can preserve the look of their animation as seen in GMod by converting every pose bone to the quaternion rotation mode before re-exporting.
  - In addition, the animator can use `Discontinuity (Euler) Filter` (accessible from Graph Editor) to fix jumps between 180 and -180 degrees. This doesn't affect the animation in SMH, as SMH uses quaternions in the `LerpAngle` method

## Tutorials

To learn how to use this addon, [click me](./docs/TUTORIAL.md).

## Pull Requests

Please format your files to conform to the pep8 guidelines, and ensure you have performed multiple test cases.

## Acknowledgements

- Spike from [Peak Inc](https://steamcommunity.com/groups/peakincompetence). for the idea
- [Paper](https://steamcommunity.com/id/PforPaper) for being Mr. L from Paper Mario (addon tester)
