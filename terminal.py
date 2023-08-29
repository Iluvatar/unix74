from typing import Dict, Type

from libc import Libc
from process.process import PID
from process.process_code import ProcessCode
from unix import SystemHandle, Unix
from usr.cat import Cat
from usr.ls import Ls
from usr.mv import Mv
from usr.ps import Ps
from usr.pwd import Pwd

variables = {
    "HOME": "/usr/aero",
    "PWD": "/usr/aero",
    "PATH": "/usr/local/usr:/usr/usr",
    "PS1": r"[\u@\h \W]\$ "
}

unix = Unix()
unix.startup()
# for p in unix.processes:
#     print(p)
shell = unix.processes[PID(1)]
system = SystemHandle(shell.pid, unix)
libc = Libc(system)

try:
    while True:
        # print(unix)
        # print(shell)

        try:
            i = input("$ ")
        except KeyboardInterrupt:
            libc.printf("\n")
            continue
        except EOFError:
            libc.printf("\n")
            break

        if not i:
            continue

        tokens = i.split()
        command = tokens[0]
        args = tokens[1:]

        try:
            commandDict: Dict[str, Type[ProcessCode]] = {
                "ls": Ls,
                "cat": Cat,
                "pwd": Pwd,
                "mv": Mv,
                "ps": Ps,
            }

            if command == "cd":
                path = "/"
                if len(args) > 0:
                    path = args[0]
                try:
                    system.chdir(path)
                except FileNotFoundError:
                    libc.printf(f"{path}: No such file or directory\n")
            elif command in commandDict:
                system.fork(commandDict[command], command, args)
            else:
                libc.printf(f"{command}: Command not found.\n")
        except PermissionError:
            libc.printf(f"sh: {command}: Operation not permitted\n")
except KeyboardInterrupt:
    libc.printf("\n")
    pass

# fd = handle.open("/usr/liz/note.txt", FileMode.READ)
# fd2 = handle.open("/usr/liz", FileMode.READ)

# print(handle.read(fd, 100))
# print(handle.read(fd, 100))
# handle.lseek(fd, -100, SeekFrom.END)
# print(handle.read(fd, 100))
