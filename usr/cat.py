from kernel.errors import SyscallError
from process.file_descriptor import FileMode
from process.process_code import ProcessCode


class Cat(ProcessCode):
    def run(self) -> int:
        def readFromInput():
            try:
                while True:
                    self.libc.printf(self.libc.readline() + "\n")
            except EOFError:
                pass

        if len(self.argv) == 0:
            readFromInput()
            return 0

        for file in self.argv:
            if file == "-":
                readFromInput()
                continue

            try:
                fd = self.system.open(file, FileMode.READ)
            except SyscallError:
                self.libc.printf(f"{file}: No such file or directory\n")
                continue

            totalSize = 0
            while len(data := self.libc.read(fd, 1000)) > 0:
                self.libc.printf(data)
                totalSize += len(data)
            if totalSize > 0 and not data.endswith("\n"):
                data += "\n"
            self.libc.printf(data)

        return 0
