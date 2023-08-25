from __future__ import annotations

from collections.abc import MutableSet
from dataclasses import dataclass, field

from environment import Environment
from filesystem.filesystem import INode
from process.file_descriptor import FD, PID, ProcessFileDescriptor
from self_keyed_dict import SelfKeyedDict
from user import GID, UID


@dataclass
class Process:
    pid: PID
    parent: 'Process'
    command: str
    owner: UID
    group: GID
    currentDir: INode
    env: Environment
    fdTable: SelfKeyedDict[ProcessFileDescriptor, FD] = field(default_factory=lambda: SelfKeyedDict("id"))
    children: MutableSet['Process'] = field(default_factory=set)

    def claimNextFdNum(self):
        i: FD = FD(0)
        while i in self.fdTable:
            i += 1
        return i

    def __hash__(self) -> int:
        return self.pid

    def __eq__(self, other) -> bool:
        return self.pid == other.pid

    def __str__(self) -> str:
        fds = ",".join([str(fd) for fd in self.fdTable])
        return f"['{self.command}', pid:{self.pid}, owner: {self.owner}, fd: [{fds}]]"
