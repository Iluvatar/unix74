from kernel.errors import Errno, SyscallError
from process.process_code import ProcessCode


class Ln(ProcessCode):
    def run(self) -> int:
        if len(self.argv) < 2:
            print("Usage: ln target alias")
            return 1

        target = self.argv[0]
        alias = self.argv[1]

        try:
            self.system.link(target, alias)
        except SyscallError as e:
            if e.errno == Errno.EACCES:
                print(f"ln: permission denied")
            elif e.errno == Errno.EISDIR:
                print(f"ln: cannot hard link directories")
            elif e.errno == Errno.ENOENT:
                print(f"ln: no such file or directory")
            elif e.errno == Errno.EXDEV:
                print(f"ln: cannot link across filesystems")
            raise
        return 0
