from libc import Libc
from process.process import PID
from unix import SystemHandle, Unix
from usr.cat import Cat
from usr.ls import Ls

variables = {
    "HOME": "/usr/aero",
    "PWD": "/usr/aero",
    "PATH": "/usr/local/usr:/usr/usr",
    "PS1": r"[\u@\h \W]\$ "
}

# def ls(node: INode, indent: int = 0):
#     if node.fileType != FileType.DIRECTORY:
#         raise ValueError("can only handle directories")
#
#     if indent == 0:
#         print("/")
#
#     for name, child in sorted(cast(DirectoryData, node.data).children.items()):
#         print("    " * (indent + 1) + f"{name}", end="")
#         if child.fileType == FileType.DIRECTORY and not name.startswith("."):
#             print(" ↴")
#             ls(child, indent + 1)
#         else:
#             print()


unix = Unix()
unix.startup()
# for p in unix.processes:
#     print(p)
shell = unix.processes[PID(1)]
system = SystemHandle(shell.pid, unix)
libc = Libc(system)

Ls(system, libc, ["ls"]).run()
print()
Ls(system, libc, ["ls", "/"]).run()
print()
Ls(system, libc, ["ls", "/etc"]).run()
print()
Ls(system, libc, ["ls", "/dev"]).run()
print()
Ls(system, libc, ["ls", "/usr/liz"]).run()
print()

Cat(system, libc, ["cat", "/usr/liz/note.txt"]).run()

# fd = handle.open("/usr/liz/note.txt", FileMode.READ)
# fd2 = handle.open("/usr/liz", FileMode.READ)

# print(handle.read(fd, 100))
# print(handle.read(fd, 100))
# handle.lseek(fd, -100, SeekFrom.END)
# print(handle.read(fd, 100))
