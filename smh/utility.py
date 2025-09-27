import bpy


def version_has_slots():
    version = bpy.app.version
    return version[0] >= 4 and version[1] >= 4
