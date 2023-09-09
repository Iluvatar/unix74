from __future__ import annotations

import sys
from enum import IntEnum
from typing import List, Tuple

from kernel.errors import Errno, SyscallError
from process.process_code import ProcessCode

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
    def processLine(self, line: str, lastCommand: str) -> Tuple[bool, str]:
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

    @staticmethod
    def makePs1(formatString: str) -> str:
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

    def findCommandPath(self, command: str) -> str | None:
        paths = self.libc.getenv("PATH")
        for path in paths.split(":"):
            fd = self.libc.open(path)
            dentries = self.system.getdents(fd)
            for dentry in dentries:
                if dentry.name == command:
                    return f"{path}/{command}"
        return None

    def run(self) -> int:
        sys.stdin = open(0)

        lastCommand: str = ""

        self.libc.setenv("PWD", self.libc.getenv("HOME"))

        for var in variables:
            self.libc.setenv(var, variables[var])

        while True:
            # self.system.debug__print()
            # self.system.debug__print_processes()

            try:
                ps1Format = self.libc.getenv("PS1") or "$ "
                ps1 = self.makePs1(ps1Format)
                line = input(ps1)
            except KeyboardInterrupt:
                self.libc.printf("\n")
                continue
            except EOFError:
                self.libc.printf("exit\n")
                line = "exit"

            reprint, processedLine = self.processLine(line, lastCommand)

            if not processedLine:
                continue

            tokens = tokenize(processedLine)
            command = tokens[0]
            args = tokens[1:]

            if reprint:
                self.libc.printf(processedLine + "\n")

            lastCommand = processedLine

            exitCode = 0
            if command == "cd":
                path = "/"
                if len(args) > 0:
                    path = args[0]
                try:
                    self.system.chdir(path)
                    self.libc.setenv("OLDPWD", self.libc.getenv("PWD"))
                except SyscallError as e:
                    if e.errno == Errno.ENOENT:
                        self.libc.printf(f"{path}: No such file or directory\n")
                        exitCode = 1
                    else:
                        self.libc.printf(f"{e}\n")
            elif command == "exit":
                if len(args) > 0:
                    exitCode = int(args[0])
                self.system.exit(exitCode)
            else:
                path = self.findCommandPath(command)
                if path is None:
                    self.libc.printf("Invalid command\n")
                    self.libc.setenv("?", str(ShellError.EXIT_ENOENT))
                    continue

                try:
                    pid = self.system.execve(path, args)
                    _, exitCode = self.system.waitpid(pid)
                except SyscallError as e:
                    if e.errno == Errno.EACCES:
                        self.libc.printf(f"{path}: Permission denied\n")
                        exitCode = ShellError.EXIT_CANNOT_INVOKE
                    elif e.errno == Errno.ENOEXEC:
                        self.libc.printf(f"{path}: Not an executable\n")
                        exitCode = ShellError.EXIT_CANNOT_INVOKE
                    elif e.errno == Errno.EINTR:
                        self.libc.printf(f"Segmentation fault: 11\n")
                        exitCode = 1
                    else:
                        print(e)
                        self.libc.printf(f"{path}: Error\n")
                        exitCode = ShellError.EXIT_CANCELED

            self.libc.setenv("?", str(exitCode))

        return 0
