import bpy

from bpy.types import Bone, PoseBone, ActionFCurves, Armature, Object, Camera
from math import degrees, radians, floor, atan
from mathutils import Vector, Euler, Matrix, Quaternion
from abc import abstractmethod
from typing import List

from .types.frame import BoneData, PhysBoneData, ModifierData, FlexData, SMHFrameResult, SMHFrameBuilder, CameraData
from .types.shared import BoneMap, ArmatureObject, SMHFileType, CameraObject
from .types.entity import SMHEntityResult

from .props import SMHExportProperties
from .modifiers import classes as modifiers, translations as mod_map
from .utility import version_has_slots


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


def get_camera_pose_matrices(obj: Object, matrix_map: dict[str, Matrix], frame: int):
    """https://blender.stackexchange.com/questions/302699/calculate-a-pose-bones-transformation-matrix-from-its-f-curve-without-updating

    Assign pose space matrices of the camera.

    # Args:
        obj (Object): Armature or any object with an action
        matrix_map (dict[str, Matrix]): Bone to matrix mapping
        frame (int): Frame
    """

    if not obj.animation_data.action:
        return

    fcurves = obj.animation_data.action.fcurves

    matrix_map['static_prop'] = get_matrix_basis_from_fcurve(obj, fcurves, frame)


class FrameEvaluator:
    matrix_map: dict[str, Matrix]

    def set_frame(self, frame: float):
        pass

    def reset_frame(self):
        pass

    def build_camera_matrix_map(self, obj: Object, frame: float):
        pass

    def build_matrix_map(self, obj: Object, frame: float):
        pass

    def get_pose_matrix(self, obj: Object, frame: float, bone_name: str) -> Matrix | None:
        raise NotImplementedError()

    def get_bone_matrix(self, obj: Object, frame: float, bone: Bone) -> Matrix | None:
        raise NotImplementedError()

    def get_camera_matrix(self, obj: Object, frame: float) -> Matrix | None:
        raise NotImplementedError()

    def get_camera_focal_length(self, obj: CameraObject, frame: float) -> float:
        raise NotImplementedError()

    def get_shapekey_value(self, obj: bpy.types.Mesh, frame: float, shapekey_name: str) -> float:
        raise NotImplementedError()


class FCurveEvaluator(FrameEvaluator):
    matrix_map: dict[str, Matrix]

    def build_matrix_map(self, obj: Object, frame: float):
        self.matrix_map = {}
        get_pose_matrices(obj, self.matrix_map, frame)

    def build_camera_matrix_map(self, obj: Object, frame: float):
        get_camera_pose_matrices(obj, self.matrix_map, frame)

    def get_bone_matrix(self, obj: Object, frame: float, bone: Bone) -> Matrix | None:
        return get_matrix_basis_from_fcurve(bone, obj.animation_data.action.fcurves, frame)

    def get_pose_matrix(self, obj, frame, bone_name):
        return self.matrix_map.get(bone_name)

    def get_camera_matrix(self, obj, frame):
        return self.matrix_map.get('static_prop')

    def get_camera_focal_length(self, obj: CameraObject, frame: float) -> float | None:
        fc = None
        # Check for keyframe data for the currently active action slot
        if version_has_slots() and len(obj.data.animation_data.action.layers) > 0:
            fc = obj.data.animation_data.action.layers[0].strips[0].channelbag(
                obj.data.animation_data.action_slot).fcurves.find('lens')
        # Use imported data if it doesn't exist
        if not fc:
            fc = obj.animation_data.action.fcurves.find('data.lens')

        if fc:
            return fc.evaluate(frame)

        return 50.0

    def get_shapekey_value(self, obj: bpy.types.Mesh, frame, shapekey_name):
        if not obj.shape_keys:
            return 0.0

        shape_key = obj.shape_keys.key_blocks.get(shapekey_name)
        if not shape_key:
            return 0.0

        fc = obj.shape_keys.animation_data.action.fcurves.find(shape_key.path_from_id('value'))
        if fc:
            return fc.evaluate(frame)

        return 0.0


