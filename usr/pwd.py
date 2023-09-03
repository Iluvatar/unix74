from typing import List

from kernel.errors import SyscallError
from process.file_descriptor import OpenFlags
from process.process_code import ProcessCode


class Pwd(ProcessCode):
    def run(self) -> int:
        parts: List[str] = []
        while True:
            childStat = self.system.stat(".")
            parentStat = self.system.stat("..")
            parentFd = self.system.open("..", OpenFlags.READ)
            siblings = self.system.getdents(parentFd)

            useStat = childStat.filesystemId != parentStat.filesystemId

            for entry in siblings:
                if entry.name in [".", ".."]:
                    continue

                iNumber = entry.iNumber

                if useStat:
                    try:
                        siblingStat = self.system.stat(f"../{entry.name}")
                        if siblingStat.filesystemId != childStat.filesystemId:
                            continue
                        iNumber = siblingStat.iNumber
                    except SyscallError:
                        continue

                if iNumber == childStat.iNumber:
                    parts.append(entry.name)
                    self.system.close(parentFd)
                    self.system.chdir("..")
                    break
            else:
                self.system.close(parentFd)
                break

        self.libc.printf("/" + "/".join(parts) + "\n")
        return 0
