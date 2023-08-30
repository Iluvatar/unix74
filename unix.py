from __future__ import annotations

import select
from datetime import datetime
from enum import Enum, auto
from multiprocessing import Pipe
from multiprocessing.connection import Connection
from time import sleep
from typing import Any, Dict, List, NewType, Tuple, Type, TypeVar, cast

from environment import Environment
from filesystem.filesystem import DirectoryData, FilePermissions, FileType, Filesystem, INode, INodeData, Mode
from filesystem.filesystem_loader import makeRoot
from filesystem.filesystem_utils import DirEnt, INodeOperation, Stat
from libc import Libc
from process.file_descriptor import FD, FileMode, OFD, OpenFileDescriptor, PID, SeekFrom
from process.process import OsProcess, ProcessEntry, ProcessFileDescriptor, ProcessStatus
from process.process_code import ProcessCode
from self_keyed_dict import SelfKeyedDict
from user import GID, Group, GroupName, GroupPassword, Password, UID, User, UserName
from usr.sh import Sh

T = TypeVar("T")


class Errno(Enum):
    NONE = 0
    PERMISSION = auto()
    NO_ACCESS = auto()
    NO_SUCH_FILE = auto()
    IS_A_DIR = auto()
    NOT_A_DIR = auto()
    INVALID_ARG = auto()
    FUNC_NOT_IMPLEMENTED = auto()
    BAD_PID = auto()
    NOT_A_CHILD = auto()


class KernelError(Exception):
    def __init__(self, message: str, errno: Errno):
        super(KernelError, self).__init__(message)
        self.errno = errno


UserId = NewType('UserId', int)
GroupId = NewType('GroupId', int)


class SystemHandle:
    def __init__(self, pid: PID, pipe: Connection):
        self.pid = pid
        self.pipe = pipe

    def __syscall(self, name: str, *args):
        self.pipe.send((name, self.pid, *args))
        ret = self.pipe.recv()
        if ret[0] != Errno.NONE:
            raise ValueError(f"{ret[0]}: {repr(ret[1])}")
        return ret[1]

    def debug(self) -> None:
        return self.__syscall("debug")

    def printProcess(self, pid: PID) -> None:
        return self.__syscall("printProcess", pid)

    def printProcesses(self) -> None:
        return self.__syscall("printProcesses")

    def fork(self, child: Type[ProcessCode], command: str, argv: List[str]) -> PID:
        return self.__syscall("fork", child, command, argv)

    def open(self, path: str, mode: FileMode) -> FD:
        return self.__syscall("open", path, mode)

    def read(self, fd: FD, size: int) -> str:
        return self.__syscall("read", fd, size)

    def write(self, fd: FD, data: str) -> int:
        return self.__syscall("write", fd, data)

    def stat(self, path: str) -> Stat:
        return self.__syscall("stat", path)

    def getdents(self, fd: FD) -> List[DirEnt]:
        return self.__syscall("getdents", fd)

    def waitpid(self, pid: PID) -> Tuple[PID, int]:
        return self.__syscall("waitpid", pid)

    def exit(self, exitCode: int) -> None:
        return self.__syscall("exit", exitCode)


