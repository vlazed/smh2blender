# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
from bpy.props import PointerProperty
from bl_operators.presets import AddPresetBase
from bl_ui.utils import PresetPanel

from .smh.props import SMHProperties, SMHMetaData, SMHExportProperties, SMHImportProperties
from .smh.data import SMHFile
from .smh.modifiers import register_modifiers, unregister_modifiers
from .smh.types.shared import ArmatureObject, CameraObject

import time

bl_info = {
    "name": "SMH Importer/Exporter",
    "author": "vlazed",
    "description": "Exchange animations between Blender and Garry's Mod",
    "blender": (2, 80, 0),
    "version": (0, 8, 0),
    "location": "",
    "warning": "",
    "category": "Animation",
}

acceptable_types = set(['ARMATURE', 'CAMERA'])


def show_message(message="", title="Message Box", icon='INFO'):
    # https://blender.stackexchange.com/questions/109711/how-to-popup-simple-message-box-from-python-console

    print(message)

    def draw(self: bpy.types.Panel, context: bpy.types.Context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def check_metadata_for_maps(metadata: SMHMetaData, armature: ArmatureObject):
    passed = True
    msg = None
    if not metadata.physics_obj_path:
        passed = False
        msg = (
            f"{armature.name}: Empty physics map. Please supply a physics map and try again", "Error", 'ERROR')

    if not metadata.bone_path:
        passed = False
        msg = (f"{armature.name}: Empty bone map. Please supply a bone map and try again",
               "Error", 'ERROR')

    return passed, msg


def check_smh_file(path: str, armature: ArmatureObject):
    passed = True
    msg = None
    if not path:
        passed = False

    if passed and not path.endswith(".txt"):
        passed = False
        msg = (
            f"{armature.name}: SMH animation files must end with \".txt\".", "Error", 'ERROR')

    return passed, msg


class SMH_OT_BlenderToSMH(bpy.types.Operator):
    """Translate Blender to SMH"""
    bl_idname = "smh.blender2smh"
    bl_label = "Export SMH File"
    bl_description = "Translate Blender keyframes into a text file that SMH can read, from the selected armature"

    def draw(self, context):
        export_props: SMHExportProperties = context.scene.smh_export_props
        layout = self.layout

        key = layout.row()
        key.prop(export_props, "use_scene_range")
        key.prop(export_props, "keyframes_only")
        frame = layout.row()
        frame.enabled = not export_props.keyframes_only
        frame.prop(export_props, "frame_step")
        key = layout.row()
        key.prop(export_props, "batch")
        key.prop(export_props, "visual_keying")
        col = layout.column()
        col.prop(export_props, "smh_version")

        # # This won't show up in older versions of Blender. Nonetheless, this is certainly cosmetic
        # row.template_popup_confirm("smh.blender2smh", text="Export", cancel_text="Cancel", cancel_default=True)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        # disable the operator if no Armature object is selected
        return context.active_object and context.active_object.type in acceptable_types

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def check_armature(
            self,
            armature: ArmatureObject,
            metadata: SMHMetaData,
            properties: SMHProperties,
            selected_metadata: SMHMetaData):

        if armature.type == 'ARMATURE':
            result, msg = check_metadata_for_maps(metadata=metadata, armature=armature)
            if not result and msg:
                show_message(*msg)
                return False

        if not properties.name:
            show_message(
                f"{armature.name}: Empty model name. Please give the model a descriptive name and try again",
                "Error",
                'ERROR')
            return False

        if not selected_metadata.savepath:
            show_message(
                f"{armature.name}: Empty save path. Please supply a location to save the animation file and try again",
                "Error",
                'ERROR')
            return False

        return True

    def execute(self, context):
        # We polled for an armature, so our active object should be one
        selected_armature: ArmatureObject = context.active_object

        scene = context.scene
        selected_metadata: SMHMetaData = selected_armature.smh_metadata
        selected_properties: SMHProperties = selected_armature.smh_properties
        export_props: SMHExportProperties = scene.smh_export_props

        action = selected_armature.animation_data.action
        if not action:
            show_message(
                "No animation found. Make sure that the selected armature has an `Animation`", "Error", 'ERROR')
            return {'CANCELLED'}

        armatures: list[ArmatureObject] = []
        if export_props.batch:
            for armature in bpy.data.objects:
                if armature.type in acceptable_types:
                    metadata: SMHMetaData = armature.smh_metadata
                    properties: SMHProperties = armature.smh_properties
                    if self.check_armature(armature, metadata, properties, selected_metadata):
                        armatures.append(armature)
        else:
            if self.check_armature(
                    selected_armature,
                    selected_metadata,
                    selected_properties,
                    selected_metadata=selected_metadata
            ):
                armatures.append(selected_armature)

        if not armatures:
            show_message(
                "Selected armature or armatures in scene did not pass. Check the message boxes to figure out the issue",
                "Error",
                'ERROR')
            return {'CANCELLED'}

        start_time = time.perf_counter()
        filename = action.name + ".txt"

        contents = SMHFile().serialize(armatures=armatures, properties=selected_properties, export_props=export_props)
        try:
            with open(bpy.path.abspath(selected_metadata.savepath + filename), "w+") as f:
                f.write(contents)
        except Exception as e:
            show_message(
                f"SMH Exporter: An error as occurred during the process: {e}", "Error", 'ERROR')
            return {'CANCELLED'}
        end_time = time.perf_counter()
        show_message(
            f"SMH Exporter: Successfully wrote save file to {selected_metadata.savepath + filename}", "Save success")

        self.report({'INFO'}, f"SMH Exporter: Finished in {end_time - start_time:.4f} seconds")
        return {'FINISHED'}


class SMHConverter:
    selected_metadata: SMHMetaData
    import_props: SMHImportProperties

    def __init__(self, selected_metadata: SMHMetaData, import_props: SMHImportProperties):
        self.selected_metadata = selected_metadata
        self.import_props = import_props

    def load_file(self, object: bpy.types.Object, metadata: SMHMetaData):
        # Use the selected armature's loaded SMH file
        abspath = bpy.path.abspath(self.selected_metadata.loadpath)
        with open(abspath) as f:
            result, msg = SMHFile.deserialize(f, metadata=metadata, filepath=abspath,
                                              armature=object, import_props=self.import_props)

            show_message(
                f"{object.name}: {msg}", "Success" if result else "Error",
                'INFO' if result else 'ERROR')

            if not result:
                return False

            return True

    def convert_camera(self, camera: CameraObject):
        selected_metadata = self.selected_metadata
        metadata: SMHMetaData = camera.smh_metadata
        properties: SMHProperties = camera.smh_properties

        passed, msg = check_smh_file(selected_metadata.loadpath, camera)
        if not passed:
            show_message(
                *
                msg or (
                    f"{camera.name}: No animation file supplied. Please supply one and try again",
                    "Error",
                    'ERROR'))
            return False

        if not properties.model:
            show_message(
                f"{camera.name}: Empty model path. Please supply an accurate model path for the specified camera (e.g. `models/kleiner.mdl`). If you have a .qc file, you can review the `$modelname`",
                "Error",
                'ERROR')
            return False

        return self.load_file(camera, metadata)

    def convert_armature(self, armature: ArmatureObject):
        selected_metadata = self.selected_metadata
        metadata: SMHMetaData = armature.smh_metadata
        properties: SMHProperties = armature.smh_properties

        passed, msg = check_smh_file(selected_metadata.loadpath, armature)
        if not passed:
            show_message(
                *
                msg or (
                    f"{armature.name}: No animation file supplied. Please supply one and try again",
                    "Error",
                    'ERROR'))
            return False

        passed, msg = check_smh_file(metadata.ref_path, armature)
        if not passed:
            show_message(
                *
                msg or (
                    f"{armature.name}: No reference file supplied. Please supply one and try again",
                    "Error",
                    'ERROR'))
            return False

        if not properties.model:
            show_message(
                f"{armature.name}: Empty model path. Please supply an accurate model path for the specified armature (e.g. `models/kleiner.mdl`). If you have a .qc file, you can review the `$modelname`",
                "Error",
                'ERROR')
            return False

        result, msg = check_metadata_for_maps(metadata=metadata, armature=armature)
        if not result and msg:
            show_message(*msg)
            return False

        return self.load_file(armature, metadata)

    def convert(self, object: ArmatureObject | CameraObject):
        if object.type == 'ARMATURE':
            return self.convert_armature(object)
        elif object.type == 'CAMERA':
            return self.convert_camera(object)


class SMH_OT_SMHToBlender(bpy.types.Operator):
    """Translate SMH to Blender"""
    bl_idname = "smh.smh2blender"
    bl_label = "Import SMH File"
    bl_description = "Read an SMH text file and load its animation onto the selected armature"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        import_props: SMHImportProperties = context.scene.smh_import_props
        layout = self.layout

        col = layout.column()
        col.prop(import_props, "batch")
        col.prop(import_props, "smh_version")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        # disable the operator if no Armature object is selected
        return context.active_object and context.active_object.type in acceptable_types

    def execute(self, context):
        scene = context.scene
        import_props: SMHImportProperties = scene.smh_import_props
        selected_armature: ArmatureObject = context.active_object
        selected_metadata: SMHMetaData = selected_armature.smh_metadata

        converter = SMHConverter(selected_metadata, import_props)
        start_time = time.perf_counter()
        if import_props.batch:
            for armature in bpy.data.objects:
                converter.convert(armature)
        else:
            converter.convert(selected_armature)
        end_time = time.perf_counter()

        self.report({'INFO'}, f"SMH Importer: Finished in {end_time - start_time:.4f} seconds")
        return {'FINISHED'}


class View3DPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animation"


class SMH_PT_SMHPresets(PresetPanel, bpy.types.Panel):
    bl_label = "SMH Importer/Exporter Presets"
    preset_subdir = "smh2blender"
    preset_operator = "script.execute_preset"
    preset_add_operator = "smh.add_smh_preset"


class SMH_MT_SMHPresets(bpy.types.Menu):
    bl_label = "SMH Importer/Exporter Presets"
    preset_subdir = "smh2blender"
    preset_operator = "script.execute_preset"
    draw = bpy.types.Menu.draw_preset


class SMH_OT_AddSMHPreset(AddPresetBase, bpy.types.Operator):
    bl_idname = "smh.add_smh_preset"
    bl_label = "Save SMH Importer/Exporter Preset"
    preset_menu = 'SMH_MT_SMHPresets'
    bl_options = {'UNDO', 'REGISTER'}

    preset_defines = {
        'metadata = bpy.context.active_object.smh_metadata',
        'props = bpy.context.active_object.smh_properties'
    }

    preset_values = [
        'props.model',
        'props.name',
        'props.cls',
        'props.map',

        'metadata.physics_obj_path',
        'metadata.bone_path',
        'metadata.ref_path',
        'metadata.ref_name',
        'metadata.savepath',
        'metadata.loadpath',
        'metadata.name',
        'metadata.import_ang',
        'metadata.export_ang',
        'metadata.import_stretch',
    ]

    preset_subdir = 'smh2blender'


class SMH_PT_Menu(View3DPanel, bpy.types.Panel):
    bl_idname = "VIEW_3D_PT_smh_blender"
    bl_label = "SMH Importer/Exporter"

    def draw_header_preset(self, context):
        SMH_PT_SMHPresets.draw_panel_header(self.layout)

    def draw(self, context):
        layout = self.layout

        object: bpy.types.Object = context.active_object
        if not context.object or context.object.type not in acceptable_types:
            layout.label(text="Select an armature or camera")
            return

        metadata: SMHMetaData = object.smh_metadata
        properties: SMHProperties = object.smh_properties

        if context.object.type == 'ARMATURE':
            box = layout.box()
            box.label(text="Configuration", icon='TEXT')
            box.prop(metadata, "bone_path")
            box.prop(metadata, "physics_obj_path")
            box.prop(metadata, "ref_path")
            box.prop(metadata, "ref_name")
            box.prop(metadata, "flex_path")
            box.prop(metadata, "shapekey_object")

        box = layout.box()
        box.label(text="Export Settings", icon='TOOL_SETTINGS')
        box.prop(properties, "map")
        box.prop(properties, "model")
        box.prop(properties, "name")
        box.prop(properties, "cls")
        box.prop(metadata, "savepath")
        box.prop(metadata, "export_shapekeys_to_flex")
        box.label(text="Position Offset", icon='EMPTY_ARROWS')
        box.prop(metadata, "export_pos")
        box.label(text="Angle Offset", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        box.prop(metadata, "export_ang")

        box = layout.box()
        box.label(text="Import Settings", icon='TOOL_SETTINGS')
        box.prop(metadata, "name")
        box.prop(metadata, "loadpath")
        box.prop(metadata, "import_stretch")
        box.prop(metadata, "import_flex_to_shapekeys")
        box.label(text="Angle Offset", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        box.prop(metadata, "import_ang")

        row = layout.row()
        smh2blender = row.operator('smh.smh2blender')
        blender2smh = row.operator('smh.blender2smh')


classes = (
    SMHProperties,
    SMHExportProperties,
    SMHImportProperties,
    SMHMetaData,

    SMH_OT_BlenderToSMH,
    SMH_OT_SMHToBlender,
    SMH_MT_SMHPresets,
    SMH_PT_SMHPresets,
    SMH_OT_AddSMHPreset,
    SMH_PT_Menu
)


def register():
    register_modifiers()

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.smh_metadata = PointerProperty(type=SMHMetaData)
    bpy.types.Object.smh_properties = PointerProperty(type=SMHProperties)
    bpy.types.Scene.smh_export_props = PointerProperty(type=SMHExportProperties)
    bpy.types.Scene.smh_import_props = PointerProperty(type=SMHImportProperties)


def unregister():
    unregister_modifiers()

    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Object.smh_metadata
    del bpy.types.Object.smh_properties
    del bpy.types.Scene.smh_export_props
    del bpy.types.Scene.smh_import_props
