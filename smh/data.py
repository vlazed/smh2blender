import bpy

import json
import os


from .types.shared import ArmatureObject, SMHFileType
from .types.file import SMHFileBuilder, SMHFileResult
from .types.entity import SMHEntityBuilder, SMHEntityResult

from .props import SMHMetaData, SMHProperties, SMHExportProperties, SMHImportProperties

from .exporter import SMHExporter as exp
from .importer import SMHImporter as imp


def load_map(map_path: str):
    map = []
    with open(map_path) as f:
        map = f.read().splitlines()

    return map


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

        frame_step = 1 if export_props.keyframes_only else export_props.frame_step
        use_scene_range = export_props.use_scene_range

        action = self.armature.animation_data.action
        if not action:
            # Action should exist in the prior step. This is just here in case it
            # doesn't (and to silence linting errors)
            return self.data

        physics_obj_map = load_map(bpy.path.abspath(self.metadata.physics_obj_path))
        bone_map = load_map(bpy.path.abspath(self.metadata.bone_path))

        exporter = exp(action=action, armature=self.armature, use_scene_range=use_scene_range, frame_step=frame_step)
        exporter.prepare_physics(physics_obj_map=physics_obj_map)
        exporter.prepare_bones(bone_map=bone_map)
        exporter.export(self.data, export_props=export_props)

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
