from __future__ import annotations

from enum import Enum
from typing import Iterator


class TokenizerException(Exception):
    pass


class TokenType(Enum):
    ID = 1
    STRING = 2
    OPERATOR = 3


class Token:
    def __init__(self, tokenType: TokenType, value: str):
        self.tokenType = tokenType
        self.value = value

    def __str__(self):
        return f"[{self.tokenType}, '{self.value}']"

    def __repr__(self):
        return self.__str__()


class NaiveTokenizer:
    @staticmethod
    def isQuote(char: str) -> bool:
        return char == '"' or char == "'"

    @staticmethod
    def isOperator(char: str) -> bool:
        return char in "|<>&;"

    @staticmethod
    def isWhitespace(char: str) -> bool:
        return char == " "

    @staticmethod
    def tokenizeString(string: str) -> tuple[str, str]:
        if NaiveTokenizer.isQuote(string[0]):
            startQuote = string[0]
            string = string[1:]
        else:
            raise TokenizerException("Expected string to start with quote")

        out = ""
        escapeNext = False

        for i, c in enumerate(string):
            if escapeNext:
                if c != startQuote:
                    out += "\\"
                out += c
                escapeNext = False
            elif c == "\\":
                escapeNext = True
            elif c == startQuote:
                return out, string[i + 1:]
            else:
                out += c

        raise TokenizerException("Reached end of input while parsing string")

    @staticmethod
    def tokenizeOperator(string: str) -> tuple[str, str]:
        if not NaiveTokenizer.isOperator(string[0]):
            raise TokenizerException("Expected operator")

        out = ""
        for i, c in enumerate(string):
            if NaiveTokenizer.isOperator(c):
                out += c
            else:
                return out, string[i:]
        return out, ""

    @staticmethod
    def tokenizeOther(string: str) -> tuple[str, str]:
        if NaiveTokenizer.isQuote(string[0]):
            raise TokenizerException("Unexpected quote")
        elif NaiveTokenizer.isOperator(string[0]):
            raise TokenizerException("Unexpected operator")

        out = ""
        for i, c in enumerate(string):
            if NaiveTokenizer.isQuote(c) or NaiveTokenizer.isOperator(c) or NaiveTokenizer.isWhitespace(c):
                return out, string[i:]
            else:
                out += c
        return out, ""

    @staticmethod
    def eatWhitespace(string: str) -> tuple[str, str]:
        for i, c in enumerate(string):
            if NaiveTokenizer.isWhitespace(c):
                pass
            else:
                return "", string[i:]
        return "", ""

    @staticmethod
    def tokenize(string: str) -> Iterator[Token]:
        # special chars
        # | < > >> &
        while len(string):
            if NaiveTokenizer.isQuote(string[0]):
                out, string = NaiveTokenizer.tokenizeString(string)
                yield Token(TokenType.STRING, out)
            elif NaiveTokenizer.isOperator(string[0]):
                out, string = NaiveTokenizer.tokenizeOperator(string)
                yield Token(TokenType.OPERATOR, out)
            elif NaiveTokenizer.isWhitespace(string[0]):
                _, string = NaiveTokenizer.eatWhitespace(string)
            else:
                out, string = NaiveTokenizer.tokenizeOther(string)
                yield Token(TokenType.ID, out)
