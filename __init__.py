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
from bpy.props import *

from .smh.data import SMHProperties, SMHMetaData, SMHFile

bl_info = {
    "name": "Smh2blender",
    "author": "vlazed",
    "description": "Exchange animations between Blender and Garry's Mod",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Generic",
}

# https://blender.stackexchange.com/questions/109711/how-to-popup-simple-message-box-from-python-console


def show_message(message="", title="Message Box", icon='INFO'):

    def draw(self: bpy.types.Panel, context: bpy.types.Context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


class ConvertBlenderToSMH(bpy.types.Operator):
    """Translate Blender to SMH"""
    bl_idname = "smh.blender2smh"
    bl_label = "To SMH"
    bl_description = "Translate Blender keyframes into a text file that SMH can read, from the selected armature"

    @classmethod
    def poll(self, context: bpy.types.Context):
        # disable the operator if no Armature object is selected
        return context.active_object and context.active_object.type == 'ARMATURE'

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

        if not metadata.physics_obj_path:
            show_message(
                "Empty physics map. Please supply a physics map and try again", "Error", 'ERROR')
            return {'CANCELLED'}

        if not metadata.bone_path:
            show_message(
                "Empty bone map. Please supply a bone map and try again", "Error", 'ERROR')
            return {'CANCELLED'}

        if not properties.name:
            show_message(
                "Empty model name. Please give the model a descriptive name and try again", "Error", 'ERROR')
            return {'CANCELLED'}

        if not properties.model:
            show_message("Empty model path. Please supply an accurate model path for the specified armature (e.g. `models/kleiner.mdl`). If you have a .qc file, you can review the `$modelname`", "Error", 'ERROR')
            return {'CANCELLED'}

        if not metadata.savepath:
            show_message(
                "Empty save path. Please supply a location to save the animation file and try again", "Error", 'ERROR')
            return {'CANCELLED'}

        fileName = armature.animation_data.action.name + ".txt"

        smhFile = SMHFile(properties.map)
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
    bl_label = "To Blender"
    bl_description = "Read an SMH text file and load its animation onto the selected armature"

    @classmethod
    def poll(self, context: bpy.types.Context):
        # disable the operator if no Armature object is selected
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        return {'FINISHED'}


class View3DPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"


class BlenderSMHPanel(View3DPanel, bpy.types.Panel):
    bl_idname = "VIEW_3D_PT_smh_blender"
    bl_label = "Blender SMH"

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        metadata: SMHMetaData = scene.smh_metadata
        properties: SMHProperties = scene.smh_properties

        box = layout.box()
        box.label(text="Configuration", icon='TEXT')
        box.prop(metadata, "bone_path")
        box.prop(metadata, "physics_obj_path")
        box.prop(metadata, "savepath")

        box = layout.box()
        box.label(text="Save Settings", icon='TOOL_SETTINGS')
        box.prop(properties, "map")
        box.prop(properties, "model")
        box.prop(properties, "name")
        box.prop(properties, "cls")

        row = layout.row()
        blender2smh = row.operator('smh.blender2smh')
        smh2blender = row.operator('smh.smh2blender')


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
