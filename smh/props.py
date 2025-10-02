import bpy

from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty, IntProperty, FloatVectorProperty, PointerProperty
from mathutils import Euler, Vector

from math import radians
from os.path import basename


def SMHClass():
    return EnumProperty(
        name="Class",
        default='prop_ragdoll',
        description="The entity's class name, reflecting what they are in Source Engine",
        items=[
            ('prop_ragdoll', "Ragdoll", ""),
            ('prop_physics', "Prop", ""),
            ('prop_effect', "Effect", ""),
            ('gmod_cameraprop', "Camera", ""),
            ('hl_camera', "Advanced Camera", ""),
        ])


def SMHVersion():
    return EnumProperty(name="Save version",
                        description="Which version of SMH to use",
                        items=[('2', "2.0", ""), ('3', "3.0", ""), ('4', "4.0", "")],
                        default='4'
                        )


def BatchProperty(name: str, description: str):
    return BoolProperty(
        name=name,
        description=description,
        default=False
    )


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
    cls: SMHClass()
    map: StringProperty(
        name="Map",
        description="Where the animation will play. It informs the animator that an animation is made for a specific place",
        default="gm_construct")


class SMHExportProperties(bpy.types.PropertyGroup):
    use_scene_range: BoolProperty(
        name="Use scene frame range?",
        description="Whether the addon will export the action using the frame range defined on the dope sheet or from the action's Manual Frame Range.",
        default=True,
    )

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

    batch: BatchProperty(
        "Batch Export",
        "Export all actions from each armature in the scene into an SMH animation file. The selected armature's action will be used as the name"
    )
    visual_keying: BoolProperty(
        name="Visual Keying",
        description="If enabled, the addon will export the visual transforms of the bones, rather than the local transforms. This is useful if you have constraints or parented bones that you want to be reflected in the SMH animation",
        default=True,
    )


class SMHImportProperties(bpy.types.PropertyGroup):
    smh_version: SMHVersion()
    batch: BatchProperty(
        "Batch Import",
        "Import the selected armature's animation file for all armatures in the scene. The name property from each armature's Import Settings will reference the selected armature's animation file"
    )


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
        subtype='FILE_PATH')
    flex_path: StringProperty(
        name="Flex map",
        description="A list of flex controller names, ordered according to the sequence they were defined in their qc file. It maps the indices from the weight to a name, allowing Blender to choose which shapekey to assign the weight",
        default="",
        subtype='FILE_PATH')
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
    cls: SMHClass()
    import_ang: FloatVectorProperty(name="", min=-180, max=180, size=3, subtype='XYZ')
    export_ang: FloatVectorProperty(name="", min=-180, max=180, size=3, subtype='XYZ')
    export_pos: FloatVectorProperty(name="", min=-128, max=128, size=3, subtype='XYZ')

    import_stretch: BoolProperty(
        name="Import stretching",
        description="If checked, SMH animations that move the physics bones of the model will be reflected on the Blender armature."
    )
    shapekey_object: PointerProperty(
        name="Shapekey object",
        description="The object to import or export shapekey animations.",
        type=bpy.types.Mesh
    )
    import_flex_to_shapekeys: BoolProperty(
        name="Import flexes to shapekeys",
        description="If checked, face flex animations will automatically be imported as keyframes to shapekeys. Note that the order of flexes in GMod must match the shapekeys in Blender"
    )
    export_shapekeys_to_flex: BoolProperty(
        name="Export shapekeys to flexes",
        description="If checked, shapekey animations will be exported to a face flex animation. Existing flexes from previous imports may be overridden"
    )

    def import_angle_offset(self):
        return Euler((radians(self.import_ang[0]), radians(self.import_ang[1]), radians(self.import_ang[2])))

    def export_angle_offset(self):
        return Euler((radians(self.export_ang[0]), radians(self.export_ang[1]), radians(self.export_ang[2])))

    def export_pos_offset(self):
        return Vector((self.export_pos[0], self.export_pos[1], self.export_pos[2]))
