import sys

from kernel.errors import Errno, SyscallError
from process.file_descriptor import OpenFlags
from process.process_code import ProcessCode


class Cat(ProcessCode):
    def run(self) -> int:
        sys.stdin = open(0)

        def readFromInput():
            try:
                while True:
                    self.libc.printf(self.libc.readline() + "\n")
            except EOFError:
                pass

        if len(self.argv) == 0:
            readFromInput()
            return 0

        exitCode: int = 0

        for file in self.argv:
            if file == "-":
                readFromInput()
                continue

            try:
                fd = self.system.open(file, OpenFlags.READ)
            except SyscallError as e:
                exitCode = 1
                if e.errno == Errno.EACCES:
                    self.libc.printf(f"{self.command}: {file}: Permission denied\n")
                    continue
                elif e.errno == Errno.ENOENT:
                    self.libc.printf(f"{self.command}: {file}: No such file or directory\n")
                    continue
                raise

            while len(data := self.libc.read(fd, 1000)) > 0:
                self.libc.printf(data)

        return exitCode
