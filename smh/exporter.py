import bpy

from bpy.types import Bone, PoseBone, ActionFCurves, Armature, Object
from math import degrees, radians, floor
from mathutils import Vector, Euler, Matrix, Quaternion
from abc import abstractmethod
from typing import List

from .types.frame import BoneData, PhysBoneData, ModifierData, FlexData, SMHFrameResult, SMHFrameBuilder
from .types.shared import BoneMap, ArmatureObject, SMHFileType
from .types.entity import SMHEntityResult

from .props import SMHExportProperties
from .modifiers import classes as modifiers, translations as mod_map

ORDER = 'XYZ'


def get_matrix_basis_from_fcurve(pbone: PoseBone, fcurves: ActionFCurves, frame: int) -> Matrix:
    """https://blender.stackexchange.com/questions/302699/calculate-a-pose-bones-transformation-matrix-from-its-f-curve-without-updating

    # Args:
        pbone (PoseBone)
        fcurves (ActionFCurves)
        frame (int)

    # Returns:
        Matrix
    """
    vecs = [Vector(), Vector([1, 1, 1, 1])]
    props = ('location', 'scale')
    for j in range(len(props)):
        data_path = pbone.path_from_id(props[j])
        for i in range(3):
            fc = fcurves.find(data_path, index=i)
            if fc is None:
                continue
            vecs[j][i] = fc.evaluate(frame)
    trans = Matrix.Translation(vecs[0])
    scale = Matrix.Diagonal(vecs[1])

    data_path = pbone.path_from_id('rotation_euler')
    ang, temp_ang = Euler((0, 0, 0), ORDER), Euler((0, 0, 0), ORDER)
    num_components = 3
    if pbone.rotation_mode == 'QUATERNION' or pbone.rotation_mode == 'AXIS_ANGLE':
        data_path = pbone.path_from_id('rotation_quaternion')
        ang, temp_ang = Quaternion(), Quaternion()
        num_components = 4

    for i in range(num_components):
        fc = fcurves.find(data_path, index=i)
        if fc is None:
            break
        temp_ang[i] = fc.evaluate(frame)
    else:
        ang = temp_ang
    rot = ang.to_matrix().to_4x4()

    return trans @ rot @ scale


def fcurve_exists(obj: Object, data_path: str):
    if not obj.animation_data.action:
        return False

    fcurves = obj.animation_data.action.fcurves

    if fcurves.find(data_path=data_path):
        return True

    return False


def get_modifier_frame_value(obj: Object, data_path: str, frame: int, index: int = 0) -> float:
    """Get the value of a modifier (by data_path) at a specific frame

    Args:
        obj (Object): Armature or any object with an action
        data_path (str): Modifier data path
        frame (int): Frame
        index (int, optional): Array index if modifier is an array. Defaults to 0.

    Returns:
        float: Value of modifier at a `frame`
    """

    if not obj.animation_data.action:
        return 0

    fcurves = obj.animation_data.action.fcurves
    fc = fcurves.find(data_path, index=index)

    return fc.evaluate(frame)


def get_pose_matrices(obj: Object, matrix_map: dict[str, Matrix], frame: int):
    """https://blender.stackexchange.com/questions/302699/calculate-a-pose-bones-transformation-matrix-from-its-f-curve-without-updating

    Assign pose space matrices of all bones at once, ignoring constraints.

    # Args:
        obj (Object): Armature or any object with an action
        matrix_map (dict[str, Matrix]): Bone to matrix mapping
        frame (int): Frame
    """

    if not obj.animation_data.action:
        return

    fcurves = obj.animation_data.action.fcurves

    def rec(pbone: PoseBone):

        matrix_basis = get_matrix_basis_from_fcurve(pbone, fcurves, frame)

        # Compute the updated pose matrix from local and new parent matrix
        if pbone.parent:
            matrix_map[pbone.name] = pbone.bone.convert_local_to_pose(
                matrix_basis,
                pbone.bone.matrix_local,
                parent_matrix=matrix_map[pbone.parent.name],
                parent_matrix_local=pbone.parent.bone.matrix_local,
            )
        else:
            matrix_map[pbone.name] = pbone.bone.convert_local_to_pose(
                matrix_basis,
                pbone.bone.matrix_local,
            )

        # Recursively process children, passing the new matrix through
        for child in pbone.children:
            rec(child)

    # Scan all bone trees from their roots
    for pbone in obj.pose.bones:
        if not pbone.parent:
            rec(pbone)


