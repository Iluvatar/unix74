from kernel.errors import Errno, SyscallError
from process.process_code import ProcessCode


class Rm(ProcessCode):
    def run(self) -> int:
        target = self.argv[0]

        try:
            self.system.unlink(target)
        except SyscallError as e:
            if e.errno == Errno.EACCES:
                print(f"rm: permission denied")
            elif e.errno == Errno.EISDIR:
                print(f"rm: cannot delete directory")
            elif e.errno == Errno.ENOENT:
                print(f"rm: no such file or directory")
        return 0
