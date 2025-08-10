# Watch the files for changes and restart if they changed
import os
import sys
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def get_imported_files():
    imported_files = set()

    for name, module in sys.modules.items():
        try:
            # Skip modules without __file__ attribute (like built-in modules)
            if hasattr(module, "__file__") and module.__file__:
                # Convert to absolute path and resolve any symlinks
                file_path = Path(module.__file__).resolve()

                # Only include .py files (skip .pyc, .pyd, .so files)
                if file_path.suffix == ".py":
                    if "site-packages" not in str(
                        file_path
                    ) and "lib/python" not in str(file_path):
                        imported_files.add(str(file_path))
        except (AttributeError, TypeError):
            continue

    return list(imported_files)


class Watcher:
    def __init__(self, files):
        self.files = files + get_imported_files()
        self.observer = Observer()
        self.event_handler = WatcherEventHandler(self)
        for file in self.files:
            self.observer.schedule(self.event_handler, file, recursive=False)
        self.observer.start()


class WatcherEventHandler(FileSystemEventHandler):
    def __init__(self, watcher):
        self.watcher = watcher

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path in self.watcher.files:
            # exec yourself with the same args
            os.execv(sys.argv[0], sys.argv)
