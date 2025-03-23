import bpy

from mathutils import Vector, Euler, Matrix
from typing import Generator
from math import radians

from .types.frame import GenericBoneData, PhysBoneData, BoneData
from .types.shared import ArmatureObject, BoneMap, SMHFileType
from .types.entity import SMHEntityResult
from .types.file import SMHFileResult

from .exporter import PhysBoneTree
from .props import SMHMetaData


class GenericBoneField:
    pos: Vector
    ang: Euler
    armature: ArmatureObject
    frame: float

    @staticmethod
    def get_matrix(pos: Vector, ang: Euler, scale: Vector = Vector((1, 1, 1, 1))):
        # Convert to pose space
        return Matrix.Translation(pos) @ (ang.to_matrix().to_4x4()) @ Matrix.Diagonal(scale)

    def __init__(self, armature: ArmatureObject, data: GenericBoneData, frame: float, angle_offset: Euler = Euler()):
        self.pos = self._transform_vec(data["Pos"], sign=(1, 1, 1))
        self.ang = self._transform_ang(data["Ang"], angle_offset=angle_offset)
        self.frame = frame
        self.armature = armature
        self.matrix = self.get_matrix(self.pos, self.ang)

    def add_pos(self, offset: Vector):
        self.pos += offset
        self.matrix = self.get_matrix(self.pos, self.ang)

    def _transform_vec(self, vec: str, sign=(1, 1, 1)) -> Vector:
        """Transform an SMH vector into a Blender `Vector` in local space

        Also switches y and z axes, as a bone's up axis is y.

        Args:
            vec (str): SMH vector

        Returns:
            Vector: Blender vector in local space
        """
        vec_list = [float(x) for x in vec[1:-1].split(" ")]
        return Vector((sign[0] * vec_list[0], sign[1] * vec_list[1], sign[2] * vec_list[2]))

    def _transform_ang(self, ang: str, angle_offset: Euler = Euler()) -> Euler:
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

    def __init__(self, armature: ArmatureObject, data: PhysBoneData, frame: float, angle_offset: Euler):
        super().__init__(armature=armature, data=data, frame=frame, angle_offset=angle_offset)
        self.local_pos = self.local_ang = self.local_matrix = None
        if data.get("LocalPos"):
            self.local_pos = self.__transform_local_vec(
                data["LocalPos"], sign=(1, 1, 1))
            self.local_ang = self.__transform_local_ang(data["LocalAng"])
            self.local_matrix = self.get_matrix(self.local_pos, self.local_ang)

    def __transform_local_ang(self, ang: str) -> Euler:
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

    def __transform_local_vec(self, vec: str, sign=(1, 1, 1)) -> Vector:
        """Transform an SMH local pos into a Blender angle in local space

        Args:
            vec (str): SMH local pos, with respect to its physics bone parent

        Returns:
            Vector: Blender vector in local space
        """

        # Switch back the y and z axes for the local vectors
        new_vec = self._transform_vec(vec, sign)
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

    def __init__(self, armature: ArmatureObject, frame: float, data: BoneData):
        super().__init__(armature=armature, frame=frame, data=data)
        self.ang = self.transform_manip_ang(data["Ang"])
        if data["Scale"]:
            self.scale = self._transform_vec(data["Scale"]).to_4d()
            self.scale[3] = 1
        self.matrix = self.get_matrix(self.pos, self.ang, self.scale)


