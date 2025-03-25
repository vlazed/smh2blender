# PropertyGroups with a `value` indicate that the data is directly assigned to the modifier,
# e.g. 'skin': 0.0, rather than 'skin': {"Skin": 0.0}
# TODO: Split these classes into their own files, to make this "extensive-friendly" by
# providing py files for new modifiers

import bpy

from bpy.props import FloatProperty, FloatVectorProperty, PointerProperty, CollectionProperty, StringProperty


class AdvancedCamera(bpy.types.PropertyGroup):
    FOV: FloatProperty(name="FOV", min=0, max=179.99, default=75, options={'ANIMATABLE'})
    Nearz: FloatProperty(name="NearZ", min=0, options={'ANIMATABLE'})
    Farz: FloatProperty(name="FarZ", min=0, options={'ANIMATABLE'})
    Roll: FloatProperty(name="Roll", min=0, options={'ANIMATABLE'})
    Offset: FloatVectorProperty(name="Offset", default=(0, 0, 0), options={'ANIMATABLE'})


class FlexWeight(bpy.types.PropertyGroup):
    name: StringProperty(name="Flex")
    value: FloatProperty(options={'ANIMATABLE'}, default=0)


class Flex(bpy.types.PropertyGroup):
    Weights: CollectionProperty(type=FlexWeight)
    Scale: FloatProperty(name="Scale", options={'ANIMATABLE'})


class EyeTarget(bpy.types.PropertyGroup):
    EyeTarget: FloatVectorProperty(name="Eye Target", default=(180, 0, 0), options={'ANIMATABLE'})


class BodygroupItem(bpy.types.PropertyGroup):
    name: StringProperty(name="Bodygroup")
    value: FloatProperty(options={'ANIMATABLE'}, default=0)


class Bodygroup(bpy.types.PropertyGroup):
    value: CollectionProperty(
        type=BodygroupItem
    )


class Skin(bpy.types.PropertyGroup):
    value: FloatProperty(name="Skin", default=0, step=1, options={'ANIMATABLE'})


class ModelScale(bpy.types.PropertyGroup):
    ModelScale: FloatProperty(name="ModelScale", default=1.0, options={'ANIMATABLE'})


class Color(bpy.types.PropertyGroup):
    Color: FloatVectorProperty(name="Color", size=4, default=(255, 255, 255, 255), options={'ANIMATABLE'})


translations = {
    "smh_color": "color",
}

classes = {
    "flex": Flex,
    "advcamera": AdvancedCamera,
    "eyetarget": EyeTarget,
    "bodygroup": Bodygroup,
    "skin": Skin,
    "modelscale": ModelScale,
    # Doesn't work if "smh_color" -> "color".
    # I suspect some reserved properties in Blender, which is why this is called `smh_color` instead of `color`
    "smh_color": Color
}


class SMHModifierPanel(bpy.types.Panel):
    bl_label = "SMH Modifiers"
    bl_idname = "OBJECT_PT_smh_modifiers"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        for name in classes:
            entry: bpy.types.PropertyGroup = getattr(context.object, name)
            col = layout.column(align=True)
            col.label(text=name)
            box = col.box()
            for property in entry.bl_rna.properties:
                if property.is_runtime:
                    row = box.row(align=True)
                    row.label(text=property.name)
                    row.prop(entry, property.identifier, text="")


def register_modifiers():
    bpy.utils.register_class(BodygroupItem)
    bpy.utils.register_class(FlexWeight)

    for name, cls in classes.items():
        bpy.utils.register_class(cls)
        setattr(bpy.types.Object, name, PointerProperty(type=cls))
    bpy.utils.register_class(SMHModifierPanel)


def unregister_modifiers():
    bpy.utils.unregister_class(BodygroupItem)
    bpy.utils.unregister_class(FlexWeight)

    for name, cls in classes.items():
        bpy.utils.unregister_class(cls)
        delattr(bpy.types.Object, name)
    bpy.utils.unregister_class(SMHModifierPanel)
