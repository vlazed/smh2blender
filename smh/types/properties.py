from typing import TypedDict, Union, List, Literal

from .shared import SMHFileType


class SMHPropertiesBase(TypedDict):
    Model: str
    Class: str
    Name: str


class SMHProperties3_0(SMHPropertiesBase):
    Timelines: int
    TimelineMods: list[dict[str, str]]


class SMHProperties4_0(SMHPropertiesBase):
    pass


SMHPropertiesResult = Union[SMHProperties3_0, SMHProperties4_0]


class SMHPropertiesBuilder:
    shared: SMHPropertiesResult

    def __init__(self, model: str, name: str, cls: str):
        self.shared = {
            "Model": model,
            "Name": name,
            "Class": cls
        }

    def build(self, type: SMHFileType = '4') -> SMHPropertiesResult:
        if type == '3':
            data3: SMHProperties3_0 = self.shared
            data3['Timelines'] = 1
            data3['TimelineMods'] = [
                {
                    "bones": 1,
                    "physbones": 2,
                    "KeyColor": {
                        "r": 0,
                        "b": 0,
                        "a": 255,
                        "g": 200
                    }
                }
            ]
            return data3
        elif type == '4':
            data4: SMHProperties4_0 = self.shared
            return data4
        elif type == '2':
            return self.shared


SMHPropertiesResult = Union[SMHProperties3_0 | SMHProperties4_0]
