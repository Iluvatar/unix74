from filesystem.filesystem import SpecialFileData


class DevNull(SpecialFileData):
    def read(self, size, offset):
        return ""

    def write(self, data, offset):
        pass

    def append(self, data):
        pass


class DevConsole(SpecialFileData):
    def read(self, size, offset):
        data = ""
        try:
            while True:
                data += input() + "\n"
                if len(data) >= size:
                    return data[:size]
        except EOFError:
            return data

    def write(self, data, offset):
        print(data)

    def append(self, data):
        print(data)