class PhysBoneTree:
    class PhysBone:
        parent: PoseBone | None
        bone: PoseBone

        def __init__(self, bone: PoseBone):
            super().__init__()
            self.bone = bone
            self.name = bone.name
            self.parent = None

        def get_parent(self, phys_map: BoneMap):
            phys_set = set(phys_map)
            walk = self.bone
            while walk.parent:
                walk = walk.parent
                if walk.name in phys_set:
                    self.parent = walk
                    break

        def __str__(self):
            return self.name

    bones: List[PhysBone]
    bone_dict: dict[str, int]

    def __init__(self, armature: Armature | Object, phys_map: BoneMap):
        self.armature = armature
        self.bones = []
        self.bone_dict = {}

        for phys_name in phys_map:
            bone = armature.pose.bones.get(phys_name)
            if not bone:
                continue

            physbone = self.PhysBone(bone)
            physbone.get_parent(phys_map=phys_map)

            self.bones.append(physbone)
            self.bone_dict[phys_name] = len(self.bones) - 1

    def get_bone_from_index(self, index) -> PoseBone:
        return self.bones[index].bone

    def get_parent(self, phys_name: str) -> PoseBone | None:
        if self.bone_dict.get(phys_name) and self.bones[self.bone_dict[phys_name]]:
            return self.bones[self.bone_dict[phys_name]].parent

    def get_parent_index(self, phys_name: str) -> int | None:
        return self.bone_dict.get(phys_name, None)

    def __str__(self):
        tree = ""
        none = "none"
        for bone in self.bones:
            bone_str = f"{{bone: {bone.name}, parent: {bone.parent.name if bone.parent else none}}}\n"
            tree += bone_str

        return tree


class Frame:
    pos: Vector
    ang: Euler
    bone: PoseBone

    @staticmethod
    def vec_to_str(vec: Vector, sign=(1, 1, 1)):
        return f"[{sign[0] * vec.x} {sign[1] * vec.y} {sign[2] * vec.z}]"

    @staticmethod
    def ang_to_str(ang: Euler):
        # We switch angles because
        # "QAngle are Pitch (around y), Yaw (around Z), Roll (around X)"
        # https://github.com/ValveSoftware/source-sdk-2013/blob/a62efecf624923d3bacc67b8ee4b7f8a9855abfd/src/public/vphysics_interface.h#L26
        return f"{{{degrees(ang.y)} {degrees(ang.z)} {degrees(ang.x)}}}"

    @staticmethod
    def list_to_json(lst: list[float]):
        if len(lst) == 3:
            return f"[{lst[0]} {lst[1]} {lst[2]}]"
        elif len(lst) == 4:
            return {
                "r": lst[0],
                "g": lst[1],
                "b": lst[2],
                "a": lst[3],
            }

    def __init__(self, bone: PoseBone):
        self.bone = bone
        self.pos = Vector()
        self.ang = Euler()

    @abstractmethod
    def calculate(self):
        pass

    @abstractmethod
    def to_json(self):
        pass