class VisualKeyingEvaluator(FrameEvaluator):
    def __init__(self, frame: float):
        self.initial_frame = frame

    def set_frame(self, frame: float):
        bpy.context.scene.frame_set(frame)

    def reset_frame(self):
        bpy.context.scene.frame_set(self.initial_frame)

    def get_camera_matrix(self, obj, frame):
        return obj.matrix_world

    def get_pose_matrix(self, obj, frame, bone_name):
        pbone = obj.pose.bones.get(bone_name)
        return pbone.matrix if pbone else None

    def get_bone_matrix(self, obj, frame, bone: Bone):
        pbone = obj.pose.bones.get(bone.name)
        return pbone.matrix_basis if pbone else None

    def get_camera_focal_length(self, obj, frame):
        return obj.data.lens

    def get_shapekey_value(self, obj: bpy.types.Mesh, frame, shapekey_name):
        if not obj.shape_keys:
            return 0.0

        shape_key = obj.shape_keys.key_blocks.get(shapekey_name)
        if not shape_key:
            return 0.0

        return shape_key.value


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

        if armature.type != 'ARMATURE':
            return

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
        self.scale = Vector((1, 1, 1))

    # manip_matrix is in local space
    def calculate(self, matrix: Matrix):
        rest_matrix = self.bone.matrix_basis

        self.pos = matrix.translation - rest_matrix.translation
        self.scale = matrix.to_scale()

        rest_matrix.to_3x3().rotate(matrix.to_euler(ORDER))
        self.ang = matrix.to_euler(ORDER)

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


class CameraFrame(Frame):
    camera: CameraObject
    fov: float

    def __init__(self, camera):
        self.camera = camera

    # Matrices are defined in pose space
    def calculate(self, matrix: Matrix):
        self.pos = matrix.translation
        self.ang = matrix.to_euler(ORDER)

    def calculate2(self, focal_length: float):
        # Exporting animatable focal length from fcurves is only available after Blender 4.4
        self.fov = degrees(2 * atan(self.camera.data.sensor_width * 0.5 / focal_length))

    def to_json(self) -> PhysBoneData:
        x_rot = Euler((radians(-90), 0, 0)).to_matrix()
        z_rot = Euler((0, 0, radians(90))).to_matrix()
        ang = self.ang.to_matrix() @ x_rot @ z_rot
        data: PhysBoneData = {
            "Moveable": False,
            "Pos": self.vec_to_str(self.pos, sign=(1, 1, 1)),
            "Ang": self.ang_to_str(ang.to_euler()),
        }

        return data

    def to_json2(self, other_data: CameraData | None) -> CameraData:
        data: CameraData = {
            "FOV": self.fov,
            "Nearz": 0,
            "Farz": 0,
            "Roll": 0,
            "Offset": self.vec_to_str(Vector(), sign=(1, 1, 1)),
        }
        if other_data:
            data["Roll"] = other_data["Roll"]
            data["Farz"] = other_data["Farz"]
            data["Nearz"] = other_data["Nearz"]
            data["Offset"] = other_data["Offset"]

        return data


class Frames:
    armature: Armature | Object
    frame_range: tuple[int, int, int]

    def __init__(self, armature: Armature | Object, frame_range: tuple[int, int]):
        self.armature = armature
        self.frame_range = frame_range

    @abstractmethod
    def to_json(self, map: BoneMap | None, physics_map: BoneMap | None): pass


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
                            value = get_modifier_frame_value(
                                data_path=data_path, obj=self.armature, frame=frame)
                            data[str(frame)][mod_name][prop.identifier] = value

                if type(data[str(frame)][mod_name]) == dict and len(data[str(frame)][mod_name]) == 0:
                    # No keyframes exists for the current modifier? Don't use it
                    del data[str(frame)][mod_name]

        return data


