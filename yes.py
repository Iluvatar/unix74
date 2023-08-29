import time

from process.process_code import ProcessCode


class Yes(ProcessCode):
    def run(self) -> int:
        string = "y"
        if len(self.argv) > 0:
            string = self.argv[0]

        try:
            while True:
                self.libc.printf(string + "\n")
                time.sleep(0.1)
        except EOFError:
            return 0
