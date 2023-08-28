import typing
from typing import List

if typing.TYPE_CHECKING:
    from libc import Libc
    from unix import SystemHandle


class ProcessCode:
    def __init__(self, systemHandle: 'SystemHandle', libc: 'Libc', argv: List[str]):
        self.system = systemHandle
        self.libc = libc
        self.argv = argv

    def run(self) -> int:
        raise NotImplementedError()
