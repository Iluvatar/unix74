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
            except FileNotFoundError:
                self.libc.printf(f"{file}: No such file or directory\n")
                continue

            out = ""
            while len(data := self.system.read(fd, 100)) > 0:
                out += data

            self.libc.printf(out)

        return 0
