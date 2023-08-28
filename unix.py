from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, NewType, Type, cast

from environment import Environment
from filesystem.filesystem import DirectoryData, FilePermissions, FileType, INode, INodeData, Mode, RegularFileData
from filesystem.filesystem_loader import makeDev, makeRoot
from filesystem.filesystem_utils import DirEnt, INodeOperation, Stat
from libc import Libc
from process.file_descriptor import BadFileNumberError, FD, FileMode, OFD, OpenFileDescriptor, PID, SeekFrom
from process.process import Process, ProcessFileDescriptor
from process.process_code import ProcessCode
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

    def close(self, fd: FD) -> int:
        return self.__unix.close(self.__pid, fd)

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

    def gettimeofday(self, time: int) -> int:
        return self.__unix.gettimeofday(self.__pid, time)

    def link(self, target: str, alias: str) -> None:
        return self.__unix.link(self.__pid, target, alias)

    def unlink(self, target: str) -> None:
        return self.__unix.unlink(self.__pid, target)

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

        self.doStrace: bool = False

    def __str__(self):
        out = "Unix74\n------\n"

        out += f"mounts ({len(self.mounts)}):\n"
        for mount in self.mounts:
            out += f"    {mount}: {self.mounts[mount].inumber}\n"
        out += f"root mount is {self.rootMount.inumber}\n\n"

        out += f"processes ({len(self.processes)}):\n"
        for process in self.processes:
            out += f"    {process.pid}: {process}\n"
        out += "\n"

        out += f"open file table ({len(self.openFileTable)}):\n"
        for entry in self.openFileTable:
            out += f"    {entry}\n"

        return out

    @staticmethod
    def strace(func):
        def stringify(arg: Any) -> str:
            if isinstance(arg, INode):
                arg = cast(INode, arg)
                return f"INode[{arg.inumber}, perm={arg.permissions}, type={arg.fileType}, {arg.owner}:{arg.group}]"
            elif isinstance(arg, Stat):
                arg = cast(Stat, arg)
                return f"Stat[{arg.inode.inumber}]"
            else:
                return repr(arg)

        def inner(*args, **kwargs):
            self = args[0]
            if self.doStrace:
                name = func.__name__
                argString = ", ".join([stringify(arg) for arg in args[2:]])
                print(f"strace >>> {name}({argString})", end="")

            ret = func(*args, **kwargs)

            if self.doStrace:
                print(f" -> {stringify(ret)}")

            return ret

        return inner

    def claimNextPid(self) -> PID:
        pid = self.nextPid
        self.nextPid += 1
        return pid

    def claimNextOftId(self) -> OFD:
        nextOfd: OFD = OFD(0)
        while nextOfd in self.openFileTable:
            nextOfd += 1
        return nextOfd

    # def makeProcess(self, parent: Process, code: Callable[Any, Any]):
    #     Process(self.claimNextPid(), parent, "", parent.owner, parent.env.copy(), code)

    def getProcess(self, pid: PID):
        try:
            return self.processes[pid]
        except KeyError:
            raise KernelError(f"No such process {pid}") from None

    def isSuperUser(self, uid: UID):
        return uid == UID(0)

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
                raise PermissionError(f"Mode requested {m}, actual is {inodeMode}")
            else:
                return True

        process = self.getProcess(pid)
        if self.isSuperUser(process.owner):
            if Mode.EXEC in mode and Mode.EXEC not in (
                    inode.permissions.owner | inode.permissions.group | inode.permissions.other):
                raise PermissionError()
            return True
        if process.owner == inode.owner:
            return checkModeSubset(mode, inode.permissions.owner)
        if process.group == inode.group:
            return checkModeSubset(mode, inode.permissions.group)
        return checkModeSubset(mode, inode.permissions.other)

    def traversePath(self, pid: PID, path: str, op: INodeOperation) -> INode:
        if not self.rootMount:
            raise KernelError("No root mount found")

        process = self.getProcess(pid)
        currentNode: INode = process.currentDir
        if path.startswith("/"):
            currentNode = self.rootMount

        parts = path.rstrip("/").split("/")
        traversePath = parts
        if op == INodeOperation.CREATE or op == INodeOperation.DELETE:
            traversePath = parts[:-1]
        for part in traversePath:
            if currentNode.fileType != FileType.DIRECTORY:
                raise NotADirectoryError()
            self.access(pid, currentNode, Mode.EXEC)
            if part == "":
                part = "."

            try:
                currentNode = cast(DirectoryData, currentNode.data).children[part]
            except KeyError:
                raise FileNotFoundError(part) from None

        if op == INodeOperation.GET or op == INodeOperation.DELETE:
            return currentNode
        elif op == INodeOperation.CREATE:
            try:
                return cast(DirectoryData, currentNode.data).children[parts[-1]]
            except KeyError:
                pass

            self.access(pid, currentNode, Mode.WRITE)
            child = INode(currentNode.permissions, FileType.NONE, process.owner, process.group, datetime.now(),
                          datetime.now(), INodeData())
            cast(DirectoryData, currentNode.data).addChild(parts[-1], child)
        else:
            raise NotImplementedError()

    def getINodeFromPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.GET)

    def createINodeAtPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.CREATE)

    def getINodeParentFromPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.DELETE)

    # System calls

    @strace
    def fork(self, pid: PID, child: Type[ProcessCode], argv: List[str]) -> PID:
        process = self.getProcess(pid)
        childPid = self.claimNextPid()
        system = SystemHandle(childPid, self)
        libc = Libc(system)
        childProcess = child(system, libc, argv)
        # t = Thread(target=child.run, )

        return PID(0)

    @strace
    def open(self, pid: PID, path: str, mode: FileMode) -> FD:
        process = self.getProcess(pid)
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
        process = self.getProcess(pid)
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
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if FileMode.READ not in ofdEntry.mode:
            raise BadFileNumberError()

        data = ofdEntry.file.data.read(size, ofdEntry.offset)
        ofdEntry.offset += len(data)
        return data

    @strace
    def write(self, pid: PID, fd: FD, data: str) -> int:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if FileMode.WRITE not in ofdEntry.mode:
            raise BadFileNumberError()

        numBytes = ofdEntry.file.data.write(data, ofdEntry.offset)
        ofdEntry.offset += numBytes
        return numBytes

    @strace
    def close(self, pid: PID, fd: FD) -> int:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        ofdEntry.refCount -= 1
        if ofdEntry.refCount == 0:
            self.openFileTable.remove(ofdEntry.id)

        process.fdTable.remove(fd)

        return 0

    @strace
    def pipe(self, pid: PID) -> (FD, FD):
        pass

    @strace
    def stat(self, pid: PID, path: str) -> Stat:
        inode = self.getINodeFromPath(pid, path)
        return Stat(inode, inode.permissions, inode.fileType, inode.owner, inode.group, inode.timeCreated,
                    inode.timeModified, inode.deviceNumber, inode.references)

    @strace
    def getdents(self, pid: PID, fd: FD) -> List[DirEnt]:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd
        if ofdEntry.file.fileType != FileType.DIRECTORY:
            raise KernelError("Not a directory")
        out: List[DirEnt] = []
        for name, child in cast(DirectoryData, ofdEntry.file.data).children.items():
            out.append(DirEnt(name, child))
        return out

    @strace
    def chdir(self, pid: PID, path: str) -> None:
        process = self.getProcess(pid)
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
    def setuid(self, pid: PID, uid: UID) -> int:
        pass

    @strace
    def setgid(self, pid: PID, gid: GID) -> int:
        pass

    @strace
    def gettimeofday(self, pid: PID, time: int) -> int:
        pass

    @strace
    def link(self, pid: PID, target: str, alias: str) -> None:
        process = self.getProcess(pid)
        targetInode = self.getINodeFromPath(pid, target)

        if targetInode.fileType == FileType.DIRECTORY or alias.endswith("/"):
            if not (targetInode.fileType == FileType.DIRECTORY and self.isSuperUser(process.owner)):
                raise KernelError("Cannot hard link directories")
            alias = alias.rstrip("/")

        # cannot overwrite an existing file
        try:
            self.getINodeFromPath(pid, alias)
            raise FileExistsError()
        except FileNotFoundError:
            pass

        aliasParts = alias.split("/")
        aliasFile = aliasParts[-1]
        aliasParent = "/".join(aliasParts[:-1])

        aliasParentInode = self.getINodeFromPath(pid, aliasParent)
        self.access(pid, aliasParentInode, Mode.WRITE)
        cast(DirectoryData, aliasParentInode.data).addChild(aliasFile, targetInode)
        targetInode.references += 1

    @strace
    def unlink(self, pid: PID, target: str) -> None:
        process = self.getProcess(pid)
        parentInode = self.getINodeParentFromPath(pid, target)
        childInode = self.getINodeFromPath(pid, target)

        self.access(pid, parentInode, Mode.WRITE)
        if childInode.fileType == FileType.DIRECTORY and not self.isSuperUser(process.owner):
            raise KernelError("Cannot unlink directories")

        childName: str = ""
        for name, child in cast(DirectoryData, parentInode.data).children.items():
            if child.inumber == childInode.inumber:
                childName = name
                break
        else:
            raise KernelError("Could not find child in parent")

        cast(DirectoryData, parentInode.data).removeChild(childName)
        childInode.references -= 1

        # TODO remove debugging
        if childInode.references == 0:
            print("Removing file", childName)

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
        cast(DirectoryData, devDir.data).addChild("..", self.rootMount)
        self.rootMount.references += 1
        cast(DirectoryData, self.rootMount.data).addChild("dev", devDir)
        devDir.references += 1

        swapper = Process(self.claimNextPid(), None, "swapper", self.rootUser.uid, self.rootUser.gid, self.rootMount,
                          Environment())
        swapper.parent = swapper

        self.processes.add(swapper)

        shell = Process(self.claimNextPid(), swapper, "/usr/csh", UID(128), GID(128), self.rootMount, Environment())
        self.processes.add(shell)
