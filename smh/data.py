import bpy
from bpy.props import *

import json
import os
from typing import TypedDict
from math import floor

from .frame import PhysBoneFrames, BoneFrames


class SMHEntityData():
    class SMHEntityDataDict(TypedDict):
        bones: dict[str, str]
        physbones: dict[str, str]
        EaseOut: dict[str, float]
        EaseIn: dict[str, float]
        Position: int

    data: SMHEntityDataDict
    armature: bpy.types.Armature | bpy.types.Object
    position: int

    def __init__(self, position: int, armature: bpy.types.Armature):
        self.data = {
            "EntityData": {
                "bones": {},
                "physbones": {},
            },
            "EaseIn": {
                "bones": 0.0,
                "physbones": 0.0
            },
            "Position": position,
            "EaseOut": {
                "bones": 0.0,
                "physbones": 0.0
            },
        }

        self.armature = armature
        self.position = position

    def bake_physbones(self, physbones):
        self.data["EntityData"]["physbones"] = physbones

    def bake_bones(self, bones):
        self.data["EntityData"]["bones"] = bones

    def to_json(self, physbones, bones) -> SMHEntityDataDict:
        self.bake_physbones(physbones)
        self.bake_bones(bones)

        return self.data


class SMHProperties(bpy.types.PropertyGroup):
    model: StringProperty(
        name="Model path",
        default="models/kleiner.mdl",
        description="The location of the model with respect to the game's root folder)"
    )
    name: StringProperty(
        name="Name",
        default="kleiner",
        description="A unique identifier of the model, which Stop Motion Helper displays to the user (rather than e.g. kleiner.mdl)"
    )
    cls: EnumProperty(
        name="Class",
        default='prop_ragdoll',
        description="The entity's class name, reflecting what they are in Source Engine",
        items=[
            ('prop_ragdoll', "Ragdoll", ""),
            ('prop_physics', "Prop", ""),
            ('prop_effect', "Effect", ""),
        ])
    map: StringProperty(
        name="Map",
        description="Where the animation will play. It informs the animator that an animation is made for a specific place",
        default="gm_construct"
    )

    def to_json(self) -> str:
        data = {
            "Model": self.model,
            "Name": self.name,
            "Class": self.cls
        }

        return data


class SMHMetaData(bpy.types.PropertyGroup):
    physics_obj_path: StringProperty(
        name="Physics map",
        description="A list of bone names, ordered implicitly by Source Engine. It indicates bones as physical bones, which the Source Engine uses for collision models. Stop Motion Helper distinguishes between physical bones and regular (nonphysical) bones for animation",
        default="",
        subtype='FILE_PATH'
    )
    bone_path: StringProperty(
        name="Bone map",
        description="A list of bone names, ordered implicitly by Source Engine. It indicates the bones for a certain Source Engine model, which may differ from the Blender representation (due to $definebone or a different bone hierarchy)",
        default="",
        subtype='FILE_PATH'
    )
    savepath: StringProperty(
        name="Save path",
        description="Choose where to save animation file",
        default="",
        subtype='DIR_PATH'
    )


class SMHEntity():
    class SMHEntityDict(TypedDict):
        Frames: list[SMHEntityData]
        Properties: str
        Model: str

    data: SMHEntityDict
    armature: bpy.types.Armature | bpy.types.Object
    metadata: SMHMetaData

    def __init__(self, armature: bpy.types.Armature | bpy.types.Object, properties: SMHProperties, metadata: SMHMetaData):
        self.data = {
            "Frames": [],
            "Model": os.path.basename(properties.model),
            "Properties": properties.to_json(),
        }

        self.armature = armature
        self.metadata = metadata

    def construct_frames(self):
        physics_obj_map = []
        with open(bpy.path.abspath(self.metadata.physics_obj_path)) as f:
            physics_obj_map = f.read().splitlines()

        bone_map = []
        with open(bpy.path.abspath(self.metadata.bone_path)) as f:
            bone_map = f.read().splitlines()

        frame_range = (floor(self.armature.animation_data.action.frame_start), floor(
            self.armature.animation_data.action.frame_end + 1))

        physbone_frames = PhysBoneFrames(
            self.armature, frame_range).to_json(physics_obj_map=physics_obj_map)

        bone_frames = BoneFrames(
            self.armature, frame_range).to_json(bone_map=bone_map)

        for frame in range(frame_range[0], frame_range[1]):
            entityData = SMHEntityData(armature=self.armature, position=frame)
            self.data["Frames"].append(entityData.to_json(
                physbone_frames[str(frame)], bone_frames[str(frame)]))

    def bake_to_smh(self):
        # Get armature animdata

        # Iterate over the armature frame range and append to the `Frames` with `EntityData`
        self.construct_frames()

        return self.data

    def bake_from_smh(self, frame_range):
        # Get armature animdata
        data = {}
        # Iterate over the frame range and make keyframes per bone
        return data


class SMHFile():
    class SMHFileData(TypedDict):
        Map: str
        Entities: list[SMHEntity]

    data: SMHFileData

    def __init__(self, map: str):
        self.data = {
            "Map": map,
            "Entities": []
        }

    def serialize(self, armature: bpy.types.Armature, metadata: SMHMetaData, properties: SMHProperties) -> str:
        # TODO: Support multiple armatures as other entities
        entity = SMHEntity(
            armature=armature,
            metadata=metadata,
            properties=properties
        )

        # Call their `bake_to_smh` functions and store their strings per entity
        self.data["Entities"].append(entity.bake_to_smh())

        return json.dumps(self.data, indent=4)

    def deserialize(self):

        pass
