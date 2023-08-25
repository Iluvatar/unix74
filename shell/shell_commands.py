from abc import ABC
from typing import List

from commands import ArgType, Command
from shell import Shell
from tokenizer import Token


class ShellCommand(Command, ABC):
    def __init__(self, args: List[Token], shell: Shell):
        super().__init__(args)
        self.shell = shell


class Ls(ShellCommand):
    name = "ls"
    opts = [{
        "name": "long",
        "flag": "l",
        "type": ArgType.FLAG
    }, {
        "name": "hidden",
        "flag": "a",
        "type": ArgType.FLAG
    }, {
        "name": "dirslash",
        "flag": "p",
        "type": ArgType.FLAG
    }]

    def run(self, stdin, stdout, stderr):
        children = sorted(self.shell.currentDir.getChildren(), key=lambda i: i["name"])
        for child in children:
            stdout.write(child["name"])


class Cd(ShellCommand):
    name = "cd"
    strictArgChecking = False

    def run(self, stdin, stdout, stderr):
        if len(self.argv) == 0:
            self.shell.currentDir = self.shell.getINodeFromPath(self.shell.environment.getVar("HOME"))
        elif self.argv[0] == "-":
            # self.shell.environment
            pass
        else:
            try:
                self.shell.getINodeFromPath(self.argv[0])
            except INodeException:
                yield
