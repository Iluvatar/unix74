from __future__ import annotations

import typing
from typing import Dict, List, NewType

from environment import Environment
from filesystem.filesystem import DirectoryData, FilePermissions, FileType, INode, Mode, RegularFileData
from filesystem.filesystem_loader import makeDev, makeRoot
from filesystem.filesystem_utils import DirEnt, Stat
from process.file_descriptor import BadFileNumberError, FD, FileMode, OFD, OpenFileDescriptor, PID, SeekFrom
from process.process import Process, ProcessFileDescriptor
from self_keyed_dict import SelfKeyedDict
from user import GID, Group, GroupName, GroupPassword, Password, UID, User, UserName


class KernelError(Exception):
    pass


UserId = NewType('UserId', int)
GroupId = NewType('GroupId', int)


class SystemHandle:
    def __init__(self, pid: PID, unix: Unix):
        self.__pid = pid
        self.__unix = unix

    def open(self, path: str, mode: FileMode) -> FD:
        return self.__unix.open(self.__pid, path, mode)

    def lseek(self, fd: FD, offset: int, whence: SeekFrom) -> int:
        return self.__unix.lseek(self.__pid, fd, offset, whence)

    def read(self, fd: FD, size: int) -> str:
        return self.__unix.read(self.__pid, fd, size)

    def write(self, fd: FD, data: str) -> int:
        return self.__unix.write(self.__pid, fd, data)

    def pipe(self) -> (FD, FD):
        return self.__unix.pipe(self.__pid)

    def stat(self, path: str) -> Stat:
        return self.__unix.stat(self.__pid, path)

    def getdents(self, fd: FD) -> List[DirEnt]:
        return self.__unix.getdents(self.__pid, fd)

    def chdir(self, path: str) -> None:
        return self.__unix.chdir(self.__pid, path)

    def chmod(self, path: str, permissions: FilePermissions) -> int:
        return self.__unix.chmod(self.__pid, path, permissions)

    def chown(self, path: str, owner: UID, group: GID) -> int:
        return self.__unix.chown(self.__pid, path, owner, group)

    def getdirentries(self, fd: FD) -> int:
        return self.__unix.getdirentries(self.__pid, fd)

    def gettimeofday(self, time: int) -> int:
        return self.__unix.gettimeofday(self.__pid, time)

    def link(self, target: str, alias: str) -> int:
        return self.__unix.link(self.__pid, target, alias)

    def mkdir(self, path: str, permissions: FilePermissions) -> int:
        return self.__unix.mkdir(self.__pid, path, permissions)

    def rename(self, path: str, to: str) -> int:
        return self.__unix.rename(self.__pid, path, to)

    def rmdir(self, path: str) -> int:
        return self.__unix.rmdir(self.__pid, path)

    def symlink(self, target: str, alias: str) -> int:
        return self.__unix.symlink(self.__pid, target, alias)


