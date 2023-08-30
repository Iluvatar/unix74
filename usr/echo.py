from process.process_code import ProcessCode


class Echo(ProcessCode):
    def run(self) -> int:
        self.libc.printf(" ".join(self.argv) + "\n")
        return 0
