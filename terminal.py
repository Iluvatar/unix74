from threading import Thread

from kernel.unix import Unix

if __name__ == "__main__":
    unix = Unix()

    kernel = Thread(target=unix.start)
    kernel.start()

    unix.startup()
