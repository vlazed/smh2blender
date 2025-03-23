import bpy

import json
import os
from mathutils import Vector, Euler, Matrix
from math import floor
from typing import Generator

from .frame import PhysBoneFrames, BoneFrames, PhysBoneTree
from .types import SMHEntityDict, SMHFileDict, SMHEntityFrameDict, ArmatureObject, BoneMap
from .bone import PhysBoneField, BoneField
from .props import SMHMetaData, SMHProperties


class SMHImporter:
    physics_obj_map: BoneMap
    bone_map: BoneMap
    action: bpy.types.Action
    physics_tree: PhysBoneTree
    armature: ArmatureObject
    interpolation: list

    def create_fc(
        self,
        index: float,
        frames: list[int],
        samples: Generator[float, None, None],
        data_path: str,
        group_name: str
    ):
        num_frames = len(frames)
        fc: bpy.types.FCurve = self.action.fcurves.new(
            data_path=data_path, index=index, action_group=group_name)
        fc.keyframe_points.add(num_frames)
        fc.keyframe_points.foreach_set(
            "co", [x for co in zip(frames, samples) for x in co])
        fc.keyframe_points.foreach_set(
            "interpolation", self.interpolation)
        fc.update()

    def __init__(
            self,
            physics_obj_map: BoneMap,
            bone_map: BoneMap,
            armature: ArmatureObject,
            action: bpy.types.Action,
            entity: SMHEntityDict):
        self.physics_obj_map = physics_obj_map
        self.bone_map = bone_map
        self.action = action

        self.armature = armature
        self.physics_tree = PhysBoneTree(armature, physics_obj_map)

        frames = [
            frame["Position"] for frame in entity["Frames"] if len(frame["EntityData"]) > 0
        ]
        num_frames = len(frames)
        self.interpolation = [
            bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value] * num_frames
        action.frame_start = min(frames)
        action.frame_end = max(frames)

    @staticmethod
    def get_pose(
        data: list[list[PhysBoneField | BoneField]], index: int,
        bone: bpy.types.PoseBone, local_condition: bool = False
    ):
        matrices: list[Matrix] = None
        if local_condition:
            matrices = [row[index].local_matrix for row in data]
        else:
            matrices = [row[index].matrix for row in data]

        frames = [row[index].frame for row in data]

        pos = [
            (matrix.translation.x for matrix in matrices),
            (matrix.translation.y for matrix in matrices),
            (matrix.translation.z for matrix in matrices)
        ]

        ang = [
            (matrix.to_quaternion().w for matrix in matrices),
            (matrix.to_quaternion().x for matrix in matrices),
            (matrix.to_quaternion().y for matrix in matrices),
            (matrix.to_quaternion().z for matrix in matrices),
        ] if bone.rotation_mode == 'QUATERNION' else [
            (matrix.to_euler().x for matrix in matrices),
            (matrix.to_euler().y for matrix in matrices),
            (matrix.to_euler().z for matrix in matrices),
        ]

        return pos, ang, frames

    def fcurves_from_data(
        self,
        pos: list[Generator[float, None, None]],
        ang: list[Generator[float, None, None]],
        frames: list[float],
        name: str,
        bone: bpy.types.PoseBone,
        location_condition: bool = True,
        rotation_condition: bool = True
    ):
        if location_condition:
            data_path = bone.path_from_id('location')
            [self.create_fc(
                index=index, samples=samples, data_path=data_path,
                group_name=name, frames=frames) for index, samples in enumerate(pos)]

        if rotation_condition:
            data_path = bone.path_from_id(
                'rotation_quaternion'
                if bone.rotation_mode == 'QUATERNION' else 'rotation_euler'
            )
            [self.create_fc(
                index=index, samples=samples, data_path=data_path,
                group_name=name, frames=frames) for index, samples in enumerate(ang) if samples is not None]

    def import_physics(self, physbone_data: list[list[PhysBoneField]], metadata: SMHMetaData):
        # Stop Motion Helper reports the root physics object location as an offset from the ground (about 38 units)
        # Without this adjustment, the armature will be offset from the ground
        offset = self.physics_tree.get_bone_from_index(
            0).bone.matrix_local.translation
        offset = Vector((offset[0], offset[1], offset[2]))
        [
            [
                physbone.add_pos(-offset)
                for physbone_index, physbone in enumerate(physbone_row)
                if physbone_index == 0
            ]
            for physbone_row in physbone_data
        ]

        for index, phys_name in enumerate(self.physics_obj_map):
            bone = self.armature.pose.bones.get(phys_name)
            if not bone:
                continue

            pos, ang, frames = self.get_pose(
                data=physbone_data,
                index=index,
                bone=bone,
                local_condition=self.physics_tree.get_parent(phys_name) is not None
            )

            if self.physics_tree.get_parent(phys_name) is None:
                bone.bone.use_local_location = False

            self.fcurves_from_data(
                pos,
                ang,
                frames,
                name=phys_name,
                bone=bone,
                location_condition=metadata.import_stretch or self.physics_tree.get_parent(phys_name) is None
            )

    def import_bones(self, bone_data: list[list[BoneField]]):
        for index, bone_name in enumerate(self.bone_map):
            bone = self.armature.pose.bones.get(bone_name)
            if not bone or self.physics_tree.bone_dict.get(bone_name) is not None:
                continue

            pos, ang, frames = self.get_pose(
                data=bone_data,
                index=index,
                bone=bone,
            )

            self.fcurves_from_data(
                pos,
                ang,
                frames,
                name=bone_name,
                bone=bone,
            )


