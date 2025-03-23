from mathutils import Vector, Euler, Matrix

from math import radians

from .types import GenericBoneDict, PhysBoneDict, BoneDict, ArmatureObject


class GenericBoneField:
    pos: Vector
    ang: Euler
    armature: ArmatureObject
    frame: float

    @staticmethod
    def get_matrix(pos: Vector, ang: Euler, scale: Vector = Vector((1, 1, 1, 1))):
        # Convert to pose space
        return Matrix.Translation(pos) @ (ang.to_matrix().to_4x4()) @ Matrix.Diagonal(scale)

    def __init__(self, armature: ArmatureObject, data: GenericBoneDict, frame: float, angle_offset: Euler = Euler()):
        self.pos = self.transform_vec(data["Pos"], sign=(1, 1, 1))
        self.ang = self.transform_ang(data["Ang"], angle_offset=angle_offset)
        self.frame = frame
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
        return Vector((sign[0] * vec_list[0], sign[1] * vec_list[1], sign[2] * vec_list[2]))

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
    local_pos: Vector | None
    local_ang: Euler | None
    local_matrix: Matrix | None

    def __init__(self, armature: ArmatureObject, data: PhysBoneDict, frame: float, angle_offset: Euler):
        super().__init__(armature=armature, data=data, frame=frame, angle_offset=angle_offset)
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

    def transform_local_vec(self, vec: str, sign=(1, 1, 1)) -> Vector:
        """Transform an SMH local pos into a Blender angle in local space

        Args:
            vec (str): SMH local pos, with respect to its physics bone parent

        Returns:
            Vector: Blender vector in local space
        """

        # Switch back the y and z axes for the local vectors
        new_vec = self.transform_vec(vec, sign)
        return Vector((new_vec[0], new_vec[1], new_vec[2]))

    def set_ref_offset(self, refphysbone, is_root: bool):
        """Use the reference mapped physics bone to correct the local angle

        Args:
            refphysbone (PhysBoneField): Reference physics bone
        """

        if is_root:
            self.ang = (refphysbone.ang.to_matrix().transposed()
                        @ self.ang.to_matrix()).to_euler()
            self.matrix = self.get_matrix(self.pos, self.ang)

        if self.local_pos and self.local_ang:
            self.local_pos = (
                refphysbone.local_matrix.inverted()
                @ self.local_matrix).translation
            self.local_ang = (refphysbone.local_ang.to_matrix(
            ).transposed() @ self.local_ang.to_matrix()).to_euler()
            self.local_matrix = self.get_matrix(self.local_pos, self.local_ang)


class BoneField(GenericBoneField):
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

    def __init__(self, armature: ArmatureObject, frame: float, data: BoneDict):
        super().__init__(armature=armature, frame=frame, data=data)
        self.ang = self.transform_manip_ang(data["Ang"])
        if data["Scale"]:
            self.scale = self.transform_vec(data["Scale"]).to_4d()
            self.scale[3] = 1
        self.matrix = self.get_matrix(self.pos, self.ang, self.scale)
