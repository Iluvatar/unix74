from environment import Environment
from shell import Shell
from stream import UserInputStream, TerminalOutputStream

variables = {
    "HOME": "/usr/aero",
    "PWD": "/usr/aero",
    "PATH": "/usr/local/bin:/usr/bin",
    "PS1": r"[\u@\h \W]\$ "
}

env = Environment(root, variables)

stdin = UserInputStream()
stdout = TerminalOutputStream()

shell = Shell(env, stdin, stdout)

try:
    shell.run()
except EOFError:
    print("exit")
