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
from bpy.props import PointerProperty, BoolProperty, IntProperty

from .smh.props import SMHProperties, SMHMetaData, SMHVersion
from .smh.data import SMHFile

bl_info = {
    "name": "SMH Importer/Exporter",
    "author": "vlazed",
    "description": "Exchange animations between Blender and Garry's Mod",
    "blender": (2, 80, 0),
    "version": (0, 1, 2),
    "location": "",
    "warning": "",
    "category": "Animation",
}


def show_message(message="", title="Message Box", icon='INFO'):
    # https://blender.stackexchange.com/questions/109711/how-to-popup-simple-message-box-from-python-console

    def draw(self: bpy.types.Panel, context: bpy.types.Context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def check_metadata_for_maps(metadata: SMHMetaData):
    passed = True
    msg = None
    if not metadata.physics_obj_path:
        passed = False
        msg = (
            "Empty physics map. Please supply a physics map and try again", "Error", 'ERROR')

    if not metadata.bone_path:
        passed = False
        msg = ("Empty bone map. Please supply a bone map and try again",
               "Error", 'ERROR')

    return passed, msg


def check_smh_file(path):
    passed = True
    msg = None
    if not path:
        passed = False

    if passed and not path.endswith(".txt"):
        passed = False
        msg = (
            "SMH animation files must end with \".txt\".", "Error", 'ERROR')

    return passed, msg


class ConvertBlenderToSMH(bpy.types.Operator):
    """Translate Blender to SMH"""
    bl_idname = "smh.blender2smh"
    bl_label = "Export SMH File"
    bl_description = "Translate Blender keyframes into a text file that SMH can read, from the selected armature"

    keyframes_only: BoolProperty(
        name="Keyframes only?",
        description="Only evaluate the f-curve if a keyframe is defined at a certain frame. Disables Frame step if checked.",
        default=False,
    )

    frame_step: IntProperty(
        name="Frame step",
        description="Resolution of the animation when exported to SMH. Higher frame steps result in a less accurate portrayal in SMH, but it is more flexible to modify. Lower frame steps is more accurate, but it is less flexible to modify",
        min=1,
        soft_max=10,
        default=1,
    )

    smh_version: SMHVersion()

    def draw(self, context):
        layout = self.layout

        key = layout.row()
        key.prop(self, "keyframes_only")
        frame = layout.row()
        frame.enabled = not self.keyframes_only
        frame.prop(self, "frame_step")
        row = layout.row()
        row.prop(self, "smh_version")

        # # This won't show up in older versions of Blender. Nonetheless, this is certainly cosmetic
        # row.template_popup_confirm("smh.blender2smh", text="Export", cancel_text="Cancel", cancel_default=True)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        # disable the operator if no Armature object is selected
        return context.active_object and context.active_object.type == 'ARMATURE'

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        metadata: SMHMetaData = scene.smh_metadata
        properties: SMHProperties = scene.smh_properties

        # We polled for an armature, so our active object should be one
        armature: bpy.types.Armature | bpy.types.Object = context.active_object

        if not armature.animation_data.action:
            show_message(
                "No animation found. Make sure that an armature has an `Animation`", "Error", 'ERROR')
            return {'CANCELLED'}

        result = check_metadata_for_maps(metadata=metadata)
        if not result:
            show_message(*result[2])
            return {'CANCELLED'}

        if not properties.name:
            show_message(
                "Empty model name. Please give the model a descriptive name and try again", "Error", 'ERROR')
            return {'CANCELLED'}

        if not properties.model:
            show_message(
                "Empty model path. Please supply an accurate model path for the specified armature (e.g. `models/kleiner.mdl`). If you have a .qc file, you can review the `$modelname`",
                "Error",
                'ERROR')
            return {'CANCELLED'}

        if not metadata.savepath:
            show_message(
                "Empty save path. Please supply a location to save the animation file and try again", "Error", 'ERROR')
            return {'CANCELLED'}

        fileName = armature.animation_data.action.name + ".txt"

        smhFile = SMHFile(properties.map, check_keyframes=self.keyframes_only, frame_step=self.frame_step)
        contents = smhFile.serialize(armature, metadata, properties)
        try:

            with open(bpy.path.abspath(metadata.savepath + fileName), "w+") as f:
                f.write(contents)
        except Exception as e:
            show_message(
                f"An error as occurred during the process: {e}", "Error", 'ERROR')
            return {'CANCELLED'}

        show_message(
            f"Successfully wrote save file to {metadata.savepath + fileName}", "Save success")
        return {'FINISHED'}


class ConvertSMHToBlender(bpy.types.Operator):
    """Translate SMH to Blender"""
    bl_idname = "smh.smh2blender"
    bl_label = "Import SMH File"
    bl_description = "Read an SMH text file and load its animation onto the selected armature"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        # disable the operator if no Armature object is selected
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        scene = context.scene
        metadata: SMHMetaData = scene.smh_metadata
        properties: SMHProperties = scene.smh_properties

        # We polled for an armature, so our active object should be one
        armature: bpy.types.Armature | bpy.types.Object = context.active_object

        passed, msg = check_smh_file(metadata.loadpath)
        if not passed:
            show_message(
                *msg or ("No animation file supplied. Please supply one and try again", "Error", 'ERROR'))
            return {'CANCELLED'}

        passed, msg = check_smh_file(metadata.ref_path)
        if not passed:
            show_message(
                *msg or ("No reference file supplied. Please supply one and try again", "Error", 'ERROR'))
            return {'CANCELLED'}

        if not properties.model:
            show_message(
                "Empty model path. Please supply an accurate model path for the specified armature (e.g. `models/kleiner.mdl`). If you have a .qc file, you can review the `$modelname`",
                "Error",
                'ERROR')
            return {'CANCELLED'}

        result = check_metadata_for_maps(metadata=metadata)
        if not result:
            show_message(*result[2])
            return {'CANCELLED'}

        abspath = bpy.path.abspath(metadata.loadpath)
        with open(abspath) as f:
            file = SMHFile()
            result, msg = file.deserialize(
                f, metadata=metadata,
                filepath=abspath, armature=armature
            )

            show_message(
                msg, "Success" if result else "Error",
                'INFO' if result else 'ERROR')

        return {'FINISHED'}


class View3DPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animation"


class BlenderSMHPanel(View3DPanel, bpy.types.Panel):
    bl_idname = "VIEW_3D_PT_smh_blender"
    bl_label = "SMH Importer/Exporter"

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        metadata: SMHMetaData = scene.smh_metadata
        properties: SMHProperties = scene.smh_properties

        box = layout.box()
        box.label(text="Configuration", icon='TEXT')
        box.prop(metadata, "bone_path")
        box.prop(metadata, "physics_obj_path")
        box.prop(metadata, "ref_path")
        box.prop(metadata, "ref_name")

        box = layout.box()
        box.label(text="Export Settings", icon='TOOL_SETTINGS')
        box.prop(properties, "map")
        box.prop(properties, "model")
        box.prop(properties, "name")
        box.prop(properties, "cls")
        box.prop(metadata, "savepath")

        box = layout.box()
        box.label(text="Import Settings", icon='TOOL_SETTINGS')
        box.prop(metadata, "name")
        box.prop(metadata, "loadpath")
        box.prop(metadata, "import_stretch")
        box.label(text="Angle Offset", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        box.prop(metadata, "ang_x")
        box.prop(metadata, "ang_y")
        box.prop(metadata, "ang_z")

        row = layout.row()
        smh2blender = row.operator('smh.smh2blender')
        blender2smh = row.operator('smh.blender2smh')


classes = (
    ConvertBlenderToSMH,
    ConvertSMHToBlender,
    SMHProperties,
    SMHMetaData,
    BlenderSMHPanel
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.smh_metadata = PointerProperty(type=SMHMetaData)
    bpy.types.Scene.smh_properties = PointerProperty(type=SMHProperties)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.smh_metadata
    del bpy.types.Scene.smh_properties
