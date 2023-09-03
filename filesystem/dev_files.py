from typing import List

from filesystem.filesystem import SpecialFileData


class DevNull(SpecialFileData):
    def read(self, size, offset):
        return ""


class DevConsole(SpecialFileData):
    def read(self, size, offset):
        data = ""
        try:
            data = input() + "\n"
            return data[:size]
        except EOFError:
            return data

    def write(self, data, offset):
        print(data)

    def append(self, data):
        print(data)


class Mem(SpecialFileData):
    def read(self, size, offset):
        lines: List[str] = []
        for process in self.unix.processes:
            lines.append(".".join([str(process.pid), str(process.uid), str(process.tty), process.command]))
        string = "\n".join(lines)
        return string[offset:offset + size]
