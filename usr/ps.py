from typing import List, Tuple

from process.file_descriptor import PID
from process.process_code import ProcessCode
from user import UID


class Ps(ProcessCode):
    def run(self) -> int:
        allFlag: bool = False
        noTtyFlag: bool = False
        longFlag: bool = False

        while len(self.argv) > 0:
            for arg in self.argv[0]:
                if arg == "a":
                    allFlag = True
                elif arg == "x":
                    noTtyFlag = True
                elif arg == "l":
                    longFlag = True
            self.argv = self.argv[1:]

        try:
            fd = self.libc.open("/dev/mem")
        except FileNotFoundError:
            self.libc.printf("Could not open mem")
            return 1
        file: str = ""
        while len(data := self.libc.read(fd, 100)) > 0:
            file += data
        self.libc.close(fd)

        ownUid = self.system.getuid()

        processes: List[Tuple[PID, UID, int, str]] = []
        for line in file.split("\n"):
            parts = line.split(".", maxsplit=3)
            pid = PID(int(parts[0]))
            uid = UID(int(parts[1]))
            tty = int(parts[2])
            command = parts[3]

            if (allFlag or uid == ownUid) and (noTtyFlag or tty >= 0):
                processes.append((pid, uid, tty, command))

        def formatRow(pid: str, uid: str, tty: str, time: str, command: str, isLong: bool) -> str:
            if isLong:
                return f"{uid: <8} {pid: >5} {tty: <3} {time: >5} {command}\n"
            else:
                command = command.split()[0]
                return f"{pid: >5} {tty: <3} {time: >5} {command}\n"

        self.libc.printf(formatRow("PID", "USER", "TTY", "TIME", "COMMAND", longFlag))
        for process in processes:
            pid, uid, tty, command = process
            self.libc.printf(formatRow(str(pid), str(uid), "?" if tty < 0 else str(tty), "0:00", command, longFlag))

        return 0
