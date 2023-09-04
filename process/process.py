from __future__ import annotations

import traceback
import typing
from collections.abc import Callable, MutableSet
from dataclasses import dataclass, field
from enum import Enum, auto
from multiprocessing import Process
from multiprocessing.connection import Connection
from signal import Signals, signal
from types import FrameType
from typing import List, Tuple

from filesystem.filesystem import INode
from kernel.errors import Errno, SyscallError
from process.file_descriptor import FD, PID, ProcessFileDescriptor
from process.process_code import ProcessCode
from self_keyed_dict import SelfKeyedDict
from user import GID, UID

if typing.TYPE_CHECKING:
    pass


class ProcessStatus(Enum):
    RUNNING = auto()
    WAITING = auto()
    ZOMBIE = auto()


@dataclass
class ProcessEntry:
    pid: PID
    ppid: PID
    command: str
    realUid: UID
    realGid: GID
    currentDir: INode
    uid: UID | None = None
    gid: GID | None = None
    pipe: Connection | None = None
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
        return f"['{self.command}', pid: {self.pid}, owner: {self.uid}, {self.status}, fd: [{fds}]]"

    def __repr__(self):
        return self.__str__()


SignalHandler = Tuple[Signals, Callable[[int, FrameType], None]]


class OsProcess:
    def __init__(self, code: ProcessCode, signalHandlers: List[SignalHandler] | None = None):
        self.signalHandlers: List[SignalHandler] = []
        if signalHandlers is not None:
            self.signalHandlers = signalHandlers
        self.code = code
        self.process: Process | None = None

    def run(self):
        self.process = Process(target=self.runInternal)
        self.process.start()

    def runInternal(self):
        self.code.system.kernelPipe.close()

        for handler in self.signalHandlers:
            signal(handler[0], handler[1])

        exitCode = Errno.UNSPECIFIED
        try:
            exitCode = self.code.run()
            if exitCode is None:
                exitCode = 0
        except SyscallError as e:
            pass
        except Exception as e:
            traceback.print_tb(e.__traceback__)
            print(repr(e))

        try:
            self.code.system.exit(exitCode)
        except (EOFError, BrokenPipeError):
            pass