class SMHEntityData():
    data: SMHEntityFrameDict
    armature: ArmatureObject
    position: int

    def __init__(self, position: int, armature: ArmatureObject):
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

    def to_json(self, physbones, bones) -> SMHEntityFrameDict:
        self.bake_physbones(physbones)
        self.bake_bones(bones)

        return self.data


def load_map(map_path: str):
    map = []
    with open(map_path) as f:
        map = f.read().splitlines()

    return map


def has_keyframe(fcurves: bpy.types.ActionFCurves, frame: float):
    for fcurve in fcurves:
        for keyframe in fcurve.keyframe_points:
            if keyframe.co[0] == frame:
                return True

    return False


class SMHEntity():
    data: SMHEntityDict
    armature: ArmatureObject
    metadata: SMHMetaData

    @staticmethod
    def load_physbones(entity: SMHEntityDict, armature: ArmatureObject, metadata: SMHMetaData | None = None):
        return [
            [
                PhysBoneField(
                    armature=armature, data=datum,
                    angle_offset=metadata.angle_offset() if metadata else Euler(),
                    frame=frame["Position"]
                ) for datum in frame["EntityData"]["physbones"].values()
            ]
            for frame in entity["Frames"] if dict(frame["EntityData"]).get("physbones")
        ]

    @staticmethod
    def load_bones(entity: SMHEntityDict, armature):
        return [
            [
                BoneField(
                    armature=armature,
                    data=datum,
                    frame=frame["Position"]
                ) for datum in frame["EntityData"]["bones"].values()
            ]
            for frame in entity["Frames"] if dict(frame["EntityData"]).get("bones")
        ]

    @staticmethod
    def load_entity(data: SMHFileDict, name: str):
        return next((
            entity for entity in data.get("Entities")
            if entity.get("Properties") and entity["Properties"].get("Name", "") == name), None
        )

    def __init__(self, armature: ArmatureObject, properties: SMHProperties, metadata: SMHMetaData):
        self.data = {
            "Frames": [],
            "Model": os.path.basename(properties.model),
            "Properties": properties.to_json(),
        }

        self.armature = armature
        self.metadata = metadata

    def bake_to_smh(self, frame_step: int = 1, check_keyframe: bool = False):
        """Read physics map and bone map, and write SMH animation data from the Blender

        Returns:
            SMHEntityDict: SMH animation data representing the Blender action
        """

        action = self.armature.animation_data.action
        if not action:
            # Action should exist in the prior step. This is just here in case it
            # doesn't (and to silence linting errors)
            return self.data

        physics_obj_map = []
        with open(bpy.path.abspath(self.metadata.physics_obj_path)) as f:
            physics_obj_map = f.read().splitlines()

        bone_map = []
        with open(bpy.path.abspath(self.metadata.bone_path)) as f:
            bone_map = f.read().splitlines()

        frame_range = (floor(action.frame_start), floor(
            action.frame_end + 1), frame_step)

        physbone_frames = PhysBoneFrames(
            self.armature, frame_range).to_json(map=physics_obj_map)

        bone_frames = BoneFrames(
            self.armature, frame_range).to_json(map=bone_map)

        for frame in range(frame_range[0], frame_range[1], frame_range[2]):
            entityData = SMHEntityData(armature=self.armature, position=frame)

            if check_keyframe and not has_keyframe(action.fcurves, frame):
                continue

            self.data["Frames"].append(entityData.to_json(
                physbone_frames[str(frame)], bone_frames[str(frame)]))

        return self.data

    @classmethod
    def bake_from_smh(cls, data: SMHFileDict, metadata: SMHMetaData, filename: str, armature: ArmatureObject):
        """Load SMH animation data into Blender

        Args:
            data (SMHEntityDict): SMH animation data to read
            metadata (SMHMetaData): UI settings
            filename (str): The name of the animation file to load
            armature (ArmatureObject): The selected armature

        Returns:
            success (bool): Whether the operation succeeded
            msg (str): Success or error message
        """

        name: str = metadata.name
        ref_name: str = metadata.ref_name

        ref_physbone_data = None
        with open(bpy.path.abspath(metadata.ref_path)) as f:
            ref_data: SMHFileDict = json.load(f)
            ref_entity = cls.load_entity(
                ref_data, ref_name)
            if not ref_entity:
                return False, f"Failed to load {filename}: reference entity name doesn't match {name}"
            ref_physbone_data = cls.load_physbones(
                armature=armature, entity=ref_entity)

        entity = cls.load_entity(data, name)
        if not entity:
            return False, f"Failed to load {filename}: entity name doesn't match {name}"
        physbone_data = cls.load_physbones(
            armature=armature, entity=entity, metadata=metadata)
        bone_data = cls.load_bones(armature=armature, entity=entity)
        [
            [
                physbone.set_ref_offset(
                    refphysbone=ref_physbone_data[0][physbone_index], is_root=physbone_index == 0)
                for physbone_index, physbone in enumerate(physbone_row)
            ]
            for physbone_row in physbone_data
        ]

        action = bpy.data.actions.new(filename)
        action.use_frame_range = True
        physics_obj_map = load_map(bpy.path.abspath(metadata.physics_obj_path))
        bone_map = load_map(bpy.path.abspath(metadata.bone_path))
        armature.animation_data_create()
        armature.animation_data.action = action

        importer = SMHImporter(physics_obj_map, bone_map, armature, action, entity)

        importer.import_bones(bone_data)
        importer.import_physics(physbone_data, metadata)

        return True, f"Successfully loaded {filename}"


class SMHFile():
    data: SMHFileDict
    check_keyframes: bool
    frame_step: int

    def __init__(self, map: str = "none", check_keyframes: bool = False, frame_step: int = 1):
        self.data = {
            "Map": map,
            "Entities": []
        }
        self.check_keyframes = check_keyframes
        self.frame_step = 1 if check_keyframes else frame_step

    def serialize(self, armature: bpy.types.Armature, metadata: SMHMetaData, properties: SMHProperties) -> str:
        # TODO: Support multiple armatures as other entities
        entity = SMHEntity(
            armature=armature,
            metadata=metadata,
            properties=properties
        )

        # Call their `bake_to_smh` functions and store their strings per entity
        self.data["Entities"].append(
            entity.bake_to_smh(
                frame_step=self.frame_step,
                check_keyframe=self.check_keyframes
            )
        )

        return json.dumps(self.data, indent=4)

    def deserialize(self, file, metadata: SMHMetaData, filepath: str, armature: ArmatureObject):
        data = json.load(file)
        return SMHEntity.bake_from_smh(
            data=data, metadata=metadata, filename=os.path.basename(
                filepath).removesuffix(".txt"), armature=armature)
