import sys
from typing import Dict, Type

from process.process_code import ProcessCode
from usr.cat import Cat
from usr.echo import Echo
from usr.ls import Ls


class Sh(ProcessCode):
    def run(self):
        sys.stdin = open(0)
        while True:
            try:
                line = input("$ ")
            except KeyboardInterrupt:
                self.libc.printf("\n")
                continue
            except EOFError:
                self.libc.printf("\n")
                break

            if not line:
                continue

            tokens = line.split()
            command = tokens[0]
            args = tokens[1:]

            commandDict: Dict[str, Type[ProcessCode]] = {
                "ls": Ls,
                "cat": Cat,
                "echo": Echo,
            }

            if command in commandDict:
                pid = self.system.fork(commandDict[command], command, args)
                self.system.waitpid(pid)
            else:
                self.libc.printf("Invalid command\n")
