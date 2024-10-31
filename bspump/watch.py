# Watch the files for changes and restart if they changed
import os
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import signal

class Watcher:
    def __init__(self, files):
        self.files = files
        self.observer = Observer()
        self.event_handler = WatcherEventHandler(self)
        for file in files:
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
