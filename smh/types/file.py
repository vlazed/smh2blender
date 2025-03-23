from typing import TypedDict, Union

from .shared import SMHFileType
from .entity import SMHEntity2_0, SMHEntity3_0, SMHEntity4_0


class SMHFileBase(TypedDict):
    Map: str


class SMHFile2_0(SMHFileBase):
    Entities: list[SMHEntity2_0]


class SMHFile3_0(SMHFileBase):
    Entities: list[SMHEntity3_0]


class SMHFile4_0(SMHFileBase):
    Entities: list[SMHEntity4_0]


SMHFileResult = Union[SMHFile4_0 | SMHFile3_0 | SMHFile2_0]
SMHPropFile = Union[SMHFile4_0 | SMHFile3_0]


class SMHFileBuilder():
    shared: SMHFileResult

    def __init__(self, map: str):
        self.shared = {
            "Map": map,
            "Entities": []
        }

    def build(self, type: SMHFileType = '4'):
        if type == '2':
            data2: SMHFile2_0 = self.shared
            return data2
        elif type == '3':
            data3: SMHFile3_0 = self.shared
            return data3
        else:
            data4: SMHFile4_0 = self.shared
            return data4
