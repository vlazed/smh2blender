import bpy
from bpy.props import *

import json
import os
from math import radians
from typing import TypedDict, Union
from mathutils import Vector, Euler, Matrix
from math import floor

from .frame import PhysBoneFrames, BoneFrames, PhysBoneTree

ArmatureObject = Union[bpy.types.Armature, bpy.types.Object]


class GenericBoneField:
    class Data(TypedDict):
        Pos: str
        Ang: str

    pos: Vector
    ang: Euler
    armature: ArmatureObject

    @staticmethod
    def get_matrix(pos: Vector, ang: Euler, scale: Vector = Vector((1, 1, 1, 1))):
        # Convert to pose space
        return Matrix.Translation(pos) @ (ang.to_matrix().to_4x4()) @ Matrix.Diagonal(scale)

    def __init__(self, armature: ArmatureObject, data: Data, angle_offset: Euler = Euler()):
        self.pos = self.transform_vec(data["Pos"], sign=(1, 1, -1))
        self.ang = self.transform_ang(data["Ang"], angle_offset=angle_offset)
        self.armature = armature
        self.matrix = self.get_matrix(self.pos, self.ang)

    def add_pos(self, offset: Vector):
        self.pos += offset
        self.matrix = self.get_matrix(self.pos, self.ang)

    def transform_vec(self, vec: str, sign=(1, 1, 1)) -> Vector:
        """Transform an SMH vector into a Blender `Vector` in local space

        Also switches y and z axes, as a bone's up axis is y.

        Args:
            vec (str): SMH vector

        Returns:
            Vector: Blender vector in local space
        """
        vec_list = [float(x) for x in vec[1:-1].split(" ")]
        return Vector((sign[0] * vec_list[0], sign[1] * vec_list[2], sign[2] * vec_list[1]))

    def transform_ang(self, ang: str, angle_offset: Euler = Euler()) -> Euler:
        """Transform an SMH angle into a Blender angle in local space.

        Args:
            ang (str): SMH Angle

        Returns:
            Euler: Blender angle in local space
        """

        # Gotcha: Blender uses radians to represent its Euler angles. Convert to this
        # Switch YZX (120) -> XYZ (012)
        ang_list = [radians(float(x)) for x in ang[1:-1].split(" ")]
        return Euler((ang_list[2] + angle_offset.x, ang_list[0] + angle_offset.y, ang_list[1] + angle_offset.z))


class PhysBoneField(GenericBoneField):
    class Data(GenericBoneField.Data):
        LocalPos: str | None
        LocalAng: str | None

    local_pos: Vector | None
    local_ang: Euler | None
    local_matrix: Matrix | None

    def __init__(self, armature: bpy.types.Armature, data: Data, angle_offset: Euler):
        super().__init__(armature=armature, data=data, angle_offset=angle_offset)
        self.local_pos = self.local_ang = self.local_matrix = None
        if data.get("LocalPos"):
            self.local_pos = self.transform_local_vec(
                data["LocalPos"], sign=(1, 1, 1))
            self.local_ang = self.transform_local_ang(data["LocalAng"])
            self.local_matrix = self.get_matrix(self.local_pos, self.local_ang)

    def transform_local_ang(self, ang: str) -> Euler:
        """Transform an SMH local angle into a Blender angle in local space

        Args:
            ang (str): SMH local angle, with respect to its physics bone parent

        Returns:
            Euler: Blender angle in local space
        """
        # Gotcha: Blender uses radians to represent its Euler angles. Convert to this
        # Switch YZX (120) -> XYZ (012)
        ang_list = [radians(float(x)) for x in ang[1:-1].split(" ")]
        return Euler((ang_list[2], ang_list[0], ang_list[1]))

    def transform_local_vec(self, vec: str, sign=(1, 1, 1)) -> Euler:
        """Transform an SMH local pos into a Blender angle in local space

        Args:
            vec (str): SMH local pos, with respect to its physics bone parent

        Returns:
            Vector: Blender vector in local space
        """

        # Switch back the y and z axes for the local vectors
        new_vec = self.transform_vec(vec, sign)
        return Vector((new_vec[0], new_vec[2], new_vec[1]))

    def set_ref_offset(self, refphysbone, is_root: bool):
        """Use the reference mapped physics bone to correct the local angle

        Args:
            refphysbone (PhysBoneField): Reference physics bone
        """

        if is_root:
            self.ang = (refphysbone.ang.to_matrix().transposed()
                        @ self.ang.to_matrix()).to_euler()
            self.matrix = self.get_matrix(self.pos, self.ang)

        if self.local_pos:
            self.local_pos = (
                refphysbone.local_matrix.inverted()
                @ self.local_matrix).translation
            self.local_ang = (refphysbone.local_ang.to_matrix(
            ).transposed() @ self.local_ang.to_matrix()).to_euler()
            self.local_matrix = self.get_matrix(self.local_pos, self.local_ang)


