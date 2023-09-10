from time import sleep

from process.process_code import ProcessCode


class Swapper(ProcessCode):
    def run(self):
        while True:
            sleep(1000)
