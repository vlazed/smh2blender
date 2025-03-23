from bpy.types import Armature, Object
from typing import Union, List, Literal

SMHFileType = Union[Literal['2'], Literal['3'], Literal['4']]

ArmatureObject = Union[Armature, Object]
BoneMap = List[str]
