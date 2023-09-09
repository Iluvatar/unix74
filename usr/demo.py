from process.process_code import ProcessCode


class Demo(ProcessCode):
    def run(self) -> int:
        self.libc.printf(str(self.system.getuid()) + "\n")
        return 0
