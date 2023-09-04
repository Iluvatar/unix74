import datetime
from typing import Dict, List

from filesystem.filesystem import FileType, Mode, SetId
from filesystem.filesystem_utils import Stat
from kernel.errors import SyscallError
from process.file_descriptor import OpenFlags
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
            passwdFd = self.system.open("/etc/passwd", OpenFlags.READ)
            contents = self.libc.readAll(passwdFd)
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
            groupFd = self.system.open("/etc/group", OpenFlags.READ)
            contents = self.libc.readAll(groupFd)
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

        def permissionString(stat: Stat) -> str:
            perms = stat.permissions

            s = fileTypeChar.get(stat.fileType, "?")
            s += "r" if perms.owner & Mode.READ else "-"
            s += "w" if perms.owner & Mode.WRITE else "-"
            s += "s" if perms.high & SetId.SET_UID else "x" if perms.owner & Mode.EXEC else "-"
            s += "r" if perms.group & Mode.READ else "-"
            s += "w" if perms.group & Mode.WRITE else "-"
            s += "s" if perms.high & SetId.SET_GID else "x" if perms.group & Mode.EXEC else "-"
            s += "r" if perms.other & Mode.READ else "-"
            s += "w" if perms.other & Mode.WRITE else "-"
            s += "t" if perms.high & SetId.STICKY else "x" if perms.other & Mode.EXEC else "-"

            return s

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
                fd = self.system.open(path, OpenFlags.READ)
            except SyscallError:
                notFoundFiles.append(f"{path} not found\n")
                continue

            entries = self.system.getdents(fd)
            self.system.close(fd)

            fullString: str = ""

            entryParts = []
            for entry in entries:
                name = entry.name
                stat = self.system.stat(path + "/" + name)

                permissions = permissionString(stat)
                links = str(stat.references)
                owner = userDict[stat.owner] if stat.owner in userDict else str(stat.owner)
                group = groupDict[stat.group] if stat.group in groupDict else str(stat.group)
                size = str(stat.size)
                modified = formatTime(stat.timeModified)
                iNumber = str(stat.iNumber)
                entryParts.append({
                    "name": name,
                    "permissions": permissions,
                    "links": links,
                    "owner": owner,
                    "group": group,
                    "size": size,
                    "modifiedStr": modified,
                    "iNumber": iNumber,
                    "type": stat.fileType,
                    "modified": stat.timeModified,
                })

            if timeFlag:
                entryParts.sort(key=lambda e: e["modified"], reverse=not reverseFlag)
            else:
                entryParts.sort(key=lambda e: e["name"], reverse=reverseFlag)

            iNumberLength = max([len(e["iNumber"]) for e in entryParts], default=0)
            linksLength = max([len(e["links"]) for e in entryParts], default=0)
            ownerLength = max([len(e["owner"]) for e in entryParts], default=0)
            groupLength = max([len(e["group"]) for e in entryParts], default=0)

            if len(paths) > 1:
                fullString += f"{path}:\n"

            for fileParts in entryParts:
                if fileParts["name"].startswith(".") and not showDotFlag:
                    continue

                lineString = ""
                if inodeFlag:
                    lineString += f"{fileParts['iNumber']: >{iNumberLength}} "

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
