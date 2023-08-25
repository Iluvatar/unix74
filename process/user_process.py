from typing import List

from libc import Libc
from unix import SystemHandle


class UserProcess:
    def __init__(self, systemHandle: SystemHandle, libc: Libc, argv: List[str]):
        self.system = systemHandle
        self.libc = libc
        self.argv = argv

    def run(self) -> int:
        raise NotImplementedError()