class SMHImporter:
    physics_obj_map: BoneMap
    bone_map: BoneMap
    action: bpy.types.Action
    physics_tree: PhysBoneTree
    armature: ArmatureObject
    interpolation: list

    @staticmethod
    def load_physbones(entity: SMHEntityResult, armature: ArmatureObject, metadata: SMHMetaData | None = None):
        return [
            [
                PhysBoneField(
                    armature=armature, data=datum,
                    angle_offset=metadata.angle_offset() if metadata else Euler(),
                    frame=frame["Position"]
                ) for datum in frame["EntityData"]["physbones"].values()
            ]
            for frame in entity["Frames"] if dict(frame["EntityData"]).get("physbones")
        ]

    @staticmethod
    def load_bones(entity: SMHEntityResult, armature):
        return [
            [
                BoneField(
                    armature=armature,
                    data=datum,
                    frame=frame["Position"]
                ) for datum in frame["EntityData"]["bones"].values()
            ]
            for frame in entity["Frames"] if dict(frame["EntityData"]).get("bones")
        ]

    @staticmethod
    def load_entity(data: SMHFileResult, name: str, type: SMHFileType = '4'):
        if type == '2':
            return next((
                entity for entity in data.get("Entities")
                if entity["Model"] == name), None
            )
        elif type == '3' or type == '4':
            return next((
                entity for entity in data.get("Entities")
                if entity.get("Properties") and entity["Properties"].get("Name", "") == name), None  # type: ignore
            )

    def create_fc(
        self,
        index: float,
        frames: list[int],
        samples: Generator[float, None, None],
        data_path: str,
        group_name: str
    ):
        num_frames = len(frames)
        interpolation = [
            bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value] * num_frames
        fc: bpy.types.FCurve = self.action.fcurves.new(
            data_path=data_path, index=index, action_group=group_name)
        fc.keyframe_points.add(num_frames)
        fc.keyframe_points.foreach_set(
            "co", [x for co in zip(frames, samples) for x in co])
        fc.keyframe_points.foreach_set(
            "interpolation", interpolation)
        fc.update()

    def __init__(
            self,
            physics_obj_map: BoneMap,
            bone_map: BoneMap,
            armature: ArmatureObject,
            action: bpy.types.Action,
            entity: SMHEntityResult):
        self.physics_obj_map = physics_obj_map
        self.bone_map = bone_map
        self.action = action

        self.armature = armature
        self.physics_tree = PhysBoneTree(armature, physics_obj_map)

        frames = [
            frame["Position"] for frame in entity["Frames"] if len(frame["EntityData"]) > 0
        ]

        action.frame_start = min(frames)
        action.frame_end = max(frames)

        bpy.context.scene.frame_start = int(action.frame_start)
        bpy.context.scene.frame_end = int(action.frame_end)

    @staticmethod
    def get_pose(
        data: list[list[PhysBoneField | BoneField]], index: int,
        bone: bpy.types.PoseBone, local_condition: bool = False
    ):
        matrices: list[Matrix] = None
        if local_condition:
            matrices = [row[index].local_matrix for row in data]
        else:
            matrices = [row[index].matrix for row in data]

        frames = [row[index].frame for row in data]

        pos = [
            (matrix.translation.x for matrix in matrices),
            (matrix.translation.y for matrix in matrices),
            (matrix.translation.z for matrix in matrices)
        ]

        ang = [
            (matrix.to_quaternion().w for matrix in matrices),
            (matrix.to_quaternion().x for matrix in matrices),
            (matrix.to_quaternion().y for matrix in matrices),
            (matrix.to_quaternion().z for matrix in matrices),
        ] if bone.rotation_mode == 'QUATERNION' else [
            (matrix.to_euler().x for matrix in matrices),
            (matrix.to_euler().y for matrix in matrices),
            (matrix.to_euler().z for matrix in matrices),
        ]

        return pos, ang, frames

    def fcurves_from_data(
        self,
        pos: list[Generator[float, None, None]],
        ang: list[Generator[float, None, None]],
        frames: list[float],
        name: str,
        bone: bpy.types.PoseBone,
        location_condition: bool = True,
        rotation_condition: bool = True
    ):
        if location_condition:
            data_path = bone.path_from_id('location')
            [self.create_fc(
                index=index, samples=samples, data_path=data_path,
                group_name=name, frames=frames) for index, samples in enumerate(pos)]

        if rotation_condition:
            data_path = bone.path_from_id(
                'rotation_quaternion'
                if bone.rotation_mode == 'QUATERNION' else 'rotation_euler'
            )
            [self.create_fc(
                index=index, samples=samples, data_path=data_path,
                group_name=name, frames=frames) for index, samples in enumerate(ang) if samples is not None]

    def import_physics(self, physbone_data: list[list[PhysBoneField]], metadata: SMHMetaData):
        # Stop Motion Helper reports the root physics object location as an offset from the ground (about 38 units)
        # Without this adjustment, the armature will be offset from the ground
        offset = self.physics_tree.get_bone_from_index(
            0).bone.matrix_local.translation
        offset = Vector((offset[0], offset[1], offset[2]))
        [
            [
                physbone.add_pos(-offset)
                for physbone_index, physbone in enumerate(physbone_row)
                if physbone_index == 0
            ]
            for physbone_row in physbone_data
        ]

        for index, phys_name in enumerate(self.physics_obj_map):
            bone = self.armature.pose.bones.get(phys_name)
            if not bone:
                continue

            pos, ang, frames = self.get_pose(
                data=physbone_data,
                index=index,
                bone=bone,
                local_condition=self.physics_tree.get_parent(phys_name) is not None
            )

            if self.physics_tree.get_parent(phys_name) is None:
                bone.bone.use_local_location = False

            self.fcurves_from_data(
                pos,
                ang,
                frames,
                name=phys_name,
                bone=bone,
                location_condition=metadata.import_stretch or self.physics_tree.get_parent(phys_name) is None
            )

    def import_bones(self, bone_data: list[list[BoneField]]):
        for index, bone_name in enumerate(self.bone_map):
            bone = self.armature.pose.bones.get(bone_name)
            if not bone or self.physics_tree.bone_dict.get(bone_name) is not None:
                continue

            pos, ang, frames = self.get_pose(
                data=bone_data,
                index=index,
                bone=bone,
            )

            self.fcurves_from_data(
                pos,
                ang,
                frames,
                name=bone_name,
                bone=bone,
            )
