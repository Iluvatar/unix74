import typing
from _md5 import md5

from process.file_descriptor import FD, OpenFlags, SeekFrom
from user import UID

if typing.TYPE_CHECKING:
    from kernel.unix import SystemHandle


class Libc:
    STDIN = FD(0)
    STDOUT = FD(1)
    STDERR = FD(2)

    def __init__(self, systemHandle: 'SystemHandle'):
        self.system = systemHandle

    def printf(self, string: str) -> int:
        print(string, end="")
        return len(string)  # return self.system.write(Libc.STDOUT, string)

    def readline(self) -> str:
        return input()

    def readAll(self, fd: FD) -> str:
        text = ""
        while len(data := self.system.read(fd, 1000)) > 0:
            text += data
        return text

    def open(self, path: str, mode: OpenFlags = OpenFlags.READ) -> FD:
        return self.system.open(path, mode)

    def lseek(self, fd: FD, offset: int, whence: SeekFrom) -> int:
        return self.system.lseek(fd, offset, whence)

    def read(self, fd: FD, size: int) -> str:
        return self.system.read(fd, size)

    def write(self, fd: FD, data: str) -> int:
        return self.system.write(fd, data)

    def close(self, fd: FD) -> None:
        return self.system.close(fd)

    def crypt(self, plaintext) -> str:
        return md5(plaintext.encode("utf-8")).hexdigest()[:16]

    def getenv(self, var: str) -> str:
        return self.system.env.getVar(var)

    def setenv(self, var: str, value: str) -> None:
        return self.system.env.setVar(var, value)

    def getPw(self, uid: UID) -> str:
        fd = self.open("/etc/passwd", OpenFlags.READ)
        file = ""
        while len(data := self.read(fd, 100)):
            file += data

        lines = file.split("\n")
        for line in lines:
            try:
                _, _, uidStr, _, _, _, _ = line.split(":")
            except ValueError:
                continue

            if uid == int(uidStr):
                return line

        raise ValueError(f"No such user {uid}")
