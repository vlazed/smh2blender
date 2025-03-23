from typing import TypedDict, Union

from .shared import SMHFileType


class GenericBoneData(TypedDict):
    Pos: str
    Ang: str


class BoneData(GenericBoneData):
    Scale: str | None


class PhysBoneData(GenericBoneData):
    LocalPos: str | None
    LocalAng: str | None
    Moveable: bool | None


class SMHEntityDataDict(TypedDict):
    bones: dict[str, BoneData]
    physbones: dict[str, PhysBoneData]


class SMHFrameBase(TypedDict):
    EntityData: SMHEntityDataDict
    Position: int


class SMHFrame2_0(SMHFrameBase):
    EaseIn: float
    EaseOut: float


class SMHFrame3_0(SMHFrameBase):
    EaseIn: float
    EaseOut: float
    Modifier: str


class SMHFrame4_0(SMHFrameBase):
    EaseOut: dict[str, float]
    EaseIn: dict[str, float]


SMHFrameResult = Union[SMHFrame2_0, SMHFrame3_0, SMHFrame4_0]


class SMHFrameBuilder:
    shared: dict

    def __init__(self, position: int):
        self.shared = {
            "EntityData": {},
            "Position": position,
        }

    def build(self, type: SMHFileType = '4'):
        if type == '2':
            data2: SMHFrame2_0 = self.shared
            data2["EntityData"] = {
                "bones": {},
                "physbones": {},
            }
            data2["EaseIn"] = data2["EaseOut"] = 0
            return data2
        elif type == '3':
            data3: SMHFrame3_0 = self.shared
            data3["EaseIn"] = data3["EaseOut"] = 0
            return data3
        else:
            data4: SMHFrame4_0 = self.shared
            data4["EntityData"] = {
                "bones": {},
                "physbones": {},
            }
            data4["EaseIn"] = data4["EaseOut"] = {
                "bones": 0.0,
                "physbones": 0.0
            }
            return data4
