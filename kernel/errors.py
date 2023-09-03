from enum import Enum, auto


class Errno(Enum):
    NONE = 0
    UNSPECIFIED = auto()
    PERMISSION = auto()
    NO_ACCESS = auto()
    NO_SUCH_FILE = auto()
    IS_A_DIR = auto()
    NOT_A_DIR = auto()
    INVALID_ARG = auto()
    FUNC_NOT_IMPLEMENTED = auto()
    BAD_PID = auto()
    NOT_A_CHILD = auto()

    PANIC = auto()


class KernelError(Exception):
    def __init__(self, message: str, errno: Errno):
        super(KernelError, self).__init__(message)
        self.errno = errno

    def __str__(self):
        return f"{str(self.errno)}: {self.args[0]}"


class SyscallError(KernelError):
    pass