class Unix:
    def __init__(self):
        self.mounts: Dict[str, Filesystem] = {}
        self.rootMount: INode | None = None
        self.rootUser: User = User(UserName("root"), Password(""), UID(0), GID(0), "root", "/", "/usr/sh")
        self.processes: SelfKeyedDict[ProcessEntry, PID] = SelfKeyedDict("pid")
        self.openFileTable: SelfKeyedDict[OpenFileDescriptor, OFD] = SelfKeyedDict("id")
        self.nextPid: PID = PID(0)

        self.pipes: List[Connection] = []

        self.doStrace: bool = False

    def __str__(self):
        out = "Unix74\n------\n"

        out += f"mounts ({len(self.mounts)}):\n"
        for mount in self.mounts:
            out += f"    {mount}: {len(self.mounts[mount])}\n"
        out += f"root mount is {self.rootMount.iNumber}\n\n"

        out += f"processes ({len(self.processes)}):\n"
        for process in self.processes:
            out += f"    {process.pid}: {process}\n"
        out += "\n"

        out += f"open file table ({len(self.openFileTable)}):\n"
        for entry in self.openFileTable:
            out += f"    {entry}\n"

        return out

    def sendSyscallReturn(self, pipe: Connection, errno: Errno, value) -> None:
        pipe.send((errno, value))

    def syscallReturnSuccess(self, pid: PID, value: T) -> T:
        process = self.getProcess(pid)
        self.sendSyscallReturn(process.pipe, Errno.NONE, value)
        return value

    def debug(self, pid: PID):
        print(self)
        self.syscallReturnSuccess(pid, None)

    def printProcess(self, pid: PID, processPid: PID):
        print(self.processes[processPid])
        self.syscallReturnSuccess(pid, None)

    def printProcesses(self, pid: PID):
        for process in self.processes:
            print(process)
        self.syscallReturnSuccess(pid, None)

    def start(self):
        syscallDict = {
            "debug": self.debug,
            "printProcess": self.printProcess,
            "printProcesses": self.printProcesses,

            "fork": self.fork,
            "open": self.open,
            "read": self.read,
            "write": self.write,
            "getdents": self.getdents,
            "stat": self.stat,
            "waitpid": self.waitpid,
            "exit": self.exit,
        }

        while True:
            ready, _, _ = select.select(self.pipes, [], [], 1)
            for pipe in ready:
                try:
                    data: Tuple[str, PID, ...] = pipe.recv()
                except EOFError:
                    continue
                syscall: str = data[0]
                pid: PID = data[1]
                args: Tuple[Any] = data[2:]

                try:
                    if syscall in syscallDict:
                        syscallDict[syscall](pid, *args)
                    else:
                        self.sendSyscallReturn(pipe, Errno.FUNC_NOT_IMPLEMENTED, f"Invalid syscall {syscall}")
                except TypeError as e:
                    self.sendSyscallReturn(pipe, Errno.INVALID_ARG, repr(e))
                except KernelError as e:
                    self.sendSyscallReturn(pipe, e.errno, str(e))

    @staticmethod
    def strace(func):
        def stringify(arg: Any) -> str:
            if isinstance(arg, INode):
                arg = cast(INode, arg)
                return f"INode[{arg.iNumber}, perm={arg.permissions}, type={arg.fileType}, {arg.owner}:{arg.group}]"
            elif isinstance(arg, Stat):
                arg = cast(Stat, arg)
                return f"Stat[{arg.iNumber}]"
            elif isinstance(arg, str):
                maxLen = 50
                if len(arg) > maxLen:
                    return f'"{arg[:maxLen - 3]}..."'
                return repr(arg)
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

    def getProcess(self, pid: PID):
        try:
            return self.processes[pid]
        except KeyError:
            raise KernelError(f"No such process {pid}", Errno.BAD_PID) from None

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
                raise KernelError(f"Mode requested {m}, actual is {inodeMode}", Errno.NO_ACCESS)
            else:
                return True

        process = self.getProcess(pid)
        if self.isSuperUser(process.uid):
            if Mode.EXEC in mode and Mode.EXEC not in (
                    inode.permissions.owner | inode.permissions.group | inode.permissions.other):
                raise KernelError("", Errno.NO_ACCESS)
            return True
        if process.uid == inode.owner:
            return checkModeSubset(mode, inode.permissions.owner)
        if process.gid == inode.group:
            return checkModeSubset(mode, inode.permissions.group)
        return checkModeSubset(mode, inode.permissions.other)

    def traversePath(self, pid: PID, path: str, op: INodeOperation) -> INode:
        if not (fs := self.mounts["/"]):
            raise KernelError("No root mount found", Errno.NO_SUCH_FILE)

        process = self.getProcess(pid)
        currentNode: INode = fs.inodes[process.currentDir]
        if path.startswith("/"):
            currentNode = fs.root()

        parts = path.rstrip("/").split("/")
        traversePath = parts
        if op == INodeOperation.CREATE or op == INodeOperation.DELETE:
            traversePath = parts[:-1]
        for part in traversePath:
            if currentNode.fileType != FileType.DIRECTORY:
                raise KernelError(f"No such file ro directory: {path}", Errno.NO_SUCH_FILE)
            self.access(pid, currentNode, Mode.EXEC)
            if part == "":
                part = "."

            try:
                currentNode = fs.inodes[cast(DirectoryData, currentNode.data).children[part]]
            except KeyError:
                raise KernelError(f"No such file ro directory: {path}", Errno.NO_SUCH_FILE)

        if op == INodeOperation.GET or op == INodeOperation.DELETE:
            return currentNode
        elif op == INodeOperation.CREATE:
            try:
                return fs.inodes[cast(DirectoryData, currentNode.data).children[parts[-1]]]
            except KeyError:
                pass

            self.access(pid, currentNode, Mode.WRITE)
            child = INode(fs.claimNextINumber(), currentNode.permissions, FileType.NONE, process.uid, process.gid,
                          datetime.now(), datetime.now(), INodeData())
            cast(DirectoryData, currentNode.data).addChild(parts[-1], child.iNumber)
        else:
            raise KernelError(f"Invalid op: {op}", Errno.FUNC_NOT_IMPLEMENTED)

    def getINodeFromPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.GET)

    def createINodeAtPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.CREATE)

    def getINodeParentFromPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.DELETE)

    # System calls

    @strace
    def fork(self, pid: PID, child: Type[ProcessCode], command: str, argv: List[str]) -> PID:
        process = self.getProcess(pid)
        childPid = self.claimNextPid()
        userPipe, kernelPipe = Pipe()
        self.pipes.append(kernelPipe)
        childProcessEntry = ProcessEntry(childPid, pid, command, process.realUid, process.realGid, process.currentDir,
                                         process.env, pipe=kernelPipe)
        self.processes.add(childProcessEntry)

        system = SystemHandle(childPid, userPipe)
        libc = Libc(system)
        childProcess = OsProcess(child(system, libc, argv), childProcessEntry)
        childProcess.run()
        childProcessEntry.pythonPid = childProcess.process.pid

        return self.syscallReturnSuccess(pid, childPid)

    @strace
    def open(self, pid: PID, path: str, mode: FileMode) -> FD:
        process = self.getProcess(pid)
        try:
            inode = self.getINodeFromPath(pid, path)
        except FileNotFoundError:
            raise KernelError(f"No such file or directory: {path}", Errno.NO_SUCH_FILE)

        if FileMode.READ in mode:
            self.access(pid, inode, Mode.READ)
        if (FileMode.WRITE | FileMode.APPEND | FileMode.CREATE | FileMode.TRUNCATE) & mode:
            self.access(pid, inode, Mode.WRITE)
            mode |= FileMode.WRITE

        ofd = OpenFileDescriptor(self.claimNextOftId(), mode, inode)
        self.openFileTable.add(ofd)
        processFdNum: FD = process.claimNextFdNum()
        process.fdTable.add(ProcessFileDescriptor(processFdNum, ofd))

        return self.syscallReturnSuccess(pid, processFdNum)

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

        return self.syscallReturnSuccess(pid, ofdEntry.offset)

    @strace
    def read(self, pid: PID, fd: FD, size: int) -> str:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if FileMode.READ not in ofdEntry.mode:
            raise KernelError("", Errno.NO_ACCESS)

        data = ofdEntry.file.data.read(size, ofdEntry.offset)
        ofdEntry.offset += len(data)

        return self.syscallReturnSuccess(pid, data)

    @strace
    def write(self, pid: PID, fd: FD, data: str) -> int:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if FileMode.WRITE not in ofdEntry.mode:
            raise KernelError("", Errno.NO_ACCESS)

        numBytes = ofdEntry.file.data.write(data, ofdEntry.offset)
        ofdEntry.offset += numBytes

        return self.syscallReturnSuccess(pid, numBytes)

    @strace
    def close(self, pid: PID, fd: FD) -> None:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        ofdEntry.refCount -= 1
        if ofdEntry.refCount == 0:
            self.openFileTable.remove(ofdEntry.id)

        process.fdTable.remove(fd)

    @strace
    def pipe(self, pid: PID) -> (FD, FD):
        pass

    @strace
    def stat(self, pid: PID, path: str) -> Stat:
        inode = self.getINodeFromPath(pid, path)
        stat = Stat(inode.iNumber, inode.permissions, inode.fileType, inode.owner, inode.group, inode.data.size(),
                    inode.timeCreated, inode.timeModified, inode.deviceNumber, inode.references)
        return self.syscallReturnSuccess(pid, stat)

    @strace
    def getdents(self, pid: PID, fd: FD) -> List[DirEnt]:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd
        if ofdEntry.file.fileType != FileType.DIRECTORY:
            raise KernelError("", Errno.NOT_A_DIR)
        out: List[DirEnt] = []
        for name, child in cast(DirectoryData, ofdEntry.file.data).children.items():
            out.append(DirEnt(name, child))

        return self.syscallReturnSuccess(pid, out)

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
    def waitpid(self, pid: PID, childPid: PID) -> Tuple[PID, int]:
        process = self.getProcess(pid)
        childProcess = self.getProcess(childPid)
        if childProcess.ppid != pid:
            raise KernelError("Cannot wait on non-child", Errno.NOT_A_CHILD)

        if childProcess.status == ProcessStatus.ZOMBIE:
            self.processes.remove(childPid)
            return self.syscallReturnSuccess(pid, (childPid, childProcess.exitCode))
        else:
            process.status = ProcessStatus.WAITING

    @strace
    def getuid(self, pid: PID) -> UID:
        process = self.getProcess(pid)
        return process.realUid

    @strace
    def geteuid(self, pid: PID) -> UID:
        process = self.getProcess(pid)
        return process.uid

    @strace
    def setuid(self, pid: PID, uid: UID) -> int:
        process = self.getProcess(pid)
        if uid == process.uid or uid == process.realUid or self.isSuperUser(process.uid):
            process.uid = uid
            process.realUid = uid
            return 0
        return 1

    @strace
    def getgid(self, pid: PID) -> GID:
        process = self.getProcess(pid)
        return process.realGid

    @strace
    def getegid(self, pid: PID) -> GID:
        process = self.getProcess(pid)
        return process.gid

    @strace
    def setgid(self, pid: PID, gid: GID) -> int:
        process = self.getProcess(pid)
        if gid == process.gid or gid == process.realGid or self.isSuperUser(process.uid):
            process.gid = gid
            process.realGid = gid
            return 0
        return 1

    @strace
    def getpid(self, pid: PID) -> PID:
        return pid

    @strace
    def gettimeofday(self, pid: PID, time: int) -> int:
        pass

    @strace
    def link(self, pid: PID, target: str, alias: str) -> None:
        process = self.getProcess(pid)
        targetInode = self.getINodeFromPath(pid, target)

        if targetInode.fileType == FileType.DIRECTORY or alias.endswith("/"):
            if not (targetInode.fileType == FileType.DIRECTORY and self.isSuperUser(process.uid)):
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
        if childInode.fileType == FileType.DIRECTORY and not self.isSuperUser(process.uid):
            raise KernelError("Cannot unlink directories")

        childName: str = ""
        for name, child in cast(DirectoryData, parentInode.data).children.items():
            if child.iNumber == childInode.iNumber:
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

    @strace
    def exit(self, pid: PID, exitCode: int) -> None:
        process = self.getProcess(pid)
        if process.status == ProcessStatus.ZOMBIE:
            return

        process.status = ProcessStatus.ZOMBIE
        process.exitCode = exitCode

        # clean up loose fds
        for fd in process.fdTable:
            ofd = self.openFileTable[fd.openFd.id]
            ofd.refCount -= 1
            if ofd.refCount == 0:
                self.openFileTable.remove(ofd.id)

        # send signal to parent
        if process.ppid >= 0:
            parentProcess = self.getProcess(process.ppid)
            if parentProcess.status == ProcessStatus.WAITING:
                self.processes.remove(process.pid)
                self.syscallReturnSuccess(process.ppid, pid)

        # make sure actual process terminates
        if process.pipe:
            process.pipe.close()
            self.pipes.remove(process.pipe)

    def mount(self, path: str, fs: Filesystem):
        if not path.startswith("/"):
            raise KernelError("Mount paths must be absolute", Errno.INVALID_ARG)
        self.mounts[path] = fs

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

        rootFs = makeRoot()
        self.mount("/", rootFs)
        self.rootMount = rootFs.root()
        # devFs = makeDev(self)
        # cast(DirectoryData, devFs.root()).addChild("..", self.rootMount)
        # self.rootMount.references += 1
        # cast(DirectoryData, self.rootMount.data).addChild("dev", devDir)
        # devDir.references += 1

        swapperPid = self.claimNextPid()
        swapper = ProcessEntry(swapperPid, swapperPid, "swapper", self.rootUser.uid, self.rootUser.gid,
                               self.rootMount.iNumber, Environment())
        self.processes.add(swapper)

        sleep(1)

        userPipe, kernelPipe = Pipe()
        swapper.pipe = kernelPipe
        self.pipes.append(kernelPipe)
        system = SystemHandle(swapper.pid, userPipe)
        system.fork(Sh, "sh", [])
        while True:
            sleep(1000)
