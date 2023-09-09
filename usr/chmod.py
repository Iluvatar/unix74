from filesystem.filesystem import FilePermissions
from kernel.errors import SyscallError
from process.process_code import ProcessCode


class Chmod(ProcessCode):
    def run(self) -> int:
        if len(self.argv) < 2:
            self.libc.printf("arg count\n")
            return 1

        permInt = int(self.argv[0], 8)
        if permInt < 0 or permInt >= 8 ** 4:
            self.libc.printf("bad mode\n")
            return 1
        permissions = FilePermissions(permInt)
        for path in self.argv[1:]:
            try:
                self.system.chmod(path, permissions)
            except SyscallError as e:
                self.libc.printf(f"cannot chmod {path}\n")

        return 1
