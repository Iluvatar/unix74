from process.file_descriptor import OpenFlags
from process.process_code import ProcessCode


class Demo(ProcessCode):
    def run(self) -> int:
        op = 0
        if len(self.argv) > 0:
            op = int(self.argv[0])

        fd = self.libc.open("/bin/ls", OpenFlags.READ_WRITE | OpenFlags.TRUNCATE)

        if op == 1:
            self.libc.write(fd, "asdf")

        return 0
