import bpy

import json
import os
from mathutils import Vector, Euler, Matrix
from math import floor

from .frame import PhysBoneFrames, BoneFrames, PhysBoneTree
from .types import SMHEntityDict, SMHFileDict, SMHEntityFrameDict, ArmatureObject
from .bone import PhysBoneField, BoneField
from .props import SMHMetaData, SMHProperties


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


class SMHEntity():
    data: SMHEntityDict
    armature: ArmatureObject
    metadata: SMHMetaData

    @staticmethod
    def load_physbones(entity, armature: ArmatureObject, metadata: SMHMetaData | None = None):
        return [
            [
                PhysBoneField(
                    armature=armature, data=datum,
                    angle_offset=metadata.angle_offset() if metadata else Euler()
                ) for datum in frame["EntityData"]["physbones"].values()
            ]
            for frame in entity["Frames"] if frame["EntityData"].get("physbones")
        ]

    @staticmethod
    def load_bones(entity: SMHEntityDict, armature):
        return [
            [
                BoneField(
                    armature=armature,
                    data=datum
                ) for datum in frame["EntityData"]["bones"].values()
            ]
            for frame in entity["Frames"] if frame["EntityData"].get("bones")
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

    def bake_to_smh(self):
        """Read physics map and bone map, and write SMH animation data from the Blender

        Returns:
            SMHEntityDict: SMH animation data representing the Blender action
        """

        action = self.armature.animation_data.action
        if not action:
            # Action should exist in the prior step. This is just here in case it doesn't (and to silence linting errors)
            return self.data

        physics_obj_map = []
        with open(bpy.path.abspath(self.metadata.physics_obj_path)) as f:
            physics_obj_map = f.read().splitlines()

        bone_map = []
        with open(bpy.path.abspath(self.metadata.bone_path)) as f:
            bone_map = f.read().splitlines()

        frame_range = (floor(action.frame_start), floor(
            action.frame_end + 1))

        physbone_frames = PhysBoneFrames(
            self.armature, frame_range).to_json(map=physics_obj_map)

        bone_frames = BoneFrames(
            self.armature, frame_range).to_json(map=bone_map)

        for frame in range(frame_range[0], frame_range[1]):
            entityData = SMHEntityData(armature=self.armature, position=frame)
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
        physics_tree = PhysBoneTree(armature, physics_obj_map)
        bone_map = load_map(bpy.path.abspath(metadata.bone_path))
        armature.animation_data_create()
        armature.animation_data.action = action

        # Stop Motion Helper reports the root physics object location as an offset from the ground (about 38 units)
        # Without this adjustment, the armature will be offset from the ground
        offset = physics_tree.get_bone_from_index(
            0).bone.matrix_local.translation
        offset = Vector((offset[0], offset[2], offset[1]))
        [
            [
                physbone.add_pos(-offset)
                for physbone_index, physbone in enumerate(physbone_row)
                if physbone_index == 0
            ]
            for physbone_row in physbone_data
        ]

        frames = [
            frame["Position"] for frame in entity["Frames"]
        ]
        num_frames = len(frames)
        interpolation = [
            bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value] * num_frames
        action.frame_start = min(frames)
        action.frame_end = max(frames)

        def create_fc(index, samples, data_path, group_name):
            fc: bpy.types.FCurve = action.fcurves.new(
                data_path=data_path, index=index, action_group=group_name)
            fc.keyframe_points.add(num_frames)
            fc.keyframe_points.foreach_set(
                "co", [x for co in zip(frames, samples) for x in co])
            fc.keyframe_points.foreach_set(
                "interpolation", interpolation)
            fc.update()

        for index, bone_name in enumerate(bone_map):
            bone = armature.pose.bones.get(bone_name)
            if not bone or physics_tree.bone_dict.get(bone_name) != None:
                continue

            matrices = [row[index].matrix for row in bone_data]

            pos = [
                (matrix.translation.x for matrix in matrices),
                (matrix.translation.y for matrix in matrices),
                (matrix.translation.z for matrix in matrices)
            ]

            ang = [
                (matrix.to_euler().x for i, matrix in enumerate(matrices)),
                (matrix.to_euler().y for i, matrix in enumerate(matrices)),
                (matrix.to_euler().z for i, matrix in enumerate(matrices))
            ]

            data_path = bone.path_from_id('location')
            [create_fc(
                index=index, samples=samples, data_path=data_path,
                group_name=bone_name) for index, samples in enumerate(pos)]

            data_path = bone.path_from_id('rotation_euler')
            [create_fc(
                index=index, samples=samples, data_path=data_path,
                group_name=bone_name) for index, samples in enumerate(ang)]

        for index, phys_name in enumerate(physics_obj_map):
            bone = armature.pose.bones.get(phys_name)
            if not bone:
                continue

            matrices: list[Matrix] = None
            if physics_tree.get_parent(phys_name):
                matrices = [row[index].local_matrix for row in physbone_data]
            else:
                matrices = [row[index].matrix for row in physbone_data]

            pos = [
                (matrix.translation.x for matrix in matrices),
                (matrix.translation.y for matrix in matrices),
                (matrix.translation.z for matrix in matrices)
            ]

            ang = [
                (matrix.to_euler().x for i, matrix in enumerate(matrices)),
                (matrix.to_euler().y for i, matrix in enumerate(matrices)),
                (matrix.to_euler().z for i, matrix in enumerate(matrices))
            ]

            if metadata.import_stretch or physics_tree.get_parent(phys_name) is None:
                data_path = bone.path_from_id('location')
                [create_fc(
                    index=index, samples=samples, data_path=data_path,
                    group_name=phys_name) for index, samples in enumerate(pos)]

            data_path = bone.path_from_id('rotation_euler')
            [create_fc(
                index=index, samples=samples, data_path=data_path,
                group_name=phys_name) for index, samples in enumerate(ang)]

        return True, f"Successfully loaded {filename}"


class SMHFile():
    data: SMHFileDict

    def __init__(self, map: str = "none"):
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

    def deserialize(self, file, metadata: SMHMetaData, filepath: str, armature: ArmatureObject):
        data = json.load(file)
        return SMHEntity.bake_from_smh(
            data=data, metadata=metadata, filename=os.path.basename(
                filepath).removesuffix(".txt"), armature=armature)
