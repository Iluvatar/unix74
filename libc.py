from _md5 import md5
from getpass import getpass
from typing import TYPE_CHECKING

from kernel.errors import Errno
from process.file_descriptor import FD, OpenFlags, SeekFrom

if TYPE_CHECKING:
    from kernel.unix import SystemHandle


class LibcError(Exception):
    def __init__(self, message: str, errno: Errno):
        super(LibcError, self).__init__(message)
        self.errno = errno

    def __str__(self):
        return f"{str(self.errno)}: {self.args[0]}"


class Libc:
    STDIN = FD(0)
    STDOUT = FD(1)
    STDERR = FD(2)

    def __init__(self, systemHandle: 'SystemHandle'):
        self.__system = systemHandle

    def printf(self, string: str) -> int:
        print(string, end="")
        return len(string)  # return self.system.write(Libc.STDOUT, string)

    def readline(self) -> str:
        return input()

    def readPassword(self) -> str:
        return getpass("")

    def readAll(self, fd: FD) -> str:
        text = ""
        while len(data := self.__system.read(fd, 1000)) > 0:
            text += data
        return text

    def open(self, path: str, mode: OpenFlags = OpenFlags.READ) -> FD:
        return self.__system.open(path, mode)

    def lseek(self, fd: FD, offset: int, whence: SeekFrom) -> int:
        return self.__system.lseek(fd, offset, whence)

    def read(self, fd: FD, size: int) -> str:
        return self.__system.read(fd, size)

    def write(self, fd: FD, data: str) -> int:
        return self.__system.write(fd, data)

    def close(self, fd: FD) -> None:
        return self.__system.close(fd)

    def crypt(self, plaintext) -> str:
        return md5(plaintext.encode("utf-8")).hexdigest()[:16]

    def getenv(self, var: str) -> str:
        return self.__system.env.getVar(var)

    def setenv(self, var: str, value: str) -> None:
        return self.__system.env.setVar(var, value)

    def getPw(self, name: str) -> str:
        fd = self.open("/etc/passwd", OpenFlags.READ)
        file = ""
        while len(data := self.read(fd, 100)):
            file += data

        lines = file.split("\n")
        for line in lines:
            try:
                user, _, _, _, _, _, _ = line.split(":")
            except ValueError:
                continue

            if user == name:
                return line

        raise LibcError(f"No such user {name}", 1)
