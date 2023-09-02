from __future__ import annotations

import typing
from collections import defaultdict
from datetime import datetime
from typing import DefaultDict
from uuid import uuid4

from filesystem.dev_files import DevConsole, DevNull, Mem
from filesystem.filesystem import DirectoryData, FilePermissions, FileType, Filesystem, INode, INodeData, INumber, Mode, \
    RegularFileData, SetId
from user import GID, UID

if typing.TYPE_CHECKING:
    from kernel.unix import Unix

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


def makeChild(fs: Filesystem, parentINum: INumber, name: str, filetype: FileType, data: INodeData, *,
              permissions: FilePermissions | None = None, owner: UID | None = None, group: GID | None = None,
              timeCreated: datetime | None = None, timeModified: datetime | None = None) -> INumber:
    parent = fs.inodes[parentINum]
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

    child = fs.add(
        INode(fs.claimNextINumber(), permissions, filetype, owner, group, timeCreated, timeModified, data, fs.uuid))
    typing.cast(DirectoryData, parent.data).addChild(name, child.iNumber)
    return child.iNumber


def makeChildDir(fs: Filesystem, parentINum: INumber, name: str, *, permissions: FilePermissions | None = None,
                 owner: UID | None = None, group: GID | None = None, timeCreated: datetime | None = None,
                 timeModified: datetime | None = None) -> INumber:
    parent = fs.inodes[parentINum]
    childINum = makeChild(fs, parentINum, name, FileType.DIRECTORY, DirectoryData(), permissions=permissions,
                          owner=owner, group=group, timeCreated=timeCreated, timeModified=timeModified)
    child = fs.inodes[childINum]
    typing.cast(DirectoryData, child.data).addChildren({
        ".": childINum,
        "..": parentINum,
    })
    child.references = 2
    parent.references += 1
    return childINum


def makeChildFile(fs: Filesystem, parentINum: INumber, name: str, data: INodeData, *,
                  permissions: FilePermissions | None = None, owner: UID | None = None, group: GID | None = None,
                  filetype: FileType | None = None, timeCreated: datetime | None = None,
                  timeModified: datetime | None = None) -> INumber:
    parent = fs.inodes[parentINum]
    if filetype == FileType.DIRECTORY:
        raise ValueError("use makeChildDir() for directories")
    elif filetype is None:
        filetype = FileType.REGULAR

    if permissions is None:
        permissions = parent.permissions.copy()
        permissions.modifyPermissions(FilePermissions.PermGroup.HIGH, FilePermissions.Op.REM, SetId.ALL)
        permissions.modifyPermissions(FilePermissions.PermGroup.OWNER, FilePermissions.Op.REM, Mode.EXEC)
        permissions.modifyPermissions(FilePermissions.PermGroup.GROUP, FilePermissions.Op.REM, Mode.EXEC)
        permissions.modifyPermissions(FilePermissions.PermGroup.OTHER, FilePermissions.Op.REM, Mode.EXEC)

    return makeChild(fs, parentINum, name, filetype, data, permissions=permissions, owner=owner, group=group,
                     timeCreated=timeCreated, timeModified=timeModified)


def makeEtc(fs: Filesystem, rootINum: INumber) -> INumber:
    etcDirINum = makeChildDir(fs, rootINum, "etc")

    makeChildFile(fs, etcDirINum, "passwd", loadFile("root/etc/passwd"), permissions=FilePermissions(0o644))
    makeChildFile(fs, etcDirINum, "group", loadFile("root/etc/group"), permissions=FilePermissions(0o644))

    return etcDirINum


def makeLizHome(fs: Filesystem, usrDirINum: INumber) -> None:
    lizCreatedTime = datetime(1974, 12, 2, 1, 24, 13, 989)
    lizHomeDirINum = makeChildDir(fs, usrDirINum, "liz", owner=users["liz"], group=groups["liz"],
                                  timeCreated=lizCreatedTime)
    makeChildFile(fs, lizHomeDirINum, "note.txt", loadFile("root/usr/liz/note.txt"))


def makeMurtaughHome(fs: Filesystem, usrDirINum: INumber) -> None:
    murtaughCreatedTime = datetime(1974, 12, 18, 19, 1, 37, 182)
    murtaughHomeDirINum = makeChildDir(fs, usrDirINum, "murtaugh", owner=users["murtaugh"], group=groups["murtaugh"],
                                       timeCreated=murtaughCreatedTime)
    makeChildFile(fs, murtaughHomeDirINum, "cat.txt", loadFile("root/usr/murtaugh/cat.txt"),
                  timeCreated=datetime(1975, 10, 14, 10, 58, 45, 619))
    makeChildFile(fs, murtaughHomeDirINum, "liz.txt", loadFile("root/usr/murtaugh/liz.txt"),
                  timeCreated=datetime(1976, 3, 26, 17, 12, 42, 107))
    makeChildFile(fs, murtaughHomeDirINum, "myself.txt", loadFile("root/usr/murtaugh/myself.txt"),
                  timeCreated=datetime(1976, 12, 13, 12, 51, 9, 588))
    makeChildFile(fs, murtaughHomeDirINum, "diary1.txt", loadFile("root/usr/murtaugh/diary1.txt"),
                  timeCreated=datetime(1977, 1, 8, 9, 2, 54, 184))
    makeChildFile(fs, murtaughHomeDirINum, "diary2.txt", loadFile("root/usr/murtaugh/diary2.txt"),
                  timeCreated=datetime(1977, 1, 8, 9, 2, 54, 184))
    makeChildFile(fs, murtaughHomeDirINum, "portal.txt", loadFile("root/usr/murtaugh/portal.txt"),
                  timeCreated=datetime(1977, 1, 8, 18, 17, 22, 374))


def makeRoot() -> Filesystem:
    fs = Filesystem(uuid4())

    root = fs.add(
        INode(fs.claimNextINumber(), FilePermissions(0o755), FileType.DIRECTORY, users["root"], groups["root"],
              origTime, origTime, DirectoryData(), fs.uuid))
    typing.cast(DirectoryData, root.data).addChildren({
        ".": root.iNumber,
        "..": root.iNumber,
    })
    root.references = 2

    binDir = makeChildDir(fs, root.iNumber, "bin")
    devDir = makeChildDir(fs, root.iNumber, "dev")
    etcDir = typing.cast(DirectoryData, root.data).addChild("etc", makeEtc(fs, root.iNumber))
    tmpDir = makeChildDir(fs, root.iNumber, "tmp", permissions=FilePermissions(0o1777))
    usrDir = makeChildDir(fs, root.iNumber, "usr")
    varDir = makeChildDir(fs, root.iNumber, "var")

    makeLizHome(fs, usrDir)
    makeMurtaughHome(fs, usrDir)

    return fs


def makeDev(unix: Unix) -> Filesystem:
    fs = Filesystem(uuid4())

    devDir = fs.add(
        INode(fs.claimNextINumber(), FilePermissions(0o755), FileType.DIRECTORY, users["root"], groups["root"],
              origTime, origTime, DirectoryData(), fs.uuid))
    typing.cast(DirectoryData, devDir.data).addChild(".", devDir.iNumber)

    makeChildFile(fs, devDir.iNumber, "null", DevNull(unix), filetype=FileType.CHARACTER,
                  permissions=FilePermissions(0o666))
    makeChildFile(fs, devDir.iNumber, "console", DevConsole(unix), filetype=FileType.CHARACTER,
                  permissions=FilePermissions(0o666))
    makeChildFile(fs, devDir.iNumber, "mem", Mem(unix), filetype=FileType.CHARACTER, permissions=FilePermissions(0o666))

    return fs
