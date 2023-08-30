from __future__ import annotations

import typing
from collections.abc import Callable, MutableSet
from dataclasses import dataclass, field
from enum import Enum, auto
from multiprocessing import Process
from signal import Signals, signal
from types import FrameType
from typing import List, Tuple

from environment import Environment
from filesystem.filesystem import INumber
from process.file_descriptor import FD, PID, ProcessFileDescriptor
from process.process_code import ProcessCode
from self_keyed_dict import SelfKeyedDict
from user import GID, UID

if typing.TYPE_CHECKING:
    pass


class ProcessStatus(Enum):
    RUNNING = auto()
    ZOMBIE = auto()


@dataclass
class ProcessEntry:
    pid: PID
    ppid: PID
    command: str
    realUid: UID
    realGid: GID
    currentDir: INumber
    env: Environment
    uid: UID | None = None
    gid: GID | None = None
    status: ProcessStatus = ProcessStatus.RUNNING
    exitCode: int = 0
    pythonPid: int = -1
    tty: int = -1
    fdTable: SelfKeyedDict[ProcessFileDescriptor, FD] = field(default_factory=lambda: SelfKeyedDict("id"))
    children: MutableSet[ProcessEntry] = field(default_factory=set)

    def __post_init__(self):
        if self.uid is None:
            self.uid = self.realUid
        if self.gid is None:
            self.gid = self.realGid

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
        return f"['{self.command}', pid: {self.pid}, owner: {self.uid}, fd: [{fds}]]"

    def __repr__(self):
        return self.__str__()


SignalHandler = Tuple[Signals, Callable[[int, FrameType], None]]


class OsProcess:
    def __init__(self, code: ProcessCode, processEntry: ProcessEntry,
                 signalHandlers: List[SignalHandler] | None = None):
        self.signalHandlers: List[SignalHandler] = []
        if signalHandlers is not None:
            self.signalHandlers = signalHandlers
        self.code = code
        self.processEntry = processEntry
        self.process: Process | None = None

    def run(self):
        self.process = Process(target=self.runInternal)
        self.process.start()

    def runInternal(self):
        for handler in self.signalHandlers:
            signal(handler[0], handler[1])

        try:
            self.code.run()
        except Exception as e:
            print("Got error:", e)
        finally:
            self.code.system.exit(0)