class Unix:
    def __init__(self):
        self.mounts: Dict[str, INode] = {}
        self.rootMount: INode | None = None
        self.rootUser: User = User(UserName("root"), Password(""), UID(0), GID(0), "root", "/", "/usr/sh")
        self.processes: SelfKeyedDict[Process, PID] = SelfKeyedDict("pid")
        self.openFileTable: SelfKeyedDict[OpenFileDescriptor, OFD] = SelfKeyedDict("id")
        self.nextPid: PID = PID(0)
        self.nextOftId: OFD = OFD(0)

        self.doStrace: bool = False

    def __str__(self):
        out = "Unix74\n------\n"

        out += f"mounts ({len(self.mounts)}):\n"
        for mount in self.mounts:
            out += f"    {mount}: {id(self.mounts[mount])}\n"
        out += f"root mount is {id(self.rootMount)}\n\n"

        out += f"processes ({len(self.processes)}):\n"
        for process in self.processes:
            out += f"    {process.pid}: {process}\n"
        out += "\n"

        out += f"open file table ({len(self.openFileTable)}):\n"
        for entry in self.openFileTable:
            out += f"    {entry}\n"

        return out

    def claimNextPid(self) -> PID:
        pid = self.nextPid
        self.nextPid += 1
        return pid

    def claimNextOftId(self) -> OFD:
        oftId = self.nextOftId
        self.nextOftId += 1
        return oftId

    # def makeProcess(self, parent: Process, code: Callable[Any, Any]):
    #     Process(self.claimNextPid(), parent, "", parent.owner, parent.env.copy(), code)

    def getUserById(self, uid: UID):
        return self.rootUser

    def getUserByName(self, name: UserName):
        return self.rootUser

    def getGroupById(self, gid: GID):
        return Group(GroupName("root"), GroupPassword("*"), GID(0), [UserName("root")])

    def getGroupByName(self, name: GroupName):
        return Group(GroupName("root"), GroupPassword("*"), GID(0), [UserName("root")])

    # TODO make permissions look at all groups
    def access(self, pid: PID, inode: INode, mode: Mode) -> bool:
        def checkModeSubset(m: Mode, inodeMode: Mode):
            if m not in inodeMode:
                raise PermissionError()
            else:
                return True

        process = self.processes[pid]
        if process.owner == UID(0):
            if Mode.EXEC in mode and Mode.EXEC not in (
                    inode.permissions.owner | inode.permissions.group | inode.permissions.other):
                raise PermissionError()
            return True
        if process.owner == inode.owner:
            return checkModeSubset(mode, inode.permissions.owner)
        if process.group == inode.group:
            return checkModeSubset(mode, inode.permissions.group)
        return checkModeSubset(mode, inode.permissions.other)

    def getINodeFromPath(self, pid: PID, path: str) -> INode:
        if not self.rootMount:
            raise KernelError("No root mount found")

        process = self.processes[pid]
        currentNode: INode = process.currentDir
        if path.startswith("/"):
            currentNode = self.rootMount

        parts = path.split("/")
        for part in parts:
            if currentNode.fileType != FileType.DIRECTORY:
                raise NotADirectoryError()
            self.access(pid, currentNode, Mode.EXEC)
            if part == "" or part == ".":
                continue

            try:
                currentNode = typing.cast(DirectoryData, currentNode.data).children[part]
            except KeyError:
                raise FileNotFoundError(part) from None

        return currentNode

    @staticmethod
    def strace(func):
        def inner(*args, **kwargs):
            self = args[0]
            if self.doStrace:
                name = func.__name__
                argString = ", ".join([repr(arg) for arg in args[2:]])
                print(f"strace >>> {name}({argString})", end="")

            ret = func(*args, **kwargs)

            if self.doStrace:
                print(f" -> {ret}")

            return ret

        return inner

    # System calls

    @strace
    def open(self, pid: PID, path: str, mode: FileMode) -> FD:
        process = self.processes[pid]
        inode = self.getINodeFromPath(pid, path)

        if FileMode.READ in mode:
            self.access(pid, inode, Mode.READ)
        if (FileMode.WRITE | FileMode.APPEND | FileMode.CREATE | FileMode.TRUNCATE) & mode:
            self.access(pid, inode, Mode.WRITE)
            mode |= FileMode.WRITE

        ofd = OpenFileDescriptor(self.claimNextOftId(), mode, inode)
        self.openFileTable.add(ofd)
        processFdNum = process.claimNextFdNum()
        process.fdTable.add(ProcessFileDescriptor(processFdNum, ofd))
        return processFdNum

    @strace
    def lseek(self, pid: PID, fd: FD, offset: int, whence: SeekFrom) -> int:
        process = self.processes[pid]
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if whence == SeekFrom.SET:
            ofdEntry.offset = offset
        elif whence == SeekFrom.CURRENT:
            ofdEntry.offset += offset
        elif whence == SeekFrom.END:
            endPos = ofdEntry.file.data.size()
            ofdEntry.offset = endPos + offset

        return ofdEntry.offset

    @strace
    def read(self, pid: PID, fd: FD, size: int) -> str:
        process = self.processes[pid]
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if FileMode.READ not in ofdEntry.mode:
            raise BadFileNumberError()

        data = ofdEntry.file.data.read(size, ofdEntry.offset)
        ofdEntry.offset += len(data)
        return data

    @strace
    def write(self, pid: PID, fd: FD, data: str) -> int:
        process = self.processes[pid]
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if FileMode.WRITE not in ofdEntry.mode:
            raise BadFileNumberError()

        numBytes = ofdEntry.file.data.write(data, ofdEntry.offset)
        ofdEntry.offset += numBytes
        return numBytes

    @strace
    def pipe(self, pid: PID) -> (FD, FD):
        pass

    @strace
    def stat(self, pid: PID, path: str) -> Stat:
        inode = self.getINodeFromPath(pid, path)
        return Stat(inode.permissions, inode.fileType, inode.owner, inode.group, inode.timeCreated, inode.timeModified,
                    inode.deviceNumber, inode.references)

    @strace
    def getdents(self, pid: PID, fd: FD) -> List[DirEnt]:
        process = self.processes[pid]
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd
        if ofdEntry.file.fileType != FileType.DIRECTORY:
            raise KernelError("Not a directory")
        out: List[DirEnt] = []
        for name, child in typing.cast(DirectoryData, ofdEntry.file.data).children.items():
            out.append(DirEnt(name, child))
        return out

    @strace
    def chdir(self, pid: PID, path: str) -> None:
        process = self.processes[pid]
        inode = self.getINodeFromPath(pid, path)
        if inode.fileType != FileType.DIRECTORY:
            raise NotADirectoryError()
        self.access(pid, inode, Mode.EXEC)
        process.currentDir = inode

    @strace
    def chmod(self, pid: PID, path: str, permissions: FilePermissions) -> int:
        pass

    @strace
    def chown(self, pid: PID, path: str, owner: int, group: int) -> int:
        pass

    @strace
    def getdirentries(self, pid: PID, fd: int) -> int:
        pass

    @strace
    def gettimeofday(self, pid: PID, time: int) -> int:
        pass

    @strace
    def link(self, pid: PID, target: str, alias: str) -> int:
        pass

    @strace
    def mkdir(self, pid: PID, path: str, permissions: FilePermissions) -> int:
        pass

    @strace
    def rename(self, pid: PID, froms: str, to: str) -> int:
        pass

    @strace
    def rmdir(self, pid: PID, path: str) -> int:
        pass

    @strace
    def symlink(self, pid: PID, target: str, alias: str) -> int:
        pass

    @staticmethod
    def getUsers(etcPasswd: RegularFileData):
        def parsePasswd(userString: str):
            fields = userString.split(":")
            try:
                name, password, uid, gid, info, home, shell = fields
                uid = UID(int(uid))
                gid = GID(int(gid))
            except ValueError:
                return None

            return User(name, password, uid, gid, info, home, shell)

        users: List[User] = []
        for line in etcPasswd.read():
            user = parsePasswd(line)
            if not user:
                continue
            users.append(user)
        return users

    def getRootMount(self) -> INode:
        try:
            return self.mounts["/"]
        except KeyError:
            raise KernelError("No root mount") from None

    def mount(self, path: str, directory: INode):
        if not path.startswith("/"):
            raise KernelError("Mount paths must be absolute")
        self.mounts[path] = directory

    def startup(self):
        # self.mount("/", makeRoot())
        # self.mount("/dev", makeDev())

        # try:
        #     etcPasswd = filesystem.getINodeFromRelativePath("/etc/passwd")
        # except INodeException:
        #     raise KernelError("Cannot find passwd file") from None

        # swapper = Process(0, None, "swapper", self.rootUser.uid, Environment())
        # swapper.parent = swapper
        # init = swapper.makeChild(1, "init")

        self.rootMount = makeRoot()
        devDir = makeDev()
        typing.cast(DirectoryData, devDir.data).addChild("..", self.rootMount)
        self.rootMount.references += 1
        typing.cast(DirectoryData, self.rootMount.data).addChild("dev", devDir)
        devDir.references += 1

        swapper = Process(self.claimNextPid(), None, "swapper", self.rootUser.uid, self.rootUser.gid, self.rootMount,
                          Environment())
        swapper.parent = swapper

        self.processes.add(swapper)

        shell = Process(self.claimNextPid(), swapper, "/usr/csh", UID(128), GID(128), self.rootMount, Environment())
        self.processes.add(shell)
