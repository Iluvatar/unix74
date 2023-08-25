import datetime

from filesystem.filesystem import FileType, INode, Mode
from process.file_descriptor import FileMode
from process.user_process import UserProcess


class Ls(UserProcess):
    def run(self) -> int:
        if len(self.argv) < 2:
            path = "."
        else:
            path = self.argv[1]
        fd = self.system.open(path, FileMode.READ)
        entries = self.system.getdents(fd)

        fileTypeChar = {
            FileType.REGULAR: "-",
            FileType.DIRECTORY: "d",
            FileType.CHARACTER: "c",
            FileType.LINK: "l",
            FileType.PIPE: "p"
        }

        def permissionString(inode: INode) -> str:
            def modeToString(mode: Mode) -> str:
                r = "r" if Mode.READ in mode else "-"
                w = "w" if Mode.WRITE in mode else "-"
                x = "x" if Mode.EXEC in mode else "-"
                return f"{r}{w}{x}"

            fileTypeStr = fileTypeChar[inode.fileType]
            ownerStr = modeToString(inode.permissions.owner)
            groupStr = modeToString(inode.permissions.group)
            otherStr = modeToString(inode.permissions.other)
            return f"{fileTypeStr}{ownerStr}{groupStr}{otherStr}"

        def formatTime(time: datetime.datetime) -> str:
            date = f"{time.strftime('%b')} {time.day: >2}"
            now = datetime.datetime.now()
            if now.year == time.year:
                timeStr = time.strftime("%H:%M")
                return f"{date} {timeStr}"
            else:
                return f"{date} {time.year: >5}"

        entryParts = []
        strLengths = [0] * 7
        for entry in entries:
            inode = entry.inode
            permissions = permissionString(inode)
            links = str(inode.references)
            owner = str(inode.owner)
            group = str(inode.group)
            size = str(inode.data.size())
            modified = formatTime(inode.timeModified)
            name = entry.name
            entryParts.append((permissions, links, owner, group, size, modified, name))
            strLengths[0] = max(len(permissions), strLengths[0])
            strLengths[1] = max(len(links), strLengths[1])
            strLengths[2] = max(len(owner), strLengths[2])
            strLengths[3] = max(len(group), strLengths[3])
            strLengths[4] = max(len(size), strLengths[4])
            strLengths[5] = max(len(modified), strLengths[5])
            strLengths[6] = max(len(name), strLengths[6])

        entryParts.sort(key=lambda x: x[6])

        for fileParts in entryParts:
            permissions, links, owner, group, size, modified, name = fileParts
            line = f"{permissions: >{strLengths[0]}} {links: >{strLengths[1]}} {owner: <{strLengths[2]}} {group: <{strLengths[3]}} {size: >{strLengths[4]}} {modified: <{strLengths[5]}} {name: <{strLengths[6]}}"
            self.libc.printf(line)

        return 0
