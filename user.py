from dataclasses import dataclass
from typing import List, NewType

UID = NewType("UID", int)
GID = NewType("GID", int)
UserName = NewType("UserName", str)
Password = NewType("Password", str)
GroupName = NewType("GroupName", str)
GroupPassword = NewType("GroupPassword", str)


@dataclass()
class User:
    name: UserName
    password: Password
    uid: UID
    gid: GID
    info: str
    home: str
    shell: str

    def __eq__(self, other):
        return self.uid == other.uid

    def __str__(self):
        return f"{self.name}:{self.password}:{self.uid}:{self.gid}:{self.info}:{self.home}:{self.shell}"


@dataclass
class Group:
    name: GroupName
    password: GroupPassword
    gid: GID
    users: List[UserName]

    def __eq__(self, other):
        return self.gid == other.gid

    def __str__(self):
        return f"{self.name}:{self.password}:{self.gid}:{','.join(self.users)}"
