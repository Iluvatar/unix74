from process.process_code import ProcessCode
from user import UID


class Whoami(ProcessCode):
    def run(self) -> int:
        processUid = self.system.geteuid()

        passwdFd = self.libc.open("/etc/passwd")
        contents = self.libc.readAll(passwdFd)
        self.system.close(passwdFd)

        lines = contents.split("\n")
        for line in lines:
            parts = line.split(":")
            try:
                username, _, uid, _, _, _, _ = parts
                uid = UID(int(uid))
            except ValueError:
                continue
            if uid == processUid:
                self.libc.printf(username + "\n")
                return 0
        return 1