class BoneFrame(Frame):
    scale: Vector

    def __init__(self, bone):
        super().__init__(bone)
        self.scale = Vector()

    # manip_matrix is in local space
    def calculate(self, fcurves: ActionFCurves, frame: int):
        matrix_basis = get_matrix_basis_from_fcurve(self.bone, fcurves, frame)
        rest_matrix = self.bone.matrix_basis

        self.pos = matrix_basis.translation - rest_matrix.translation
        self.scale = matrix_basis.to_scale()

        rest_matrix.to_3x3().rotate(matrix_basis.to_euler(ORDER))
        self.ang = matrix_basis.to_euler(ORDER)

    def to_json(self) -> BoneData:
        return {
            "Pos": self.vec_to_str(self.pos),
            "Ang": self.ang_to_str(self.ang),
            "Scale": self.vec_to_str(self.scale),
        }


class FlexFrame:
    scale: float
    weights: list[float]

    def __init__(self, scale: float, weights: list[float]):
        self.scale = scale
        self.weights = weights

    def to_json(self) -> FlexData:
        data: FlexData = {
            "Scale": self.scale,
            "Weights": self.weights,
        }

        return data


class PhysBoneFrame(Frame):
    local_pos: Vector | None
    local_ang: Euler | None

    # Matrices are defined in pose space
    def calculate(self, matrix: Matrix, parent_matrix: Matrix | None):
        self.pos = matrix.translation
        self.ang = matrix.to_euler(ORDER)
        self.local_pos = None
        self.local_ang = None

        if parent_matrix:
            # Get `matrix` in its parent space
            local_matrix = parent_matrix.inverted() @ matrix
            self.local_pos = local_matrix.translation

            self.local_ang = local_matrix.to_euler(ORDER)

    def to_json(self) -> PhysBoneData:
        data: PhysBoneData = {
            "Moveable": False,
            "Pos": self.vec_to_str(self.pos, sign=(1, 1, 1)),
            "Ang": self.ang_to_str(self.ang),
        }
        if self.local_pos and self.local_ang:
            data["LocalPos"] = self.vec_to_str(self.local_pos)
            data["LocalAng"] = self.ang_to_str(self.local_ang)

        return data


class Frames:
    armature: Armature | Object
    frame_range: tuple[int, int, int]

    def __init__(self, armature: Armature | Object, frame_range: tuple[int, int]):
        self.armature = armature
        self.frame_range = frame_range

    @abstractmethod
    def to_json(self, map: BoneMap | None): pass


class ModifierFrames(Frames):
    def to_json(self):
        data: dict[str, ModifierData] = {}
        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            data[str(frame)] = {}
            # FIXME: Iterate through modifiers that have a keyframe, instead of all modifiers
            # Reduces n modifiers in O(n(2m)), and also discards one m fcurve check to O(nm), because
            # we needed to check of animation data existed
            for modifier in modifiers:
                attr: bpy.types.PropertyGroup | None = getattr(self.armature, modifier, None)
                if not attr:
                    continue
                props = [prop for prop in attr.bl_rna.properties if prop.is_runtime]
                mod_name = modifier
                if mod_map.get(modifier):
                    mod_name = mod_map[modifier]

                data[str(frame)][mod_name] = {}
                for prop in props:
                    prop_obj = getattr(attr, prop.identifier, None)
                    if prop_obj is None:
                        continue

                    data_path = f'{modifier}.{prop.identifier}'
                    if not fcurve_exists(self.armature, data_path):
                        continue

                    if prop.type == 'COLLECTION':
                        # If this is a CollectionProperty of size n, we want to store the value of each item in a dictionary:
                        # dict = {"0": val_0, "1": val_1 ... "n-1": val_n-1}
                        if prop.identifier == 'value':
                            data[str(frame)][mod_name] = {
                                str(index): get_modifier_frame_value(data_path=data_path, obj=self.armature, frame=frame, index=index)
                                for index, obj in enumerate(prop_obj)
                            }
                        else:
                            data[str(frame)][mod_name][prop.identifier] = {
                                str(index): get_modifier_frame_value(data_path=data_path, obj=self.armature, frame=frame, index=index)
                                for index, obj in enumerate(prop_obj)
                            }
                    elif prop.type == 'FLOAT':
                        # If this is a float of size 1 < n <= 4, we want to store the value of each item as a vector or color,
                        # depending on the size
                        if type(prop_obj) == bpy.types.bpy_prop_array:
                            data[str(frame)][mod_name][prop.identifier] = Frame.list_to_json([
                                get_modifier_frame_value(data_path=data_path, obj=self.armature, frame=frame, index=index)
                                for index in range(len(prop_obj))
                            ])
                        elif prop.identifier == 'value':
                            data[str(frame)][mod_name] = get_modifier_frame_value(
                                data_path=data_path, obj=self.armature, frame=frame)
                        else:
                            data[str(frame)][mod_name][prop.identifier] = get_modifier_frame_value(
                                data_path=data_path, obj=self.armature, frame=frame)
                if type(data[str(frame)][mod_name]) == dict and len(data[str(frame)][mod_name]) == 0:
                    # No keyframes exists for the current modifier? Don't use it
                    del data[str(frame)][mod_name]

        return data


