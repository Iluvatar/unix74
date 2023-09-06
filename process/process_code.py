from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from libc import Libc
    from kernel.unix import SystemHandle


class ProcessCode:
    def __init__(self, systemHandle: 'SystemHandle', libc: 'Libc', command: str, argv: List[str]):
        self.system = systemHandle
        self.libc = libc
        self.command = command
        self.argv = argv

    def run(self) -> int:
        return 0
