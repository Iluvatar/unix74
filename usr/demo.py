from process.process_code import ProcessCode


class Demo(ProcessCode):
    def run(self) -> int:
        op = 0
        self.system.exec("/bin/ls", ["-l"])
        print("error")
        return -1