class FlexFrames(Frames):
    shapekey_object: bpy.types.Mesh

    def __init__(self, armature: Armature | Object, frame_range: list[float], shapekey_object: bpy.types.Mesh):
        super().__init__(armature, frame_range)
        self.shapekey_object = shapekey_object

    def to_json(self, map: BoneMap):
        data: FlexData = {}

        shape_keys = self.shapekey_object.shape_keys.key_blocks
        fcurves = self.shapekey_object.shape_keys.animation_data.action.fcurves  # type: ignore

        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            weights = {}
            for index, flex_name in enumerate(map):
                if not shape_keys.get(flex_name):
                    weights[index] = 0.0
                    continue

                shape_key = shape_keys[flex_name]
                fc = fcurves.find(shape_key.path_from_id('value'))
                value = 0.0
                if fc:
                    value = fc.evaluate(frame)
                weights[index] = value

            data[str(frame)] = FlexFrame(weights=weights, scale=1.0).to_json()

        return data


class PhysBoneFrames(Frames):
    def to_json(self, map: BoneMap):
        data: dict[str, PhysBoneData] = {}

        physics_obj_tree = PhysBoneTree(self.armature, map)
        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            # Matrices with respect to world space
            matrix_map: dict[str, Matrix] = {}
            get_pose_matrices(self.armature, matrix_map, frame)
            data[str(frame)] = {}

            for phys_id, bone_name in enumerate(map):
                bone = self.armature.pose.bones.get(bone_name)
                if bone:
                    frame_obj = PhysBoneFrame(bone=bone)
                    parent = physics_obj_tree.get_parent(bone_name)
                    frame_obj.calculate(
                        matrix_map[bone_name], matrix_map.get(parent.name if parent else "", None))

                    data[str(frame)][str(phys_id)] = frame_obj.to_json()

        return data


class BoneFrames(Frames):
    def to_json(self, map: BoneMap):
        data: dict[str, BoneData] = {}
        if not self.armature.animation_data.action:
            return data

        fcurves = self.armature.animation_data.action.fcurves
        if not fcurves:
            return data

        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            data[str(frame)] = {}

            # Matrices with respect to rest pose
            for boneIndex, boneName in enumerate(map):
                bone = self.armature.pose.bones.get(boneName)
                if bone:
                    frame_obj = BoneFrame(bone=bone)
                    frame_obj.calculate(
                        fcurves=fcurves, frame=frame)
                    data[str(frame)][str(boneIndex)] = frame_obj.to_json()

        return data


