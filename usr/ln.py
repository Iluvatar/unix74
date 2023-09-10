from kernel.errors import Errno, SyscallError
from process.process_code import ProcessCode


class Ln(ProcessCode):
    def run(self) -> int:
        if len(self.argv) < 2:
            print(f"Usage: {self.command} target alias")
            return 1

        target = self.argv[0]
        alias = self.argv[1]

        exitCode: int = 0

        try:
            self.system.link(target, alias)
        except SyscallError as e:
            exitCode = 1
            if e.errno == Errno.EACCES:
                print(f"{self.command}: permission denied")
            elif e.errno == Errno.EISDIR:
                print(f"{self.command}: cannot hard link directories")
            elif e.errno == Errno.ENOENT:
                print(f"{self.command}: no such file or directory")
            elif e.errno == Errno.EXDEV:
                print(f"{self.command}: cannot link across filesystems")
            raise
        return exitCode
