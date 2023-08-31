from __future__ import annotations

from typing import Dict


class Environment:
    def __init__(self, variables=None):
        if variables is None:
            variables = {}
        self.variables: Dict[str, str] = variables

    def getVar(self, name: str) -> str:
        return self.variables.get(name, "")

    def setVar(self, name: str, val: str) -> None:
        self.variables[name] = val

    def copy(self) -> Environment:
        return Environment(self.variables.copy())
