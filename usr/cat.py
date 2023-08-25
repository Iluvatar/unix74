from process.file_descriptor import FileMode
from process.user_process import UserProcess


class Cat(UserProcess):
    def run(self) -> int:
        out = ""
        for file in self.argv[1:]:
            fd = self.system.open(file, FileMode.READ)
            while len(data := self.system.read(fd, 100)) > 0:
                out += data

        self.libc.printf(out)

        return 1
