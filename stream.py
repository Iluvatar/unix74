import os
import typing
from collections.abc import Generator


class StreamException(Exception):
    pass


class InputStream(typing.Protocol):
    def __iter__(self) -> Generator[str, None, None]:
        yield from self.read()

    def read(self) -> Generator[str, None, None]:
        pass

    def readline(self) -> str:
        pass

    def close(self) -> None:
        pass


class OutputStream(typing.Protocol):
    def write(self, line: str) -> None:
        pass

    def close(self) -> None:
        pass


class FileReaderStream(InputStream):
    def __init__(self, readerFd):
        self.readerFd = readerFd

    def read(self):
        with open(self.readerFd, closefd=False) as reader:
            yield from reader

    def readline(self):
        with open(self.readerFd, closefd=False) as reader:
            return reader.readline()

    def close(self):
        os.close(self.readerFd)


class FileWriterStream(OutputStream):
    def __init__(self, writerFd):
        self.writerFd = writerFd

    def write(self, line):
        with open(self.writerFd, "w", closefd=False) as writer:
            if not line.endswith("\n"):
                line += "\n"
            writer.write(line)


class UserInputStream(InputStream):
    def read(self):
        try:
            while True:
                yield input() + "\n"
        except EOFError:
            pass

    def readline(self):
        return input()


class TerminalOutputStream(OutputStream):
    def write(self, line):
        print(line, end="")


def makePipe():
    readerFd, writerFd = os.pipe()
    return FileReaderStream(readerFd), FileWriterStream(writerFd)