class FlexFrames(Frames):
    shapekey_object: bpy.types.Mesh

    def __init__(self, armature: Armature | Object, frame_range: list[float], shapekey_object: bpy.types.Mesh):
        super().__init__(armature, frame_range)
        self.shapekey_object = shapekey_object

    def to_json(self, map: BoneMap, evaluator: FrameEvaluator):
        data: FlexData = {}

        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            evaluator.set_frame(frame)
            weights = {}
            for index, flex_name in enumerate(map):
                weights[index] = evaluator.get_shapekey_value(self.shapekey_object, frame, flex_name)

            data[str(frame)] = FlexFrame(weights=weights, scale=1.0).to_json()

        return data


class PhysBoneFrames(Frames):
    def to_json(self, map: BoneMap, evaluator: FrameEvaluator):
        data: dict[str, PhysBoneData] = {}

        physics_obj_tree = PhysBoneTree(self.armature, map)
        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            evaluator.set_frame(frame)

            # Matrices with respect to world space
            evaluator.build_matrix_map(self.armature, frame)
            data[str(frame)] = {}

            for phys_id, bone_name in enumerate(map):
                bone = self.armature.pose.bones.get(bone_name)
                if bone:
                    frame_obj = PhysBoneFrame(bone=bone)
                    parent = physics_obj_tree.get_parent(bone_name)
                    matrix = evaluator.get_pose_matrix(self.armature, frame, bone_name)
                    parent_matrix = None
                    if parent:
                        parent_matrix = evaluator.get_pose_matrix(self.armature, frame, parent.name)
                    frame_obj.calculate(matrix, parent_matrix)

                    data[str(frame)][str(phys_id)] = frame_obj.to_json()

        return data


class CameraFrames(Frames):
    def to_json(self, map: BoneMap, evaluator: FrameEvaluator):
        data: dict[str, PhysBoneData] = {}

        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            evaluator.set_frame(frame)
            evaluator.build_camera_matrix_map(self.armature, frame)
            data[str(frame)] = {}

            for phys_id, bone_name in enumerate(map):
                frame_obj = CameraFrame(camera=self.armature)
                frame_obj.calculate(evaluator.get_camera_matrix(self.armature, frame))

                data[str(frame)][str(phys_id)] = frame_obj.to_json()

        return data

    def to_json2(self, modifier_frames: dict[str, dict[str, CameraData]], evaluator: FrameEvaluator):
        data: dict[str, CameraData] = {}
        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            evaluator.set_frame(frame)

            frame_str = str(frame)
            data[frame_str] = {}
            cam_data = None
            if modifier_frames and modifier_frames.get(frame_str) and modifier_frames[frame_str].get("advcamera"):
                cam_data = modifier_frames[frame_str]["advcamera"]

            frame_obj = CameraFrame(camera=self.armature)
            frame_obj.calculate2(evaluator.get_camera_focal_length(self.armature, frame))
            data[frame_str] = frame_obj.to_json2(cam_data)

        return data


