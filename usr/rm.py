from kernel.errors import Errno, SyscallError
from process.process_code import ProcessCode


class Rm(ProcessCode):
    def run(self) -> int:
        target = self.argv[0]

        exitCode: int = 0

        try:
            self.system.unlink(target)
        except SyscallError as e:
            exitCode = 1
            if e.errno == Errno.EACCES:
                print(f"{self.command}: permission denied")
            elif e.errno == Errno.EISDIR:
                print(f"{self.command}: cannot delete directory")
            elif e.errno == Errno.ENOENT:
                print(f"{self.command}: no such file or directory")

        return exitCode
