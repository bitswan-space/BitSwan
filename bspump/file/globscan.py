import fnmatch
import glob
import logging
import os.path
import platform

#

L = logging.getLogger(__file__)

#


if platform.system() == "Windows":

    def _is_file_open(fname):
        # TODO: Provide implementation of _is_file_open() for Windows
        return False

else:

    def _is_file_open(fname):
        # TODO: Provide implementation of _is_file_open() for Linux
        # result = subprocess.run(['lsof', fname], stdout=subprocess.PIPE)
        # return len(result.stdout) != 0
        return False


def iter_files_glob(path, gauge, loop, exclude="", include=""):
    if path is None:
        return []
    if path == "":
        return []
    filelist = glob.glob(path, recursive=True)
    filelist.sort()

    # We clone the file list and send it to file_check which logs statistics about the files
    filelist_to_check = []
    filelist_to_check.extend(filelist)
    loop.call_soon_threadsafe(_file_check, filelist_to_check, gauge)

    for fname in filelist:
        if any(
            [
                fname.endswith("-locked"),
                fname.endswith("-failed"),
                fname.endswith("-processed"),
                not os.path.isfile(fname),
            ]
        ):
            continue

        if exclude != "":
            if fnmatch.fnmatch(fname, exclude):
                continue
        if include != "":
            if not fnmatch.fnmatch(fname, include):
                continue

        if _is_file_open(fname):
            continue
        yield fname
    return


def _glob_scan(path, gauge, loop, exclude="", include=""):
    try:
        return iter_files_glob(path, gauge, loop, exclude, include).__next__()
    except StopIteration:
        return None


def _file_check(filelist, gauge):
    file_count = {
        "processed": 0,
        "unprocessed": 0,
        "failed": 0,
        "locked": 0,
        "all_files": 0,
    }

    file_count["all_files"] += len(filelist)
    for file in filelist:
        if file.endswith("-locked"):
            file_count["locked"] += 1
            continue
        if file.endswith("-failed"):
            file_count["failed"] += 1
            continue
        if file.endswith("-processed"):
            file_count["processed"] += 1
            continue

        file_count["unprocessed"] += 1

    gauge.set("processed", file_count["processed"])
    gauge.set("failed", file_count["failed"])
    gauge.set("locked", file_count["locked"])
    gauge.set("unprocessed", file_count["unprocessed"])
    gauge.set("all_files", file_count["all_files"])


def test_iter_files_glob():
    class FakeGauge:
        def set(self, key, value):
            pass

    fake_gauge = FakeGauge()

    class FakeLoop:
        def call_soon_threadsafe(self, func, *args):
            func(*args)

    fake_loop = FakeLoop()
    filelist = list(
        iter_files_glob("bspump/test-data/globscan/*", fake_gauge, fake_loop)
    )
    assert len(filelist) == 3
    assert filelist[0] == "bspump/test-data/globscan/1"
    assert filelist[1] == "bspump/test-data/globscan/2"
    assert filelist[2] == "bspump/test-data/globscan/3"

    # test _glob_scan
    assert (
        _glob_scan("bspump/test-data/globscan/*", fake_gauge, fake_loop)
        == "bspump/test-data/globscan/1"
    )
