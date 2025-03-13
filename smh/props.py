import bpy

from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from mathutils import Euler

from math import radians
from os.path import basename

from .types import SMHPropertiesDict


class SMHProperties(bpy.types.PropertyGroup):
    def set_model(self, value: str):
        if len(value.strip()) == 0:
            return

        self["model"] = value

    def get_model(self):
        return self.get("model", "models/kleiner.mdl")

    model: StringProperty(
        name="Model path",
        description="The location of the model with respect to the game's root folder)",
        set=set_model,
        get=get_model
    )

    def set_name(self, value: str):
        if len(value.strip()) == 0:
            value = basename(self.model)

        if len(value) == 0:
            return

        self["name"] = value

    def get_name(self):
        return self.get("name", "kleiner")

    name: StringProperty(
        name="Name",
        description="A unique identifier of the model, which Stop Motion Helper displays to the user (rather than e.g. kleiner.mdl)",
        set=set_name,
        get=get_name,
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

    def to_json(self) -> SMHPropertiesDict:
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
    ref_path: StringProperty(
        name="Reference",
        description="An SMH animation file of the model in reference pose. This is mainly used to pose the model from the physical bones.",
        default="",
        subtype='FILE_PATH'
    )
    savepath: StringProperty(
        name="Save path",
        description="Choose where to save animation file",
        default="",
        subtype='DIR_PATH'
    )
    loadpath: StringProperty(
        name="Load path",
        description="Load an SMH animation text file",
        default="",
        subtype='FILE_PATH'
    )
    name: StringProperty(
        name="Name",
        description="The name of the model to fetch from the SMH file. Ensure the model matches the selected armature, or else the action will not look correct",
    )
    ref_name: StringProperty(
        name="Ref Name",
        description="The name of the model to fetch from the reference file.",
    )
    ang_x: FloatProperty(
        name="X",
        min=-180,
        max=180
    )
    ang_y: FloatProperty(
        name="Y",
        min=-180,
        max=180
    )
    ang_z: FloatProperty(
        name="Z",
        min=-180,
        max=180
    )
    import_stretch: BoolProperty(
        name="Import stretching",
        description="If checked, SMH animations that move the physics bones of the model will be reflected on the Blender armature."
    )

    def angle_offset(self):
        return Euler((radians(self.ang_x), radians(self.ang_y), radians(self.ang_z)))
