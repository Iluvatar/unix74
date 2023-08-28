import datetime
from typing import Dict, List

from filesystem.filesystem import FileType, INode, Mode
from process.file_descriptor import FileMode
from process.process_code import ProcessCode
from user import GID, UID


class Ls(ProcessCode):
    def run(self) -> int:
        longFlag: bool = False
        groupFlag: bool = False
        timeFlag: bool = False
        showDotFlag: bool = False
        reverseFlag: bool = False
        inodeFlag: bool = False
        recursiveFlag: bool = False
        singleLineFlag: bool = False

        while len(self.argv):
            arg = self.argv[0]
            if arg[0] == "-":
                for char in arg[1:]:
                    if char == "l":
                        longFlag = True
                        singleLineFlag = True
                    elif char == "g":
                        groupFlag = True
                    elif char == "t":
                        timeFlag = True
                    elif char == "a":
                        showDotFlag = True
                    elif char == "r":
                        reverseFlag = True
                    elif char == "i":
                        inodeFlag = True
                    elif char == "R":
                        recursiveFlag = True
                    elif char == "1":
                        singleLineFlag = True
                    else:
                        continue
                self.argv = self.argv[1:]
            else:
                break

        paths: List[str] = ["."]
        if len(self.argv) > 0:
            paths = self.argv

        fileTypeChar = {
            FileType.REGULAR: "-",
            FileType.DIRECTORY: "d",
            FileType.CHARACTER: "c",
            FileType.LINK: "l",
            FileType.PIPE: "p"
        }

        def getUidToUserDict() -> Dict[UID, str]:
            userDict: Dict[UID, str] = {}
            passwdFd = self.system.open("/etc/passwd", FileMode.READ)
            contents = ""
            while len(data := self.system.read(passwdFd, 100)) > 0:
                contents += data
            self.system.close(passwdFd)
            lines = contents.split("\n")
            for line in lines:
                parts = line.split(":")
                try:
                    username, _, uid, _, _, _, _ = parts
                    uid = UID(int(uid))
                except ValueError:
                    continue
                if uid not in userDict:
                    userDict[uid] = username

            return userDict

        def getGidToGroupDict() -> Dict[GID, str]:
            groupDict: Dict[GID, str] = {}
            groupFd = self.system.open("/etc/group", FileMode.READ)
            contents = ""
            while len(data := self.system.read(groupFd, 100)) > 0:
                contents += data
            self.system.close(groupFd)
            lines = contents.split("\n")
            for line in lines:
                parts = line.split(":")
                try:
                    groupName, _, gid, _ = parts
                    gid = GID(int(gid))
                except ValueError:
                    continue
                groupDict[gid] = groupName

            return groupDict

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

        userDict = getUidToUserDict()
        groupDict = getGidToGroupDict()

        notFoundFiles: List[str] = []
        foundFiles: List[str] = []

        for index, path in enumerate(sorted(paths)):
            try:
                fd = self.system.open(path, FileMode.READ)
            except FileNotFoundError:
                notFoundFiles.append(f"{path} not found\n")
                continue

            entries = self.system.getdents(fd)
            self.system.close(fd)

            fullString: str = ""

            entryParts = []
            for entry in entries:
                name = entry.name
                inode = entry.inode

                permissions = permissionString(inode)
                links = str(inode.references)
                owner = userDict[inode.owner] if inode.owner in userDict else str(inode.owner)
                group = groupDict[inode.group] if inode.group in groupDict else str(inode.group)
                size = str(inode.data.size())
                modified = formatTime(inode.timeModified)
                entryParts.append({
                    "name": name,
                    "permissions": permissions,
                    "links": links,
                    "owner": owner,
                    "group": group,
                    "size": size,
                    "modifiedStr": modified,
                    "inode": str(inode.inumber),
                    "type": inode.fileType,
                    "modified": inode.timeModified,
                })

            if timeFlag:
                entryParts.sort(key=lambda e: e["modified"], reverse=not reverseFlag)
            else:
                entryParts.sort(key=lambda e: e["name"], reverse=reverseFlag)

            inodeLength = max([len(e["inode"]) for e in entryParts])
            linksLength = max([len(e["links"]) for e in entryParts])
            ownerLength = max([len(e["owner"]) for e in entryParts])
            groupLength = max([len(e["group"]) for e in entryParts])

            if len(paths) > 1:
                fullString += f"{path}:\n"

            for fileParts in entryParts:
                if fileParts["name"].startswith(".") and not showDotFlag:
                    continue

                lineString = ""
                if inodeFlag:
                    lineString += f"{fileParts['inode']: >{inodeLength}} "

                if longFlag:
                    lineString += f"{fileParts['permissions']} "
                    lineString += f"{fileParts['links']: >{linksLength}} "
                    lineString += f"{fileParts['owner']: <{ownerLength}}   "
                    if groupFlag:
                        lineString += f"{fileParts['group']: <{groupLength}}   "
                    lineString += f"{fileParts['modifiedStr']} "

                lineString += f"{fileParts['name']}"

                fullString += lineString + "\n"

            foundFiles.append(fullString)

        for entry in notFoundFiles:
            self.libc.printf(entry)

        for index, entry in enumerate(foundFiles):
            if len(notFoundFiles) > 0 or index > 0:
                self.libc.printf("\n")
            self.libc.printf(entry)

        return 0