class BoneFrames(Frames):
    def to_json(
            self,
            map: BoneMap,
            physics_map: BoneMap,
            angle_offset: Euler,
            pos_offset: Vector,
            evaluator: FrameEvaluator):
        data: dict[str, BoneData] = {}
        if not self.armature.animation_data.action:
            return data

        physics_set = set(physics_map)

        for frame in range(self.frame_range[0], self.frame_range[1], self.frame_range[2]):
            evaluator.set_frame(frame)

            data[str(frame)] = {}

            # Matrices with respect to rest pose
            for bone_index, bone_name in enumerate(map):
                bone = self.armature.pose.bones.get(bone_name)
                # Prevent "doubling" on the physics movement
                if bone:
                    frame_obj = BoneFrame(bone=bone)
                    if bone_name not in physics_set:
                        frame_obj.calculate(evaluator.get_bone_matrix(self.armature, frame, bone))
                    # Check for root physics bones: physics bones without parents
                    if bone_name in physics_set and bone.parent is None:
                        # Angles are rearranged in to_json() function, so we have to rearrange them here
                        frame_obj.ang = Euler((angle_offset.z, angle_offset.x, angle_offset.y))
                        frame_obj.pos = pos_offset
                    data[str(frame)][str(bone_index)] = frame_obj.to_json()

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
            self.builder.add_description('Modifier', "flex")

    def bake_camera(self, camera):
        self.builder.add_data("advcamera", camera)
        if self.type == '3':
            self.builder.add_description('Modifier', "advcamera")

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
    bone_frames: dict[str, dict[str, BoneData]] | None
    physbone_frames: dict[str, dict[str, PhysBoneData]] | None
    modifier_frames: dict[str, dict[str, ModifierData]] | None
    flex_frames: dict[str, dict[str, FlexData]] | None
    camera_frames: dict[str, dict[str, CameraData]] | None
    evaluator: FrameEvaluator

    def __init__(
            self,
            action: bpy.types.Action,
            armature: ArmatureObject,
            frame_step: int,
            use_scene_range: bool,
            evaluator: FrameEvaluator):
        scene = bpy.context.scene
        self.frame_range = (
            floor(scene.frame_start if use_scene_range else action.frame_start),
            floor(scene.frame_end + 1 if use_scene_range else action.frame_end + 1),
            frame_step
        )
        self.armature = armature
        self.action = action
        self.evaluator = evaluator

        self.physbone_frames = None
        self.bone_frames = None
        self.modifier_frames = None
        self.flex_frames = None
        self.camera_frames = None

    def prepare_camera(self, physics_obj_map: BoneMap):
        camera_frames = CameraFrames(self.armature, self.frame_range)
        self.physbone_frames = camera_frames.to_json(map=physics_obj_map, evaluator=self.evaluator)
        self.camera_frames = camera_frames.to_json2(self.modifier_frames, evaluator=self.evaluator)

    def prepare_physics(self, physics_obj_map: BoneMap):
        self.physbone_frames = PhysBoneFrames(
            self.armature, self.frame_range).to_json(map=physics_obj_map, evaluator=self.evaluator)

    def prepare_bones(
            self,
            bone_map: BoneMap,
            physics_obj_map: BoneMap,
            angle_offset: Euler = Euler(),
            pos_offset: Vector = Vector()):
        self.bone_frames = BoneFrames(
            self.armature,
            self.frame_range
        ).to_json(
            map=bone_map,
            physics_map=physics_obj_map,
            angle_offset=angle_offset,
            pos_offset=pos_offset,
            evaluator=self.evaluator
        )

    def prepare_flexes(self, shapekey_object: bpy.types.Mesh, flex_map: BoneMap):
        self.flex_frames = FlexFrames(
            armature=self.armature,
            shapekey_object=shapekey_object,
            frame_range=self.frame_range).to_json(map=flex_map, evaluator=self.evaluator)

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
                if self.physbone_frames:
                    physbone_frame = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                    physbone_frame.bake_physbones(physbones=self.physbone_frames[str(frame)])
                    physbone_frame.build()
                    data["Frames"].append(physbone_frame.data)

                if self.bone_frames:
                    nonphysbone_frame = SMHFrameData(
                        type=export_props.smh_version, armature=self.armature, position=frame)
                    nonphysbone_frame.bake_bones(bones=self.bone_frames[str(frame)])
                    nonphysbone_frame.build()
                    data["Frames"].append(nonphysbone_frame.data)

            else:
                entity_frame = SMHFrameData(type=export_props.smh_version, armature=self.armature, position=frame)
                if self.physbone_frames:
                    entity_frame.bake_physbones(physbones=self.physbone_frames[str(frame)])
                if self.bone_frames:
                    entity_frame.bake_bones(bones=self.bone_frames[str(frame)])
                if self.modifier_frames:
                    entity_frame.bake_modifiers(modifiers=self.modifier_frames[str(frame)])
                if self.camera_frames:
                    entity_frame.bake_camera(camera=self.camera_frames[str(frame)])
                # This will override the modifier data
                # TODO: Make it only override values that it has data for
                if self.flex_frames:
                    entity_frame.bake_flexes(flex=self.flex_frames[str(frame)])
                entity_frame.build()

                data["Frames"].append(entity_frame.data)
