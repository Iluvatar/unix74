from collections import defaultdict
from datetime import datetime
from typing import DefaultDict

from file import INode, FilePermissions, INodeDirectory, DevNull, INodeFile, DevConsole

origTime = datetime(1977, 10, 17, 10, 14, 27, 387)

users: DefaultDict[str, int] = defaultdict(lambda: 6, {
    "root": 0,
    "aero": 128
})

groups: DefaultDict[str, int] = defaultdict(lambda: 6, {
    "root": 0,
    "aero": 128
})


def makeRoot():
    root = INodeDirectory(None, "", FilePermissions(755), users["root"], groups["root"], origTime, origTime)
    root.parent = root

    binDir = INodeDirectory(root, "bin", FilePermissions(755), users["root"], groups["wheel"], origTime, origTime)
    usrDir = INodeDirectory(root, "usr", FilePermissions(755), users["root"], groups["wheel"], origTime, origTime)
    varDir = INodeDirectory(root, "var", FilePermissions(755), users["root"], groups["wheel"], origTime, origTime)

    aeroHomeDir = INode(usrDir, "aero", FilePermissions(755), users["aero"], groups["aero"], origTime, origTime)

    usrDir.addChild(aeroHomeDir)
    root.setChildren({binDir, usrDir, varDir})

    return root


def makeDev():
    dev = INodeDirectory(None, "dev", FilePermissions(755), users["root"], users["root"], origTime, origTime)
    dev.parent = dev

    null = INodeFile(dev, "null", FilePermissions(666), users["root"], groups["root"], origTime, origTime, DevNull())
    console = INodeFile(dev, "console", FilePermissions(666), users["root"], groups["root"], origTime, origTime,
                        DevConsole())

    dev.setChildren({null, console})
    return dev
