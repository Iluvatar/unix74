from typing import List, Iterator

from tokenizer import Token, TokenType


class Parser:
    @staticmethod
    def parseLine(tokens: Iterator[Token]) -> List[List[Token]]:
        commandStrings: List[List[Token]] = []
        currentCommand: List[Token] = []
        for token in tokens:
            if token.tokenType == TokenType.OPERATOR:
                if token.value == "|":
                    commandStrings.append(currentCommand)
                    currentCommand = []
                elif token.value == ";":
                    commandStrings.append(currentCommand)
                    currentCommand = []
                else:
                    currentCommand.append(token)
            else:
                currentCommand.append(token)

        if len(currentCommand) > 0:
            commandStrings.append(currentCommand)

        return commandStrings
