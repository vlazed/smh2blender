import os
from typing import TypedDict, Union

from .shared import SMHFileType
from .frame import SMHFrame2_0, SMHFrame3_0, SMHFrame4_0
from .properties import SMHProperties3_0, SMHProperties4_0, SMHPropertiesBuilder
from ..props import SMHProperties


class SMHEntityBase(TypedDict):
    Model: str


class SMHEntity2_0(SMHEntityBase):
    Frames: list[SMHFrame2_0]


class SMHEntity3_0(SMHEntityBase):
    Frames: list[SMHFrame3_0]
    Properties: SMHProperties3_0


class SMHEntity4_0(SMHEntityBase):
    Frames: list[SMHFrame4_0]
    Properties: SMHProperties4_0


SMHEntityResult = Union[SMHEntity4_0 | SMHEntity3_0 | SMHEntity2_0]


class SMHEntityBuilder():
    shared: SMHEntityResult

    def __init__(self):
        self.shared = {
            "Frames": [],
            "Model": "",
        }

    def build(self, properties: SMHProperties, type: SMHFileType = '4'):
        props = SMHPropertiesBuilder(properties.model, properties.name, properties.cls).build(type=type)

        if type == '2':
            data2: SMHEntity2_0 = self.shared
            data2["Model"] = os.path.basename(properties.model)

            return data2
        elif type == '3':
            data3: SMHEntity3_0 = self.shared
            data3['Model'] = os.path.basename(properties.model)
            data3['Properties'] = props
            return data3
        else:
            data4: SMHEntity4_0 = self.shared
            data4['Model'] = os.path.basename(properties.model)
            data4['Properties'] = props
            return data4
