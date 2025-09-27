import bpy

import json
import os


from .types.shared import ArmatureObject, CameraObject
from .types.file import SMHFileBuilder, SMHFileResult
from .types.entity import SMHEntityBuilder, SMHEntityResult

from .props import SMHMetaData, SMHProperties, SMHExportProperties, SMHImportProperties

from .exporter import SMHExporter as exp
from .importer import SMHImporter as imp

camera_map = ['static_prop']


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

    def bake_from_armature(self, frame_step: int, use_scene_range: bool,
                           export_props: SMHExportProperties) -> SMHEntityResult:
        action = self.armature.animation_data.action
        if not action:
            # Action should exist in the prior step. This is just here in case it
            # doesn't (and to silence linting errors)
            return self.data

        physics_obj_map = load_map(bpy.path.abspath(self.metadata.physics_obj_path))
        bone_map = load_map(bpy.path.abspath(self.metadata.bone_path))
        flex_map = None
        if self.metadata.export_shapekeys_to_flex:
            flex_map = load_map(bpy.path.abspath(self.metadata.flex_path))
        elif self.metadata.shapekey_object:
            shapekey_object: bpy.types.Mesh = self.metadata.shapekey_object
            flex_map = [shape_key.name for shape_key in shapekey_object.shape_keys.key_blocks]

        exporter = exp(action=action, armature=self.armature, use_scene_range=use_scene_range, frame_step=frame_step)
        exporter.prepare_physics(physics_obj_map=physics_obj_map)
        exporter.prepare_bones(
            bone_map=bone_map,
            physics_obj_map=physics_obj_map,
            angle_offset=self.metadata.export_angle_offset(),
            pos_offset=self.metadata.export_pos_offset())
        exporter.prepare_modifiers()
        if self.metadata.export_shapekeys_to_flex and self.metadata.shapekey_object:
            shapekey_object: bpy.types.Mesh = self.metadata.shapekey_object
            if shapekey_object.shape_keys.animation_data.action and shapekey_object.shape_keys.animation_data.action.fcurves:
                exporter.prepare_flexes(self.metadata.shapekey_object, flex_map)
        exporter.export(self.data, export_props=export_props)

        return self.data

    def bake_from_camera(self, frame_step: int, use_scene_range: bool,
                         export_props: SMHExportProperties) -> SMHEntityResult:
        action = self.armature.animation_data.action
        if not action:
            # Action should exist in the prior step. This is just here in case it
            # doesn't (and to silence linting errors)
            return self.data

        physics_obj_map = camera_map

        exporter = exp(action=action, armature=self.armature, use_scene_range=use_scene_range, frame_step=frame_step)
        exporter.prepare_camera(physics_obj_map=physics_obj_map)
        exporter.prepare_modifiers()
        exporter.export(self.data, export_props=export_props)

        return self.data

    def bake_to_smh(self, export_props: SMHExportProperties) -> SMHEntityResult:
        """Read physics map and bone map, and write SMH animation data from the Blender

        Args:
            export_props (SMHExportProperties): Exporting properties

        Returns:
            SMHEntityResult: SMH animation data representing the Blender action
        """
        frame_step = 1 if export_props.keyframes_only else export_props.frame_step
        use_scene_range = export_props.use_scene_range

        if self.armature.type == 'ARMATURE':
            return self.bake_from_armature(frame_step, use_scene_range, export_props)
        elif self.armature.type == 'CAMERA':
            return self.bake_from_camera(frame_step, use_scene_range, export_props)

    @classmethod
    def bake_to_armature(cls,
                         data: SMHFileResult,
                         import_props: SMHImportProperties,
                         metadata: SMHMetaData,
                         filename: str,
                         armature: ArmatureObject):
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
                armature=armature, entity=ref_entity, metadata=metadata, is_ref=True
            )

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
        flex_data = None
        modifier_data = imp.load_modifiers(entity=entity, can_import_flex=metadata.import_flex_to_shapekeys)
        if metadata.import_flex_to_shapekeys and metadata.shapekey_object:
            flex_data = imp.load_flex(entity, mesh=metadata.shapekey_object)

        action = bpy.data.actions.new(f"{filename}_{armature.name}" if import_props.batch else filename)
        action.use_frame_range = True
        physics_obj_map = load_map(bpy.path.abspath(metadata.physics_obj_path))
        bone_map = load_map(bpy.path.abspath(metadata.bone_path))
        flex_map = None
        if metadata.import_flex_to_shapekeys:
            flex_map = load_map(bpy.path.abspath(metadata.flex_path))
        elif metadata.shapekey_object:
            shapekey_object: bpy.types.Mesh = metadata.shapekey_object
            flex_map = [shape_key.name for shape_key in shapekey_object.shape_keys.key_blocks]

        if metadata.shapekey_object:
            shapekey_object: bpy.types.Mesh = metadata.shapekey_object
            shapekey_object.shape_keys.animation_data_create()
            shapekey_object.shape_keys.animation_data.action = action

        armature.animation_data_create()
        armature.animation_data.action = action

        importer = imp(
            physics_obj_map=physics_obj_map,
            bone_map=bone_map,
            armature=armature,
            action=action,
            entity=entity,
            flex_map=flex_map)
        importer.import_bones(bone_data)
        importer.import_physics(physbone_data, metadata)
        if flex_data:
            importer.import_flex(flex_data, metadata)
        importer.import_modifiers(modifier_data, metadata=metadata)

        return True, f"Successfully loaded {filename}"

    @classmethod
    def bake_to_camera(cls,
                       data: SMHFileResult,
                       import_props: SMHImportProperties,
                       metadata: SMHMetaData,
                       filename: str,
                       armature: ArmatureObject):

        name: str = metadata.name
        entity = imp.load_entity(data, name, type=import_props.smh_version)

        if not entity:
            return False, f"Failed to load {filename}: entity name doesn't match {name}"
        physbone_data = imp.load_camera(
            armature=armature, entity=entity)
        modifier_data = imp.load_modifiers(entity=entity, can_import_flex=metadata.import_flex_to_shapekeys)

        action = bpy.data.actions.new(f"{filename}_{armature.name}" if import_props.batch else filename)
        action.use_frame_range = True
        physics_obj_map, bone_map = camera_map, camera_map
        flex_map = None

        armature.animation_data_create()
        armature.animation_data.action = action

        importer = imp(
            physics_obj_map=physics_obj_map,
            bone_map=bone_map,
            armature=armature,
            action=action,
            entity=entity,
            flex_map=flex_map)
        importer.import_modifiers(modifier_data, metadata=metadata)
        importer.import_camera(physbone_data, modifier_data)

        return True, f"Successfully loaded {filename}"

    @classmethod
    def bake_from_smh(
            cls,
            data: SMHFileResult,
            import_props: SMHImportProperties,
            metadata: SMHMetaData,
            filename: str,
            object: ArmatureObject | CameraObject):
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

        if object.type == 'ARMATURE':
            return cls.bake_to_armature(data, import_props, metadata, filename, object)
        elif object.type == 'CAMERA':
            return cls.bake_to_camera(data, import_props, metadata, filename, object)


class SMHFile():
    @classmethod
    def serialize(
            cls,
            export_props: SMHExportProperties,
            armatures: list[ArmatureObject],
            properties: SMHProperties) -> str:
        data = SMHFileBuilder(properties.map).build(type=export_props.smh_version)

        # TODO: Support multiple armatures as other entities
        for armature in armatures:
            props: SMHProperties = armature.smh_properties
            metadata: SMHMetaData = armature.smh_metadata
            entity = SMHEntity(
                armature=armature,
                metadata=metadata,
                properties=props,
                export_props=export_props
            )

            # Call their `bake_to_smh` functions and store their strings per entity
            data["Entities"].append(
                entity.bake_to_smh(
                    export_props=export_props
                )
            )

        return json.dumps(data, indent=4)

    @classmethod
    def deserialize(
            cls,
            file,
            import_props: SMHImportProperties,
            metadata: SMHMetaData,
            filepath: str,
            armature: ArmatureObject | CameraObject):
        data = json.load(file)
        return SMHEntity.bake_from_smh(
            data=data,
            metadata=metadata,
            filename=os.path.basename(filepath).removesuffix(".txt"),
            object=armature,
            import_props=import_props
        )
