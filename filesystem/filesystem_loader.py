from __future__ import annotations

import typing
from collections import defaultdict
from datetime import datetime
from typing import DefaultDict

from filesystem.dev_files import DevConsole, DevNull
from filesystem.filesystem import DirectoryData, FilePermissions, FileType, INode, INodeData, Mode, RegularFileData
from user import GID, UID

origTime = datetime(1974, 10, 17, 10, 14, 27, 387)

users: DefaultDict[str, UID] = defaultdict(lambda: UID(512), {
    "root": UID(0),
    "liz": UID(128),
    "murtaugh": UID(129),
})

groups: DefaultDict[str, GID] = defaultdict(lambda: GID(512), {
    "root": GID(0),
    "liz": GID(128),
    "murtaugh": GID(129),
})


def loadFile(path: str) -> RegularFileData:
    with open(path) as f:
        data = f.read()
    return RegularFileData(data)


def makeChild(parent: INode, name: str, filetype: FileType, data: INodeData, *,
              permissions: FilePermissions | None = None, owner: UID | None = None, group: GID | None = None,
              timeCreated: datetime | None = None, timeModified: datetime | None = None):
    if permissions is None:
        permissions = parent.permissions.copy()
    if owner is None:
        owner = parent.owner
    if group is None:
        group = parent.group
    if timeCreated is None:
        timeCreated = parent.timeCreated
    if timeModified is None:
        timeModified = timeCreated

    child = INode(permissions, filetype, owner, group, timeCreated, timeModified, data)
    typing.cast(DirectoryData, parent.data).addChild(name, child)
    return child


def makeChildDir(parent: INode, name: str, *, permissions: FilePermissions | None = None, owner: UID | None = None,
                 group: GID | None = None, timeCreated: datetime | None = None,
                 timeModified: datetime | None = None) -> INode:
    child = makeChild(parent, name, FileType.DIRECTORY, DirectoryData(), permissions=permissions, owner=owner,
                      group=group, timeCreated=timeCreated, timeModified=timeModified)
    typing.cast(DirectoryData, child.data).addChildren({
        ".": child,
        "..": parent
    })
    child.references = 2
    parent.references += 1
    return child


def makeChildFile(parent: INode, name: str, data: INodeData, *, permissions: FilePermissions | None = None,
                  owner: UID | None = None, group: GID | None = None, filetype: FileType | None = None,
                  timeCreated: datetime | None = None, timeModified: datetime | None = None) -> INode:
    if filetype == FileType.DIRECTORY:
        raise ValueError("use makeChildDir() for directories")
    elif filetype is None:
        filetype = FileType.REGULAR

    if permissions is None:
        permissions = parent.permissions.copy()
        permissions.modifyPermissions(FilePermissions.Entity.OWNER, FilePermissions.Op.REM, Mode.EXEC)
        permissions.modifyPermissions(FilePermissions.Entity.GROUP, FilePermissions.Op.REM, Mode.EXEC)
        permissions.modifyPermissions(FilePermissions.Entity.OTHER, FilePermissions.Op.REM, Mode.EXEC)

    return makeChild(parent, name, filetype, data, permissions=permissions, owner=owner, group=group,
                     timeCreated=timeCreated, timeModified=timeModified)


def makeEtc(root: INode) -> INode:
    etcDir = makeChildDir(root, "etc")

    makeChildFile(etcDir, "passwd", loadFile("root/etc/passwd"), permissions=FilePermissions(644))
    makeChildFile(etcDir, "group", loadFile("root/etc/group"), permissions=FilePermissions(644))

    return etcDir


def makeRoot():
    root = INode(FilePermissions(755), FileType.DIRECTORY, users["root"], groups["root"], origTime, origTime,
                 DirectoryData())
    typing.cast(DirectoryData, root.data).addChildren({
        ".": root,
        "..": root
    })
    root.references = 2

    binDir = makeChildDir(root, "bin")
    etcDir = typing.cast(DirectoryData, root.data).addChild("etc", makeEtc(root))
    usrDir = makeChildDir(root, "usr")
    varDir = makeChildDir(root, "var")

    lizCreatedTime = datetime(1974, 12, 2, 1, 24, 13, 989)
    lizHomeDir = makeChildDir(usrDir, "liz", owner=users["liz"], group=groups["liz"], timeCreated=lizCreatedTime)
    makeChildFile(lizHomeDir, "note.txt", loadFile("root/usr/liz/note.txt"))

    murtaughCreatedTime = datetime(1974, 12, 18, 19, 1, 37, 182)
    murtaughHomeDir = makeChildDir(usrDir, "murtaugh", owner=users["murtaugh"], group=groups["murtaugh"],
                                   timeCreated=murtaughCreatedTime)
    makeChildFile(murtaughHomeDir, "cat.txt", loadFile("root/usr/murtaugh/cat.txt"),
                  timeCreated=datetime(1975, 10, 14, 10, 58, 45, 619))
    makeChildFile(murtaughHomeDir, "liz.txt", loadFile("root/usr/murtaugh/liz.txt"),
                  timeCreated=datetime(1976, 3, 26, 17, 12, 42, 107))
    makeChildFile(murtaughHomeDir, "myself.txt", loadFile("root/usr/murtaugh/myself.txt"),
                  timeCreated=datetime(1976, 12, 13, 12, 51, 9, 588))
    makeChildFile(murtaughHomeDir, "diary1.txt", loadFile("root/usr/murtaugh/diary1.txt"),
                  timeCreated=datetime(1977, 1, 8, 9, 2, 54, 184))
    makeChildFile(murtaughHomeDir, "diary2.txt", loadFile("root/usr/murtaugh/diary2.txt"),
                  timeCreated=datetime(1977, 1, 8, 9, 2, 54, 184))
    makeChildFile(murtaughHomeDir, "portal.txt", loadFile("root/usr/murtaugh/portal.txt"),
                  timeCreated=datetime(1977, 1, 8, 18, 17, 22, 374))

    return root


def makeDev():
    devDir = INode(FilePermissions(755), FileType.DIRECTORY, users["root"], groups["root"], origTime, origTime,
                   DirectoryData())
    typing.cast(DirectoryData, devDir.data).addChild(".", devDir)

    makeChildFile(devDir, "null", DevNull(), filetype=FileType.CHARACTER, permissions=FilePermissions(666))
    makeChildFile(devDir, "console", DevConsole(), filetype=FileType.CHARACTER, permissions=FilePermissions(666))

    return devDir
