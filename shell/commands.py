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
