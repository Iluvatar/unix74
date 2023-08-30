from multiprocessing.connection import Connection
from typing import List, Tuple, Type

from filesystem.filesystem_utils import DirEnt, Stat
from kernel.errors import Errno, SyscallError
from process.file_descriptor import FD, FileMode, PID, SeekFrom
from process.process_code import ProcessCode


class SystemHandle:
    def __init__(self, pid: PID, userPipe: Connection, kernelPipe: Connection):
        self.pid = pid
        self.userPipe = userPipe
        self.kernelPipe = kernelPipe

    def __syscall(self, name: str, *args):
        self.userPipe.send((name, self.pid, *args))
        ret = self.userPipe.recv()
        if ret[0] != Errno.NONE:
            raise SyscallError(f"{ret[0]}: {repr(ret[1])}")
        return ret[1]

    def debug__print(self) -> None:
        return self.__syscall("debug__print")

    def debug__print_process(self, pid: PID) -> None:
        return self.__syscall("debug__print_process", pid)

    def debug__print_processes(self) -> None:
        return self.__syscall("debug__print_processes")

    def fork(self, child: Type[ProcessCode], command: str, argv: List[str]) -> PID:
        return self.__syscall("fork", child, command, argv)

    def open(self, path: str, mode: FileMode) -> FD:
        return self.__syscall("open", path, mode)

    def lseek(self, fd: FD, offset: int, whence: SeekFrom) -> FD:
        return self.__syscall("lseek", fd, offset, whence)

    def read(self, fd: FD, size: int) -> str:
        return self.__syscall("read", fd, size)

    def write(self, fd: FD, data: str) -> int:
        return self.__syscall("write", fd, data)

    def close(self, fd: FD) -> None:
        return self.__syscall("close", fd)

    def chdir(self, path: str) -> None:
        return self.__syscall("chdir", path)

    def stat(self, path: str) -> Stat:
        return self.__syscall("stat", path)

    def getdents(self, fd: FD) -> List[DirEnt]:
        return self.__syscall("getdents", fd)

    def waitpid(self, pid: PID) -> Tuple[PID, int]:
        return self.__syscall("waitpid", pid)

    def exit(self, exitCode: int) -> None:
        return self.__syscall("exit", exitCode)