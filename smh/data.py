import bpy

import json
import os
from math import floor


from .types.shared import ArmatureObject, SMHFileType
from .types.file import SMHFileBuilder, SMHFileResult
from .types.entity import SMHEntityBuilder, SMHEntityResult
from .types.frame import SMHFrameResult, SMHFrameBuilder

from .props import SMHMetaData, SMHProperties, SMHExportProperties, SMHImportProperties

from .exporter import PhysBoneFrames, BoneFrames
from .importer import SMHImporter as imp


class SMHFrameData():
    data: SMHFrameResult
    armature: ArmatureObject
    position: int

    def __init__(self, type: SMHFileType, position: int, armature: ArmatureObject):
        self.data = SMHFrameBuilder(position=position).build(type=type)
        self.type = type
        self.armature = armature
        self.position = position

    def bake_physbones(self, physbones):
        self.data["EntityData"]["physbones"] = physbones
        if self.type == '3':
            self.data['Modifier'] = "physbones"  # type: ignore

    def bake_bones(self, bones):
        self.data["EntityData"]["bones"] = bones
        if self.type == '3':
            self.data['Modifier'] = "bones"  # type: ignore


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
    data: SMHEntityResult
    armature: ArmatureObject
    metadata: SMHMetaData

    def __init__(
            self,
            armature: ArmatureObject,
            properties: SMHProperties,
            metadata: SMHMetaData,
            export_props: SMHExportProperties):

        self.data = SMHEntityBuilder().build(type=export_props.smh_version, properties=properties)
        self.type = export_props.smh_version
        self.armature = armature
        self.metadata = metadata

    def bake_to_smh(self, export_props: SMHExportProperties) -> SMHEntityResult:
        """Read physics map and bone map, and write SMH animation data from the Blender

        Args:
            export_props (SMHExportProperties): Exporting properties

        Returns:
            SMHEntityResult: SMH animation data representing the Blender action
        """

        frame_step = 1 if export_props.keyframes_only else export_props.frame_step,
        check_keyframe = export_props.keyframes_only,
        use_scene_range = export_props.use_scene_range

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

        scene = bpy.context.scene
        frame_range = (
            floor(scene.frame_start if use_scene_range else action.frame_start),
            floor(scene.frame_end + 1 if use_scene_range else action.frame_end + 1),
            frame_step[0]
        )

        physbone_frames = PhysBoneFrames(
            self.armature, frame_range).to_json(map=physics_obj_map)

        bone_frames = BoneFrames(
            self.armature, frame_range).to_json(map=bone_map)

        for frame in range(frame_range[0], frame_range[1], frame_range[2]):
            if check_keyframe and not has_keyframe(action.fcurves, frame):
                continue

            if self.type == '3':
                physbone_frame = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                physbone_frame.bake_physbones(physbones=physbone_frames[str(frame)])

                nonphysbone_frame = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                nonphysbone_frame.bake_bones(bones=bone_frames[str(frame)])

                self.data["Frames"].append(physbone_frame.data)
                self.data["Frames"].append(nonphysbone_frame.data)
            else:
                entityData = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                entityData.bake_physbones(physbones=physbone_frames[str(frame)])
                entityData.bake_bones(bones=bone_frames[str(frame)])

                self.data["Frames"].append(entityData.data)

        return self.data

    @classmethod
    def bake_from_smh(
            cls,
            data: SMHFileResult,
            import_props: SMHImportProperties,
            metadata: SMHMetaData,
            filename: str,
            armature: ArmatureObject):
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
            ref_data: SMHFileResult = json.load(f)
            ref_entity = imp.load_entity(
                ref_data, ref_name, type=import_props.smh_version)
            if not ref_entity:
                return False, f"Failed to load {filename}: reference entity name doesn't match {name}"
            ref_physbone_data = imp.load_physbones(
                armature=armature, entity=ref_entity)

        entity = imp.load_entity(data, name, type=import_props.smh_version)

        if not entity:
            return False, f"Failed to load {filename}: entity name doesn't match {name}"
        physbone_data = imp.load_physbones(
            armature=armature, entity=entity, metadata=metadata)
        bone_data = imp.load_bones(armature=armature, entity=entity)
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

        importer = imp(physics_obj_map, bone_map, armature, action, entity)
        importer.import_bones(bone_data)
        importer.import_physics(physbone_data, metadata)

        return True, f"Successfully loaded {filename}"


class SMHFile():
    def serialize(
            self,
            export_props: SMHExportProperties,
            armature: ArmatureObject,
            metadata: SMHMetaData,
            properties: SMHProperties) -> str:
        data = SMHFileBuilder(properties.map).build(type=export_props.smh_version)

        # TODO: Support multiple armatures as other entities
        entity = SMHEntity(
            armature=armature,
            metadata=metadata,
            properties=properties,
            export_props=export_props
        )

        # Call their `bake_to_smh` functions and store their strings per entity
        data["Entities"].append(
            entity.bake_to_smh(
                export_props=export_props
            )
        )

        return json.dumps(data, indent=4)

    def deserialize(
            self,
            file,
            import_props: SMHImportProperties,
            metadata: SMHMetaData,
            filepath: str,
            armature: ArmatureObject):
        data = json.load(file)
        return SMHEntity.bake_from_smh(
            data=data,
            metadata=metadata,
            filename=os.path.basename(filepath).removesuffix(".txt"),
            armature=armature,
            import_props=import_props
        )
