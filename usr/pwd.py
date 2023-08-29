from typing import List

from process.file_descriptor import FileMode
from process.process_code import ProcessCode


class Pwd(ProcessCode):
    def run(self) -> int:
        parts: List[str] = []
        while True:
            stat = self.system.stat(".")
            fd = self.system.open("..", FileMode.READ)
            siblings = self.system.getdents(fd)
            for entry in siblings:
                if entry.name in [".", ".."]:
                    continue
                if entry.iNumber.iNumber == stat.iNumber.iNumber:
                    parts.append(entry.name)
                    self.system.close(fd)
                    self.system.chdir("..")
                    break
            else:
                self.system.close(fd)
                break

        self.libc.printf("/" + "/".join(parts) + "\n")
        return 0
