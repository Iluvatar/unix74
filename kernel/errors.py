from enum import Enum, auto


class Errno(Enum):
    NONE = 0
    PERMISSION = auto()
    NO_ACCESS = auto()
    NO_SUCH_FILE = auto()
    IS_A_DIR = auto()
    NOT_A_DIR = auto()
    INVALID_ARG = auto()
    FUNC_NOT_IMPLEMENTED = auto()
    BAD_PID = auto()
    NOT_A_CHILD = auto()


class KernelError(Exception):
    def __init__(self, message: str, errno: Errno):
        super(KernelError, self).__init__(message)
        self.errno = errno


class SyscallError(Exception):
    pass
