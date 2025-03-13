import bpy

from typing import TypedDict, Union, List

ArmatureObject = Union[bpy.types.Armature, bpy.types.Object]
BoneMap = List[str]


class GenericBoneDict(TypedDict):
    Pos: str
    Ang: str


class BoneDict(GenericBoneDict):
    Scale: str | None


class PhysBoneDict(GenericBoneDict):
    LocalPos: str | None
    LocalAng: str | None
    Moveable: bool | None


class SMHEntityDataDict(TypedDict):
    bones: dict[str, BoneDict]
    physbones: dict[str, PhysBoneDict]


class SMHEntityFrameDict(TypedDict):
    EntityData: SMHEntityDataDict
    EaseOut: dict[str, float]
    EaseIn: dict[str, float]
    Position: int


class SMHPropertiesDict(TypedDict):
    Model: str
    Name: str
    Class: str


class SMHEntityDict(TypedDict):
    Frames: list[SMHEntityFrameDict]
    Properties: SMHPropertiesDict
    Model: str


class SMHFileDict(TypedDict):
    Map: str
    Entities: list[SMHEntityDict]
