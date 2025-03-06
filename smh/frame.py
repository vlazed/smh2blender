from bpy.types import Bone, PoseBone, ActionFCurves, Armature, Object
from math import degrees, radians
from mathutils import Vector, Euler, Matrix, Quaternion
from abc import abstractmethod
from typing import List

ORDER = 'XYZ'
BoneMap = List[str]


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
    quat = Euler((0, 0, 0), ORDER)
    temp_quat = Euler((0, 0, 0), ORDER)
    for i in range(3):
        fc = fcurves.find(data_path, index=i)
        if fc is None:
            break
        temp_quat[i] = fc.evaluate(frame)
    else:
        quat = temp_quat
    rot = quat.to_matrix().to_4x4()

    return trans @ rot @ scale


def get_pose_matrices(obj: Object, matrix_map: dict[str, Matrix], frame: int):
    """https://blender.stackexchange.com/questions/302699/calculate-a-pose-bones-transformation-matrix-from-its-f-curve-without-updating

    Assign pose space matrices of all bones at once, ignoring constraints.

    # Args:
        obj (Object)
        matrix_map (dict[str, Matrix])
        frame (int)
    """

    fcurves = obj.animation_data.action.fcurves

    def rec(pbone: PoseBone | Bone):

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
    bone_dict: dict[int]

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

    def get_parent(self, phys_name: str) -> PoseBone | None:
        if self.bone_dict.get(phys_name) and self.bones[self.bone_dict[phys_name]]:
            return self.bones[self.bone_dict[phys_name]].parent

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
    def vec_to_str(vec: Vector):
        return f"[{vec.x} {vec.y} {vec.z}]"

    @staticmethod
    def ang_to_str(ang: Euler):
        """
            FIXME: This implicitly switches the angle order, which I think is a workaround to getting the correct angles (although the order is right-handed here)
            Is there a "legit" method? This seems prone to errors.
        """
        return f"{{{degrees(ang.y)} {degrees(ang.z)} {degrees(ang.x)}}}"

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

    def to_json(self):
        return {
            "Pos": self.vec_to_str(self.pos),
            "Ang": self.ang_to_str(self.ang),
            "Scale": self.vec_to_str(self.scale),
        }


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

    def to_json(self):
        data = {
            "Moveable": False,
            "Pos": self.vec_to_str(self.pos),
            "Ang": self.ang_to_str(self.ang),
        }
        if self.local_pos:
            data["LocalPos"] = self.vec_to_str(self.local_pos)
            data["LocalAng"] = self.ang_to_str(self.local_ang)

        return data


class Frames:
    armature: Armature | Object
    frame_range: tuple[int, int]

    def __init__(self, armature: Armature | Object, frame_range: tuple[int, int]):
        self.armature = armature
        self.frame_range = frame_range

    @abstractmethod
    def to_json(self): pass


class PhysBoneFrames(Frames):
    def to_json(self, physics_obj_map: BoneMap):
        data = {}

        physics_obj_tree = PhysBoneTree(self.armature, physics_obj_map)
        for i in range(self.frame_range[0], self.frame_range[1]):
            # Matrices with respect to world space
            matrix_map: dict[str, Matrix] = {}
            get_pose_matrices(self.armature, matrix_map, i)
            data[str(i)] = {}

            for phys_id, bone_name in enumerate(physics_obj_map):
                bone = self.armature.pose.bones.get(bone_name)
                if bone:
                    frame = PhysBoneFrame(bone=bone)
                    parent = physics_obj_tree.get_parent(bone_name)
                    frame.calculate(
                        matrix_map[bone_name], matrix_map.get(parent.name if parent else "", None))

                    data[str(i)][str(phys_id)] = frame.to_json()

        return data


class BoneFrames(Frames):
    def to_json(self, bone_map: BoneMap):
        data = {}
        for i in range(self.frame_range[0], self.frame_range[1]):
            data[str(i)] = {}

            # Matrices with respect to rest pose
            for boneIndex, boneName in enumerate(bone_map):
                bone = self.armature.pose.bones.get(boneName)
                frame = BoneFrame(bone=bone)
                if bone:
                    frame.calculate(
                        fcurves=self.armature.animation_data.action.fcurves, frame=i)
                data[str(i)][str(boneIndex)] = frame.to_json()

        return data
