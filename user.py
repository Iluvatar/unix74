from dataclasses import dataclass
from typing import List


@dataclass
class Group:
    name: str
    password: str
    gid: int
    users: List[str]

    def __eq__(self, other):
        return self.gid == other.gid

    def __str__(self):
        return f"{self.name}:{self.password}:{self.gid}:{','.join(self.users)}"


@dataclass()
class User:
    name: str
    password: str
    uid: int
    gid: int
    info: str
    home: str
    shell: str

    def __str__(self):
        return f"{self.name}:{self.password}:{self.uid}:{self.gid}:{self.info}:{self.home}:{self.shell}"

    def __eq__(self, other):
        return self.uid == other.uid
