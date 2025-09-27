from bpy.types import Armature, Object, Camera
from typing import Union, List, Literal

SMHFileType = Union[Literal['2'], Literal['3'], Literal['4']]

ArmatureObject = Union[Armature, Object]
CameraObject = Union[Camera, Object]
BoneMap = List[str]
