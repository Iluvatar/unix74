from enum import IntEnum, auto


class Errno(IntEnum):
    NONE = 0
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
    ENOEXEC = auto()
    EINTR = auto()

    UNSPECIFIED = auto()  # internal use
    EKILLED = auto()  # internal use

    PANIC = 255


class KernelError(Exception):
    def __init__(self, message: str, errno: Errno):
        super(KernelError, self).__init__(message)
        self.errno = errno

    def __str__(self):
        return f"KernelError:({Errno(self.errno).name}: '{self.args[0]}')"

    def __repr__(self):
        return self.__str__()


class SyscallError(KernelError):
    pass


class ProcessKilledError(Exception):
    pass
