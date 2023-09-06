from filesystem.flags import FileType
from process.process_code import ProcessCode


class Mv(ProcessCode):
    @staticmethod
    def getParentAndFile(path: str) -> (str, str):
        try:
            lastSlash = path.rindex("/")
            return path[:lastSlash], path[lastSlash + 1:]
        except ValueError:
            return ".", path

    def run(self) -> int:
        if len(self.argv) != 2:
            return 1

        fromFile = self.argv[0]
        toFile = self.argv[1]

        try:
            fromStat = self.system.stat(fromFile)
        except FileNotFoundError:
            self.libc.printf("Source file is non-existent\n")
            return 1

        # TODO make dir mv work
        if fromStat.fileType == FileType.DIRECTORY:
            self.libc.printf("Can only move files")
            return 1

        try:
            toStat = self.system.stat(toFile)
            if toStat.fileType == FileType.DIRECTORY:
                _, newFileName = self.getParentAndFile(fromFile)
                parentDir = toFile
            else:
                parentDir, newFileName = self.getParentAndFile(toFile)
                self.system.unlink(toFile)
        except FileNotFoundError:
            parentDir, newFileName = self.getParentAndFile(toFile)

        try:
            self.system.stat(parentDir)
        except FileNotFoundError:
            self.libc.printf("No such file or directory")
            return 1

        self.system.link(fromFile, parentDir + "/" + newFileName)
        self.system.unlink(fromFile)
        return 0
