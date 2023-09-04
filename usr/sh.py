import sys
from enum import IntEnum
from typing import Dict, List, Tuple, Type

from kernel.errors import SyscallError
from process.process_code import ProcessCode
from usr.cat import Cat
from usr.echo import Echo
from usr.ln import Ln
from usr.ls import Ls
from usr.ps import Ps
from usr.pwd import Pwd
from usr.rm import Rm
from usr.su import Su

variables = {
    "HOME": "/usr/liz",
    "PATH": "/etc:/bin:/usr:.",
    "PS1": r"[\u@\h \W]\$ ",
    "?": "0",
}


class ShellError(IntEnum):
    EXIT_TIMEDOUT = 124,  # Time expired before child completed.
    EXIT_CANCELED = 125,  # Internal error prior to exec attempt.
    EXIT_CANNOT_INVOKE = 126,  # Program located, but not usable.
    EXIT_ENOENT = 127  # Could not find program to exec.


def tokenize(string: str) -> List[str]:
    return string.split()


class Sh(ProcessCode):
    def run(self) -> int:
        sys.stdin = open(0)

        # self.system.setuid(UID(128))

        lastCommand: str = ""

        def processLine(line: str) -> Tuple[bool, str]:
            tokens: List[str] = tokenize(line)

            needReprint: bool = False
            processedTokens: List[str] = []
            for token in tokens:
                if token[0] == "$":
                    processedTokens.append(self.libc.getenv(token[1:]))
                elif token == "!!":
                    processedTokens.append(lastCommand)
                    needReprint = True
                else:
                    processedTokens.append(token)
            return needReprint, " ".join(processedTokens)

        def makePs1(formatString: str):
            def escape(c: str):
                if c == "\\" or c == "$":
                    return c
                elif c == "u":
                    return "liz"
                elif c == "h":
                    return "pokey"
                elif c == "W":
                    return "/"
                else:
                    return c

            formattedString = ""
            i = 0
            while i < len(formatString):
                char = formatString[i]
                if char == "\\":
                    if i < len(formatString) - 1:
                        formattedString += escape(formatString[i + 1])
                    else:
                        formattedString += "\\"
                    i += 1
                else:
                    formattedString += char
                i += 1

            return formattedString

        # self.libc.setenv("PWD", self.libc.pwd())

        for var in variables:
            self.libc.setenv(var, variables[var])

        while True:
            # self.system.debug__print()
            # self.system.debug__print_processes()

            try:
                ps1Format = self.libc.getenv("PS1") or "$ "
                ps1 = makePs1(ps1Format)
                line = input(ps1)
            except KeyboardInterrupt:
                self.libc.printf("\n")
                continue
            except EOFError:
                self.libc.printf("\n")
                break

            reprint, processedLine = processLine(line)

            if not processedLine:
                continue

            tokens = tokenize(processedLine)
            command = tokens[0]
            args = tokens[1:]

            if reprint:
                self.libc.printf(processedLine + "\n")

            lastCommand = processedLine

            commandDict: Dict[str, Type[ProcessCode]] = {
                "cat": Cat,
                "echo": Echo,
                "ls": Ls,
                "pwd": Pwd,
                "ps": Ps,
                "su": Su,
                "ln": Ln,
                "rm": Rm,
            }

            if command == "cd":
                path = "/"
                if len(args) > 0:
                    path = args[0]
                try:
                    self.system.chdir(path)
                    self.libc.setenv("OLDPWD", self.libc.getenv("PWD"))
                except SyscallError as e:
                    self.libc.printf(f"{e}\n")
            elif command in commandDict:
                pid = self.system.fork(commandDict[command], command, args)
                _, exitCode = self.system.waitpid(pid)
                self.libc.setenv("?", str(exitCode))
            else:
                self.libc.printf("Invalid command\n")
                self.libc.setenv("?", str(ShellError.EXIT_ENOENT))

        return 0
