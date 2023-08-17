from dataclasses import dataclass, field
from typing import List, MutableSet, Dict

from environment import Environment
from file import INodeDirectory, INodeException, INodeFile
from user import User


class KernelError(Exception):
    pass


@dataclass
class Process:
    pid: int
    parent: 'Process'
    command: str
    owner: int
    env: Environment
    children: MutableSet['Process'] = field(default_factory=set)

    def __hash__(self):
        return self.pid

    def __eq__(self, other):
        return self.pid == other.pid

    def makeChild(self, childPid: int, command: str):
        child = Process(childPid, self, command, self.owner, self.env.copy())
        self.children.add(child)
        return child

    def kill(self):
        self.parent.children.remove(self)


class Unix:
    def __init__(self):
        self.mounts: Dict[str, INodeDirectory] = {}
        self.rootUser: User = User("root", "", 0, 0, "root", "/", "/bin/sh")
        self.processes: MutableSet[int, Process] = set()

    @staticmethod
    def getUsers(etcPasswd: INodeFile):
        def parsePasswd(userString: str):
            fields = userString.split(":")
            try:
                name, password, uid, gid, info, home, shell = fields
                uid = int(uid)
                gid = int(gid)
            except ValueError:
                return None

            return User(name, password, uid, gid, info, home, shell)

        users: List[User] = []
        for line in etcPasswd.file.read():
            user = parsePasswd(line)
            if not user:
                continue
            users.append(user)
        return users

    def getRootMount(self) -> INodeDirectory:
        try:
            return self.mounts["/"]
        except KeyError:
            raise KernelError("No root mount") from None

    def startup(self, filesystem: INodeDirectory):
        try:
            etcPasswd = filesystem.getINodeFromRelativePath("/etc/passwd")
        except INodeException:
            raise KernelError("Cannot find passwd file") from None

        swapper = Process(0, None, "swapper", self.rootUser.uid, Environment())
        swapper.parent = swapper
        init = swapper.makeChild(1, "init")
