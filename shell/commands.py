from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, TypedDict

from stream import InputStream, OutputStream
from tokenizer import Token, TokenType


class CommandException(Exception):
    pass


class ArgType(Enum):
    FLAG = auto()
    ARG = auto()


class ArgOption(TypedDict):
    name: str
    flag: str
    longName: str
    type: ArgType


class ArgParser:
    def __init__(self, opts: List[ArgOption]):
        self.opts = opts
        self.flagDict: Dict[str, ArgOption] = {opt["flag"]: opt for opt in opts if "flag" in opt}
        self.longNameDict: Dict[str, ArgOption] = {opt["longName"]: opt for opt in opts if "longName" in opt}

    def parseArgs(self, args: List[Token], strictArgChecking: bool = True) -> tuple[Dict[str, str | bool], List[str]]:
        optDict: Dict[str, Any] = {}
        otherArgs: List[str] = []
        i = 0
        while i < len(args):
            arg = args[i]

            if arg is None:
                break
            elif arg.tokenType == TokenType.STRING:
                otherArgs.append(arg.value)
            elif arg.value.startswith("--"):
                longName = arg.value[2:]
                try:
                    opt = self.longNameDict[longName]
                except KeyError:
                    if strictArgChecking:
                        raise CommandException(f"invalid option: --{longName}") from None
                    else:
                        otherArgs.append(arg.value)
                        continue

                if opt["type"] == ArgType.FLAG:
                    optDict[opt["name"]] = True
                else:
                    try:
                        optDict[opt["name"]] = args[i + 1].value
                        i += 1
                    except IndexError:
                        raise CommandException(f"option --{longName} requires an argument") from None
            elif arg.value.startswith("-"):
                shortString = arg.value[1:]
                for index, flag in enumerate(shortString):
                    try:
                        opt = self.flagDict[flag]
                    except KeyError:
                        if strictArgChecking:
                            raise CommandException(f"invalid option: -{flag}") from None
                        else:
                            otherArgs.append(arg.value)
                            break

                    if opt["type"] == ArgType.FLAG:
                        optDict[opt["name"]] = True
                    else:
                        if index < len(shortString) - 1:
                            flagArg = shortString[index + 1:]
                        elif i < len(args) - 1:
                            flagArg = args[i + 1].value
                            i += 1
                        else:
                            raise CommandException(f"option -{flag} requires an argument")

                        optDict[opt["name"]] = flagArg
                        break
            else:
                otherArgs.append(arg.value)

            i += 1

        return optDict, otherArgs


class Command:
    name: str
    opts: List[ArgOption] = []
    strictArgChecking: bool = True

    optDict: Dict[str, str | bool]
    argv: List[str]

    def __init__(self, args: List[Token]):
        argParser = ArgParser(self.opts)

        try:
            self.optDict, self.argv = argParser.parseArgs(args, self.strictArgChecking)
        except CommandException as e:
            self.raiseException(e)

    def raiseException(self, message):
        raise CommandException(f"{self.name}: {message}") from None

    def getNamedArg(self, key, default) -> str:
        return self.optDict.get(key, default)

    def getIntNamedArg(self, key, default) -> int:
        return int(self.optDict.get(key, default))

    def getBoolNamedArg(self, key) -> bool:
        return bool(self.optDict.get(key, False))

    def getArg(self, index: int, default=None) -> str:
        try:
            return self.argv[index]
        except IndexError:
            if default:
                return default
            self.raiseException(f"expected {index + 1} arguments")

    def __str__(self):
        return f"<{self.name} {self.argv}, {self.optDict}>"

    def __repr__(self):
        return str(self)

    def run(self, stdin: InputStream, stdout: OutputStream, stderr: OutputStream) -> int:
        raise NotImplementedError()


class Cat(Command):
    name = "cat"
    opts = [{
        "name": "number", "flag": "n", "type": ArgType.FLAG
    }]

    def run(self, stdin, stdout, stderr):
        numberLines = self.getBoolNamedArg("number")

        if numberLines:
            for lineNum, line in enumerate(stdin):
                stdout.write(f"{(lineNum + 1): 6}\t{line}")
        else:
            for line in stdin:
                stdout.write(line)

        return 0


class Yes(Command):
    name = "yes"
    strictArgChecking = False

    def run(self, stdin, stdout, stderr):
        string = self.getArg(0, "y")
        while True:
            stdout.write(string)


class Head(Command):
    name = "head"
    opts = [{
        "name": "number", "flag": "n", "longName": "number", "type": ArgType.ARG
    }]

    def run(self, stdin, stdout, stderr):
        numLines = self.getIntNamedArg("number", 10)

        for i, line in enumerate(stdin):
            if i == numLines:
                break
            stdout.write(line)
        return 0


class Tail(Command):
    name = "tail"
    opts = [{
        "name": "number", "flag": "n", "longName": "number", "type": ArgType.ARG
    }]

    def run(self, stdin, stdout, stderr):
        numLines = self.getIntNamedArg("number", 10)

        lines = list(stdin)
        for line in lines[-numLines:]:
            stdout.write(line)
        return 0


class Rev(Command):
    name = "rev"

    def run(self, stdin, stdout, stderr):
        for x in stdin:
            stdout.write(x.rstrip("\n")[::-1] + "\n")
        return 0


class Sort(Command):
    name = "sort"
    opts = [{
        "name": "reverse", "flag": "r", "longName": "reverse", "type": ArgType.FLAG
    }, {
        "name": "unique", "flag": "u", "longName": "unique", "type": ArgType.FLAG
    }]

    def run(self, stdin, stdout, stderr):
        reverse = self.getBoolNamedArg("reverse")
        unique = self.getBoolNamedArg("unique")
        lines: List[str] = list(stdin)
        if unique:
            lines = sorted(set(lines), reverse=reverse)
        else:
            lines = sorted(lines, reverse=reverse)

        for line in lines:
            stdout.write(line)
        return 0
