from multiprocessing.connection import Connection
from typing import List, Tuple, Type

from environment import Environment
from filesystem.filesystem import FilePermissions
from filesystem.filesystem_utils import Dentry, Stat
from kernel.errors import Errno, SyscallError
from process.file_descriptor import FD, OpenFlags, PID, SeekFrom
from process.process_code import ProcessCode
from user import GID, UID


class SystemHandle:
    def __init__(self, pid: PID, env: Environment, userPipe: Connection, kernelPipe: Connection):
        self.pid = pid
        self.env = env
        self.userPipe = userPipe
        self.kernelPipe = kernelPipe

    def __syscall(self, name: str, *args):
        self.userPipe.send((name, self.pid, *args))
        ret = self.userPipe.recv()
        if ret[1] != Errno.NONE:
            raise SyscallError(ret[0], ret[1])
        return ret[0]

    def debug__print(self) -> None:
        return self.__syscall("debug__print")

    def debug__print_process(self, pid: PID) -> None:
        return self.__syscall("debug__print_process", pid)

    def debug__print_processes(self) -> None:
        return self.__syscall("debug__print_processes")

    def debug__print_filesystems(self) -> None:
        return self.__syscall("debug__print_filesystems")

    def fork(self, child: Type[ProcessCode], command: str, argv: List[str]) -> PID:
        return self.__syscall("fork", child, command, argv, self.env)

    def open(self, path: str, mode: OpenFlags) -> FD:
        return self.__syscall("open", path, mode)

    def creat(self, path: str, permissions: FilePermissions) -> FD:
        return self.__syscall("creat", path, permissions)

    def lseek(self, fd: FD, offset: int, whence: SeekFrom) -> FD:
        return self.__syscall("lseek", fd, offset, whence)

    def read(self, fd: FD, size: int) -> str:
        return self.__syscall("read", fd, size)

    def write(self, fd: FD, data: str) -> int:
        return self.__syscall("write", fd, data)

    def close(self, fd: FD) -> None:
        return self.__syscall("close", fd)

    def link(self, target: str, alias: str) -> None:
        return self.__syscall("link", target, alias)

    def unlink(self, target: str) -> None:
        return self.__syscall("unlink", target)

    def chdir(self, path: str) -> None:
        return self.__syscall("chdir", path)

    def stat(self, path: str) -> Stat:
        return self.__syscall("stat", path)

    def getdents(self, fd: FD) -> List[Dentry]:
        return self.__syscall("getdents", fd)

    def waitpid(self, pid: PID) -> Tuple[PID, int]:
        return self.__syscall("waitpid", pid)

    def getuid(self) -> UID:
        return self.__syscall("getuid")

    def geteuid(self) -> UID:
        return self.__syscall("geteuid")

    def setuid(self, uid: UID) -> None:
        return self.__syscall("setuid", uid)

    def getgid(self) -> GID:
        return self.__syscall("getgid")

    def getegid(self) -> GID:
        return self.__syscall("getegid")

    def setgid(self, gid: GID) -> None:
        return self.__syscall("setgid", gid)

    def getpid(self) -> PID:
        return self.__syscall("getpid")

    def umount(self, path: str) -> None:
        return self.__syscall("umount", path)

    def execve(self, path: str, args: List[str]) -> PID:
        return self.__syscall("execve", path, args)

    def exit(self, exitCode: int) -> None:
        return self.__syscall("exit", exitCode)