class SMHFrameData():
    builder: SMHFrameBuilder
    data: SMHFrameResult
    armature: ArmatureObject
    position: int

    def __init__(self, type: SMHFileType, position: int, armature: ArmatureObject):
        self.builder = SMHFrameBuilder(position=position)
        self.type = type
        self.armature = armature
        self.position = position

    def bake_physbones(self, physbones):
        self.builder.add_data("physbones", physbones)
        if self.type == '3':
            self.builder.add_description('Modifier', "physbones")

    def bake_bones(self, bones):
        self.builder.add_data("bones", bones)
        if self.type == '3':
            self.builder.add_description('Modifier', "bones")

    def bake_modifiers(self, modifiers: dict):
        for name, data in modifiers.items():
            self.builder.add_data(name, data)
            if self.type == '3':
                self.builder.add_description('Modifier', name)

    def bake_flexes(self, flex):
        self.builder.add_data("flex", flex)
        if self.type == '3':
            self.builder.add_description('Modifier', "physbones")

    def build(self):
        self.data = self.builder.build(type=self.type)


def has_keyframe(fcurves: bpy.types.ActionFCurves, frame: float):
    for fcurve in fcurves:
        for keyframe in fcurve.keyframe_points:
            if keyframe.co[0] == frame:
                return True

    return False


class SMHExporter():
    frame_range: tuple[int, int, int]
    action: bpy.types.Action
    armature: ArmatureObject
    bone_frames: dict[str, dict[str, BoneData]]
    physbone_frames: dict[str, dict[str, PhysBoneData]]
    modifier_frames: dict[str, dict[str, ModifierData]]
    flex_frames: dict[str, dict[str, FlexData]] | None

    def __init__(self, action: bpy.types.Action, armature: ArmatureObject, frame_step: int, use_scene_range: bool):
        scene = bpy.context.scene
        self.frame_range = (
            floor(scene.frame_start if use_scene_range else action.frame_start),
            floor(scene.frame_end + 1 if use_scene_range else action.frame_end + 1),
            frame_step
        )
        self.armature = armature
        self.action = action

    def prepare_physics(self, physics_obj_map: BoneMap):
        self.physbone_frames = PhysBoneFrames(
            self.armature, self.frame_range).to_json(map=physics_obj_map)

    def prepare_bones(self, bone_map: BoneMap):
        self.bone_frames = BoneFrames(
            self.armature, self.frame_range).to_json(map=bone_map)

    def prepare_flexes(self, shapekey_object: bpy.types.Mesh, flex_map: BoneMap):
        self.flex_frames = FlexFrames(
            armature=self.armature,
            shapekey_object=shapekey_object,
            frame_range=self.frame_range).to_json(map=flex_map)

    def prepare_modifiers(self):
        self.modifier_frames = ModifierFrames(
            self.armature, self.frame_range).to_json()

    def export(self, data: SMHEntityResult, export_props: SMHExportProperties):
        """Iterate over the action or scene frame range and write pose and modifier data for the current action


        Args:
            data (SMHEntityResult): Data to write to
            export_props (SMHExportProperties): Configuration for exporting
        """

        frame_range = self.frame_range
        for frame in range(frame_range[0], frame_range[1], frame_range[2]):
            if export_props.keyframes_only and not has_keyframe(self.action.fcurves, frame):
                continue

            if export_props.smh_version == '3':
                physbone_frame = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                physbone_frame.bake_physbones(physbones=self.physbone_frames[str(frame)])
                physbone_frame.build()

                nonphysbone_frame = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                nonphysbone_frame.bake_bones(bones=self.bone_frames[str(frame)])
                nonphysbone_frame.build()

                data["Frames"].append(physbone_frame.data)
                data["Frames"].append(nonphysbone_frame.data)
            else:
                entity_frame = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                entity_frame.bake_physbones(physbones=self.physbone_frames[str(frame)])
                entity_frame.bake_bones(bones=self.bone_frames[str(frame)])
                entity_frame.bake_modifiers(modifiers=self.modifier_frames[str(frame)])
                # This will override the modifier data
                # TODO: Make it only override values that it has data for
                if self.flex_frames:
                    entity_frame.bake_flexes(flex=self.flex_frames[str(frame)])
                entity_frame.build()

                data["Frames"].append(entity_frame.data)
