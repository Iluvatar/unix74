from enum import Enum, auto


class Errno(Enum):
    NONE = 0
    UNSPECIFIED = auto()
    EPERM = auto()
    EACCES = auto()
    ENOENT = auto()
    EEXIST = auto()
    EISDIR = auto()
    ENOTDIR = auto()
    EINVAL = auto()
    ENOSYS = auto()
    ECHILD = auto()
    ESRCH = auto()
    EXDEV = auto()

    PANIC = auto()


class KernelError(Exception):
    def __init__(self, message: str, errno: Errno):
        super(KernelError, self).__init__(message)
        self.errno = errno

    def __str__(self):
        return f"{str(self.errno)}: {self.args[0]}"


class SyscallError(KernelError):
    pass
