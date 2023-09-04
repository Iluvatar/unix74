import sys

from kernel.errors import Errno, SyscallError
from libc import LibcError
from process.process_code import ProcessCode
from user import UID


class Su(ProcessCode):
    def run(self) -> int:
        sys.stdin = open(0)

        name = "root"
        if len(self.argv) > 0:
            name = self.argv[0]

        try:
            passwdLine = self.libc.getPw(name)
        except LibcError:
            self.libc.printf(f"Unknown login: {name}\n")
            return 1
        parts = passwdLine.split(":")
        passHash = parts[1]

        self.libc.printf("Password: ")
        entered = self.libc.readline()
        enteredHash = self.libc.crypt(entered)

        if enteredHash != passHash:
            self.libc.printf("Sorry\n")
            return 1

        uid = UID(int(parts[2]))
        try:
            self.system.setuid(uid)
        except SyscallError as e:
            if e.errno == Errno.EPERM:
                self.libc.printf("Cannot set uid\n")
                return 1
            raise
        return 0