class BoneField(GenericBoneField):
    class Data(GenericBoneField.Data):
        Scale: str | None

    scale: Vector

    def transform_manip_ang(self, ang: str) -> Euler:
        """Transform a bone manipulation space SMH angle to a Blender angle in local space

        Args:
            ang (str): SMH angle in bone manipulation space

        Returns:
            Euler: Blender angle in local space
        """
        # Gotcha: Blender uses radians to represent its Euler angles. Convert to this
        # Switch YZX (120) -> XYZ (012)
        ang_list = [radians(float(x)) for x in ang[1:-1].split(" ")]
        return Euler((ang_list[2], ang_list[0], ang_list[1]))

    def __init__(self, armature: bpy.types.Armature, data: Data):
        super().__init__(armature=armature, data=data)
        self.ang = self.transform_manip_ang(data["Ang"])
        self.scale = self.transform_vec(data["Scale"]).to_4d()
        self.scale[3] = 1
        self.matrix = self.get_matrix(self.pos, self.ang, self.scale)


class SMHEntityData():
    class SMHEntityDataDict(TypedDict):
        bones: dict[str, str]
        physbones: dict[str, str]
        EaseOut: dict[str, float]
        EaseIn: dict[str, float]
        Position: int

    data: SMHEntityDataDict
    armature: bpy.types.Armature | bpy.types.Object
    position: int

    def __init__(self, position: int, armature: bpy.types.Armature):
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

    def to_json(self, physbones, bones) -> SMHEntityDataDict:
        self.bake_physbones(physbones)
        self.bake_bones(bones)

        return self.data


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
            value = os.path.basename(self.model)

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

    def to_json(self) -> str:
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


def load_map(map_path: str):
    map = []
    with open(map_path) as f:
        map = f.read().splitlines()

    return map


class SMHEntity():
    class SMHEntityDict(TypedDict):
        Frames: list[SMHEntityData]
        Properties: str
        Model: str

    data: SMHEntityDict
    armature: bpy.types.Armature | bpy.types.Object
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
    def load_bones(entity, armature):
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
    def load_entity(data, name: str):
        return next((
            entity for entity in data.get("Entities")
            if entity.get("Properties") and entity["Properties"].get("Name", "") == name), None
        )

    def __init__(self, armature: bpy.types.Armature | bpy.types.Object, properties: SMHProperties, metadata: SMHMetaData):
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

        physics_obj_map = []
        with open(bpy.path.abspath(self.metadata.physics_obj_path)) as f:
            physics_obj_map = f.read().splitlines()

        bone_map = []
        with open(bpy.path.abspath(self.metadata.bone_path)) as f:
            bone_map = f.read().splitlines()

        frame_range = (floor(self.armature.animation_data.action.frame_start), floor(
            self.armature.animation_data.action.frame_end + 1))

        physbone_frames = PhysBoneFrames(
            self.armature, frame_range).to_json(physics_obj_map=physics_obj_map)

        bone_frames = BoneFrames(
            self.armature, frame_range).to_json(bone_map=bone_map)

        for frame in range(frame_range[0], frame_range[1]):
            entityData = SMHEntityData(armature=self.armature, position=frame)
            self.data["Frames"].append(entityData.to_json(
                physbone_frames[str(frame)], bone_frames[str(frame)]))

        return self.data

    @classmethod
    def bake_from_smh(cls, data, metadata: SMHMetaData, filename: str, armature: ArmatureObject):
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
            ref_data = json.load(f)
            ref_entity: SMHEntity.SMHEntityDict = cls.load_entity(
                ref_data, ref_name)
            if not ref_entity:
                return False, f"Failed to load {filename}: reference entity name doesn't match {name}"
            ref_physbone_data = cls.load_physbones(
                armature=armature, entity=ref_entity)

        entity: SMHEntity.SMHEntityDict = cls.load_entity(data, name)
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

            matrices = None
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
    class SMHFileData(TypedDict):
        Map: str
        Entities: list[SMHEntity]

    data: SMHFileData

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
