from __future__ import annotations

import select
import traceback
from collections.abc import Callable
from datetime import datetime
from multiprocessing import Pipe
from multiprocessing.connection import Connection
from time import sleep
from typing import Any, Dict, List, NewType, Tuple, Type, TypeVar, cast
from uuid import UUID

from environment import Environment
from filesystem.filesystem import DirectoryData, FilePermissions, FileType, Filesystem, INode, INodeData, INumber, Mode
from filesystem.filesystem_loader import makeDev, makeRoot
from filesystem.filesystem_utils import Dentry, INodeOperation, Mount, Stat
from kernel.errors import Errno, KernelError
from kernel.system_handle import SystemHandle
from libc import Libc
from process.file_descriptor import FD, OFD, OpenFileDescriptor, OpenFlags, PID, SeekFrom
from process.process import OsProcess, ProcessEntry, ProcessFileDescriptor, ProcessStatus
from process.process_code import ProcessCode
from self_keyed_dict import SelfKeyedDict
from user import GID, Group, GroupName, GroupPassword, Password, UID, User, UserName
from usr.sh import Sh

T = TypeVar("T")

UserId = NewType('UserId', int)
GroupId = NewType('GroupId', int)


class Unix:
    def __init__(self):
        self.mounts: List[Mount] = []
        self.filesystems: SelfKeyedDict[Filesystem, UUID] = SelfKeyedDict("uuid")
        self.rootNode: Filesystem | None = None
        self.rootUser: User = User(UserName("root"), Password(""), UID(0), GID(0), "root", "/", "/usr/sh")
        self.processes: SelfKeyedDict[ProcessEntry, PID] = SelfKeyedDict("pid")
        self.openFileTable: SelfKeyedDict[OpenFileDescriptor, OFD] = SelfKeyedDict("id")
        self.nextPid: PID = PID(0)

        self.pipes: List[Connection] = []

        self.doStrace: bool = False
        self.printDebug = False

    def __str__(self):
        out = "Unix74\n------\n"

        out += f"mounts ({len(self.mounts)}):\n"
        for mount in self.mounts:
            out += f"    {mount}\n"
        out += f"root mount is {self.rootNode.rootINum}\n\n"

        out += f"processes ({len(self.processes)}):\n"
        for process in self.processes:
            out += f"    {process.pid}: {process}\n"
        out += "\n"

        out += f"open file table ({len(self.openFileTable)}):\n"
        for entry in self.openFileTable:
            out += f"    {entry}\n"

        return out

    def sendSyscallReturn(self, pipe: Connection, errno: Errno, value) -> None:
        if pipe:
            pipe.send((value, errno))

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

    def printFilesystems(self, pid: PID):
        for mount in self.mounts:
            print(mount)
        self.syscallReturnSuccess(pid, None)

    def start(self):
        syscallDict: Dict[str, Callable[PID, ...]] = {
            "debug__print": self.debug,
            "debug__print_process": self.printProcess,
            "debug__print_processes": self.printProcesses,
            "debug__print_filesystems": self.printFilesystems,

            "fork": self.fork,
            "open": self.open,
            "creat": self.creat,
            "lseek": self.lseek,
            "read": self.read,
            "write": self.write,
            "close": self.close,
            "link": self.link,
            "unlink": self.unlink,
            "chdir": self.chdir,
            "getdents": self.getdents,
            "stat": self.stat,
            "waitpid": self.waitpid,
            "getuid": self.getuid,
            "geteuid": self.geteuid,
            "setuid": self.setuid,
            "getgid": self.getgid,
            "getegid": self.getegid,
            "setgid": self.setgid,
            "getpid": self.getpid,
            "umount": self.umount,
            "exit": self.exit,
        }

        while True:
            ready, _, _ = select.select(self.pipes, [], [], .05)
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
                        self.sendSyscallReturn(pipe, Errno.ENOSYS, f"Invalid syscall {syscall}")
                except TypeError as e:
                    if self.printDebug:
                        traceback.print_tb(e.__traceback__)
                    self.sendSyscallReturn(pipe, Errno.EINVAL, repr(e))
                except KernelError as e:
                    if self.printDebug:
                        traceback.print_tb(e.__traceback__)
                    self.sendSyscallReturn(pipe, e.errno, repr(e))
                except Exception as e:
                    if self.printDebug:
                        traceback.print_tb(e.__traceback__)
                    self.sendSyscallReturn(pipe, Errno.PANIC, repr(e))

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
            raise KernelError(f"No such process {pid}", Errno.ESRCH) from None

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
                raise KernelError(f"Mode requested {m}, actual is {inodeMode}", Errno.EACCES)
            return True

        process = self.getProcess(pid)
        if self.isSuperUser(process.uid):
            if Mode.EXEC in mode and Mode.EXEC not in (
                    inode.permissions.owner | inode.permissions.group | inode.permissions.other):
                raise KernelError("", Errno.EACCES)
            return True
        if process.uid == inode.owner:
            return checkModeSubset(mode, inode.permissions.owner)
        if process.gid == inode.group:
            return checkModeSubset(mode, inode.permissions.group)
        return checkModeSubset(mode, inode.permissions.other)

    def iget(self, filesystemId: UUID, iNumber: INumber) -> INode:
        fs = self.filesystems[filesystemId]
        inode = fs.inodes[iNumber]
        if inode.isMount:
            for mount in self.mounts:
                if inode.filesystemId == mount.mountedOnFsId and inode.iNumber == mount.mountedOnINumber:
                    inode = self.filesystems[mount.mountedFsId].root()
                    break
            else:
                raise KernelError(f"Unknown filesystem {filesystemId}", Errno.ENOENT)
        return inode

    def traversePath(self, pid: PID, path: str, op: INodeOperation) -> INode:
        if not self.rootNode:
            raise KernelError("No root mount found", Errno.ENOENT)

        process = self.getProcess(pid)
        currentNode: INode = process.currentDir
        if path.startswith("/"):
            currentNode = self.rootNode.root()

        parts = path.rstrip("/").split("/")
        traversePath = parts
        if op in [INodeOperation.CREATE, INodeOperation.CREATE_EXCLUSIVE, INodeOperation.PARENT]:
            traversePath = parts[:-1]
        for part in traversePath:
            if currentNode.fileType != FileType.DIRECTORY:
                raise KernelError(path, Errno.ENOTDIR)
            self.access(pid, currentNode, Mode.EXEC)
            if part == "":
                part = "."

            fs = self.filesystems[currentNode.filesystemId]

            if fs.root().iNumber == currentNode.iNumber and part == "..":
                if self.rootNode.root() == currentNode:
                    continue
                covered: INode = self.filesystems[currentNode.filesystemId].covered
                if not covered:
                    raise KernelError(path, Errno.ENOENT)
                currentNode = covered

            try:
                childINumber = cast(DirectoryData, currentNode.data).children[part]
                currentNode = self.iget(currentNode.filesystemId, childINumber)
            except KeyError:
                raise KernelError(path, Errno.ENOENT) from None

        if op == INodeOperation.GET or op == INodeOperation.PARENT:
            return currentNode
        elif op == INodeOperation.CREATE or op == INodeOperation.CREATE_EXCLUSIVE:
            name = parts[-1]
            fs = self.filesystems[currentNode.filesystemId]

            inode = fs.inodes.get(cast(DirectoryData, currentNode.data).children[name], None)
            if inode:
                if op == INodeOperation.CREATE_EXCLUSIVE:
                    raise KernelError(path, Errno.EEXIST)
                else:
                    return inode

            self.access(pid, currentNode, Mode.WRITE)
            child = INode(fs.claimNextINumber(), currentNode.permissions, FileType.REGULAR, process.uid, process.gid,
                          datetime.now(), datetime.now(), INodeData(), fs.uuid)
            cast(DirectoryData, currentNode.data).addChild(parts[-1], child.iNumber)
            self.filesystems[currentNode.filesystemId].inodes.add(child)
            return child
        else:
            raise KernelError(f"Invalid op: {op}", Errno.ENOSYS)

    def getINodeFromPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.GET)

    def createINodeAtPath(self, pid: PID, path: str, exclusive: bool = False) -> INode:
        if exclusive:
            return self.traversePath(pid, path, INodeOperation.CREATE_EXCLUSIVE)
        else:
            return self.traversePath(pid, path, INodeOperation.CREATE)

    def getINodeParentFromPath(self, pid: PID, path: str) -> INode:
        return self.traversePath(pid, path, INodeOperation.PARENT)

    # System calls

    @strace
    def fork(self, pid: PID, child: Type[ProcessCode], command: str, argv: List[str], env: Environment) -> PID:
        process = self.getProcess(pid)
        childPid = self.claimNextPid()
        userPipe, kernelPipe = Pipe()
        self.pipes.append(kernelPipe)
        childProcessEntry = ProcessEntry(childPid, pid, command, process.realUid, process.realGid, process.currentDir,
                                         pipe=kernelPipe)
        self.processes.add(childProcessEntry)

        system = SystemHandle(childPid, env.copy(), userPipe, kernelPipe)
        libc = Libc(system)
        childProcess = OsProcess(child(system, libc, command, argv))
        childProcess.run()
        childProcessEntry.pythonPid = childProcess.process.pid

        return self.syscallReturnSuccess(pid, childPid)

    def createFd(self, inode: INode, flags: OpenFlags, pid: PID) -> FD:
        process = self.getProcess(pid)
        ofd = OpenFileDescriptor(self.claimNextOftId(), flags, inode)
        self.openFileTable.add(ofd)
        processFdNum: FD = process.claimNextFdNum()
        process.fdTable.add(ProcessFileDescriptor(processFdNum, ofd))

        if flags & OpenFlags.TRUNCATE:
            inode.data.trunc()
            ofd.offset = 0

        return processFdNum

    @strace
    def open(self, pid: PID, path: str, flags: OpenFlags) -> FD:
        try:
            inode = self.getINodeFromPath(pid, path)
        except FileNotFoundError:
            raise KernelError(path, Errno.ENOENT) from None

        if OpenFlags.READ in flags:
            self.access(pid, inode, Mode.READ)
        if (OpenFlags.WRITE | OpenFlags.APPEND | OpenFlags.CREATE | OpenFlags.TRUNCATE) & flags:
            self.access(pid, inode, Mode.WRITE)
            flags |= OpenFlags.WRITE

        processFdNum = self.createFd(inode, flags, pid)
        return self.syscallReturnSuccess(pid, processFdNum)

    def creat(self, pid: PID, path: str, permissions: FilePermissions) -> FD:
        inode = self.createINodeAtPath(pid, path)
        if inode.fileType == FileType.DIRECTORY:
            raise KernelError(path, Errno.EISDIR)
        inode.permissions = permissions
        self.access(pid, inode, Mode.WRITE)

        processFdNum = self.createFd(inode, OpenFlags.WRITE | OpenFlags.TRUNCATE, pid)
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

        if OpenFlags.READ not in ofdEntry.mode:
            raise KernelError("No read access", Errno.EACCES)

        data = ofdEntry.file.data.read(size, ofdEntry.offset)
        ofdEntry.offset += len(data)

        return self.syscallReturnSuccess(pid, data)

    @strace
    def write(self, pid: PID, fd: FD, data: str) -> int:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd

        if OpenFlags.WRITE not in ofdEntry.mode:
            raise KernelError("No write access", Errno.EACCES)

        if ofdEntry.mode & OpenFlags.APPEND:
            numBytes = ofdEntry.file.data.append(data)
            ofdEntry.offset = ofdEntry.file.data.size()
        else:
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

        return self.syscallReturnSuccess(pid, None)

    @strace
    def pipe(self, pid: PID) -> (FD, FD):
        pass

    @strace
    def stat(self, pid: PID, path: str) -> Stat:
        inode = self.getINodeFromPath(pid, path)
        stat = Stat(inode.iNumber, inode.permissions, inode.fileType, inode.owner, inode.group, inode.data.size(),
                    inode.timeCreated, inode.timeModified, inode.filesystemId, inode.deviceNumber, inode.references)
        return self.syscallReturnSuccess(pid, stat)

    @strace
    def getdents(self, pid: PID, fd: FD) -> List[Dentry]:
        process = self.getProcess(pid)
        fdEntry = process.fdTable[fd]
        ofdEntry = fdEntry.openFd
        if ofdEntry.file.fileType != FileType.DIRECTORY:
            raise KernelError("", Errno.ENOTDIR)
        out: List[Dentry] = []
        for name, child in cast(DirectoryData, ofdEntry.file.data).children.items():
            out.append(Dentry(name, child, ofdEntry.file.filesystemId))

        return self.syscallReturnSuccess(pid, out)

    @strace
    def chdir(self, pid: PID, path: str) -> None:
        process = self.getProcess(pid)
        inode = self.getINodeFromPath(pid, path)
        if inode.fileType != FileType.DIRECTORY:
            raise KernelError(path, Errno.ENOENT)
        self.access(pid, inode, Mode.EXEC)
        process.currentDir = inode

        return self.syscallReturnSuccess(pid, None)

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
            raise KernelError("Cannot wait on non-child", Errno.ECHILD)

        if childProcess.status == ProcessStatus.ZOMBIE:
            self.processes.remove(childPid)
            return self.syscallReturnSuccess(pid, (childPid, childProcess.exitCode))
        else:
            process.status = ProcessStatus.WAITING

    @strace
    def getuid(self, pid: PID) -> UID:
        process = self.getProcess(pid)
        return self.syscallReturnSuccess(pid, process.realUid)

    @strace
    def geteuid(self, pid: PID) -> UID:
        process = self.getProcess(pid)
        return process.uid

    @strace
    def setuid(self, pid: PID, uid: UID) -> None:
        process = self.getProcess(pid)
        if uid == process.uid or uid == process.realUid or self.isSuperUser(process.uid):
            process.uid = uid
            process.realUid = uid
            return self.syscallReturnSuccess(pid, None)
        raise KernelError("", Errno.EPERM)

    @strace
    def getgid(self, pid: PID) -> GID:
        process = self.getProcess(pid)
        return self.syscallReturnSuccess(pid, process.realGid)

    @strace
    def getegid(self, pid: PID) -> GID:
        process = self.getProcess(pid)
        return self.syscallReturnSuccess(pid, process.gid)

    @strace
    def setgid(self, pid: PID, gid: GID) -> None:
        process = self.getProcess(pid)
        if gid == process.gid or gid == process.realGid or self.isSuperUser(process.uid):
            process.gid = gid
            process.realGid = gid
            return self.syscallReturnSuccess(pid, None)
        raise KernelError("", Errno.EPERM)

    @strace
    def getpid(self, pid: PID) -> PID:
        return self.syscallReturnSuccess(pid, pid)

    @strace
    def gettimeofday(self, pid: PID, time: int) -> int:
        pass

    @strace
    def mount(self, pid: PID, path: str, fs: Filesystem) -> None:
        process = self.getProcess(pid)
        if not self.isSuperUser(process.uid):
            raise KernelError("Only superuser can mount", Errno.EPERM)
        inode = self.getINodeFromPath(pid, path)
        self.mounts.append(Mount(fs.uuid, inode.filesystemId, inode.iNumber))
        inode.isMount = True
        fs.covered = inode
        self.filesystems.add(fs)
        return self.syscallReturnSuccess(pid, None)

    @strace
    def umount(self, pid: PID, path: str) -> None:
        process = self.getProcess(pid)
        if not self.isSuperUser(process.uid):
            raise KernelError("Only superuser can unmount", Errno.EPERM)
        inode = self.getINodeFromPath(pid, path)
        fs = self.filesystems[inode.filesystemId]
        if inode != fs.root():
            raise KernelError(f"{path} not currently mounted", Errno.EINVAL)
        fs.covered.isMount = False
        self.mounts.remove(Mount(fs.uuid, fs.covered.filesystemId, fs.covered.iNumber))
        return self.syscallReturnSuccess(pid, None)

    @strace
    def link(self, pid: PID, target: str, alias: str) -> None:
        targetInode = self.getINodeFromPath(pid, target)
        if targetInode.fileType == FileType.DIRECTORY:
            raise KernelError(target, Errno.EISDIR)

        parent = self.getINodeParentFromPath(pid, alias)
        if targetInode.filesystemId != parent.filesystemId:
            raise KernelError("", Errno.EXDEV)

        try:
            self.getINodeFromPath(pid, alias)
        except KernelError as e:
            if e.errno != Errno.ENOENT:
                raise

        childName = alias.split("/")[-1]
        cast(DirectoryData, parent.data).addChild(childName, targetInode.iNumber)
        targetInode.references += 1

        return self.syscallReturnSuccess(pid, None)

    @strace
    def unlink(self, pid: PID, target: str) -> None:
        parentInode = self.getINodeParentFromPath(pid, target)
        childInode = self.getINodeFromPath(pid, target)

        if childInode.fileType == FileType.DIRECTORY:
            raise KernelError(target, Errno.EISDIR)

        self.access(pid, parentInode, Mode.WRITE)
        childName = target.split("/")[-1]
        cast(DirectoryData, parentInode.data).removeChild(childName)
        childInode.references -= 1

        if childInode.references == 0:
            self.filesystems[childInode.filesystemId].inodes.remove(childInode.iNumber)

        return self.syscallReturnSuccess(pid, None)

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

    def startup(self):
        rootFs = makeRoot()
        self.mounts.append(Mount(rootFs.uuid, UUID(int=0), INumber(0)))
        self.rootNode = rootFs
        self.filesystems.add(rootFs)

        swapperPid = self.claimNextPid()
        swapper = ProcessEntry(swapperPid, swapperPid, "swapper", self.rootUser.uid, self.rootUser.gid,
                               self.rootNode.root())
        self.processes.add(swapper)

        devFs = makeDev(self)
        self.mount(PID(0), "/dev", devFs)

        userPipe, kernelPipe = Pipe()
        swapper.pipe = kernelPipe
        self.pipes.append(kernelPipe)
        system = SystemHandle(swapper.pid, Environment(), userPipe, kernelPipe)
        pid = system.fork(Sh, "sh", [])
        while True:
            sleep(1000)
