from process.process_code import ProcessCode
from user import UID


class Su(ProcessCode):
    def run(self) -> int:
        uid = UID(int(self.argv[0]))
        passwdLine = self.libc.getPw(uid)
        password = passwdLine.split(":")[1]
        passHash = self.libc.crypt(password)

        entered = self.libc.readline()
        enteredHash = self.libc.crypt(entered)

        return 1
