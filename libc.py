from process.file_descriptor import FD
from unix import SystemHandle


class Libc:
    STDIN = FD(0)
    STDOUT = FD(1)
    STDERR = FD(2)

    def __init__(self, systemHandle: SystemHandle):
        self.system = systemHandle

    def printf(self, string: str) -> int:
        print(string)
        return len(string)  # return self.system.write(Libc.STDOUT, string)
