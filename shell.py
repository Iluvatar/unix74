import concurrent.futures
import os
from collections.abc import Callable
from typing import List, Dict

from commands import Command
from environment import Environment, INode, NoSuchFileException
from parser import Parser
from shell_commands import ShellCommand, Ls, Cd
from stream import InputStream, OutputStream, makePipe
from tokenizer import NaiveTokenizer, Token


# allCommands: List[Type[Command]] = [Cat, Rev, Yes, Head, Tail, Sort]
# commandLookup: Dict[str, Type[Command]] = {command.name: command for command in allCommands}


class BashException(Exception):
    pass


class Shell:
    SHELL_COMMANDS: List[ShellCommand] = [Ls, Cd]

    environment: Environment
    currentDir: INode

    def __init__(self, environment: Environment, stdin: InputStream, stdout: OutputStream):
        self.environment = environment
        self.stdin = stdin
        self.stdout = stdout
        self.currentDir = self.getINodeFromPath(self.environment.getVar("HOME"))
        self.shellCommands: Dict[str, ShellCommand] = {cmd.name: cmd for cmd in Shell.SHELL_COMMANDS}

    def formatPs1(self, ps1):
        ps1 = ps1.replace(r"\h", "hostname")
        ps1 = ps1.replace(r"\t", "time")
        ps1 = ps1.replace(r"\u", "aero")
        ps1 = ps1.replace(r"\W", self.environment.getVar("PWD"))
        ps1 = ps1.replace(r"\$", "$")
        return ps1

    def getINodeFromPath(self, path: str) -> INode:
        if path.startswith("/"):
            startNode: INode = self.environment.filesystem
        else:
            startNode: INode = self.currentDir

        return startNode.getINodeFromRelativePath(path)

    def findCommand(self, name):
        if name in self.shellCommands:
            return self.shellCommands[name]

        searchPaths = self.environment.getVar("PATH").split(":")
        for path in searchPaths:
            file = os.path.join(path, name)
            try:
                command = self.getINodeFromPath(file)
                return command
            except NoSuchFileException:
                continue
        else:
            raise BashException("command not found")

    def makeCommand(self, tokens: List[Token]) -> Command:
        if len(tokens) == 0:
            raise BashException()

        commandName = tokens[0].value
        commandArgs = tokens[1:]
        command = commandLookup[commandName]
        return command(commandArgs)

    @staticmethod
    def composeCommands(commands: List[Command]) -> Callable[[InputStream, OutputStream, OutputStream], int]:

        def f(stdin: InputStream, stdout: OutputStream, stderr: OutputStream) -> int:
            if len(commands) == 0:
                return 0

            if len(commands) == 1:
                return commands[0].run(stdin, stdout, stderr)

            pipes = [makePipe() for _ in range(len(commands) - 1)]
            threads = []

            def runAndClose(command, cin, cout, stderr):
                ret = command.run(cin, cout, stderr)
                cin.close()
                cout.close()
                return ret

            with concurrent.futures.ThreadPoolExecutor() as executor:
                for index, command in enumerate(commands):
                    cin: InputStream = stdin if index == 0 else pipes[index - 1][0]
                    cout: OutputStream = stdout if index == len(commands) - 1 else pipes[index][1]
                    threads.append(executor.submit(runAndClose, command, cin, cout, stderr))

            results = [thread.result() for thread in threads]
            return results[-1]

        return f

    def doCommand(self, command):
        tokens = NaiveTokenizer.tokenize(command)
        commandStrings = Parser.parseLine(tokens)
        commands = [self.makeCommand(string) for string in commandStrings]
        finalCommand = Shell.composeCommands(commands)

        return finalCommand(self.stdin, self.stdout, self.stdout)

    def run(self):
        while True:
            self.stdout.write(self.formatPs1(self.environment.getVar("PS1")))
            self.doCommand(input())
