import asyncio
import logging
import os

import time

from .globscan import iter_files_glob
from ..abc.source import TriggerSource


L = logging.getLogger(__file__)


class FileABCSource(TriggerSource):
    """
    Description:

    """

    ConfigDefaults = {
        "path": "",
        "mode": "rb",
        "newline": os.linesep,
        "post": "move",  # one of 'delete', 'noop' and 'move'
        "exclude": "",  # glob of filenames that should be excluded (has precedence over 'include')
        "include": "",  # glob of filenames that should be included
        "encoding": "",
        "move_destination": "",  # destination folder for 'move'. Make sure it's outside of the glob search
        "lines_per_event": 10000,  # the number of lines after which the read method enters the idle state to allow other operations to perform their tasks
        "event_idle_time": 0.01,  # the time for which the read method enters the idle state (see above)
        "files_per_cycle": 1,
    }

    def __init__(self, app, pipeline, id=None, config=None):
        """
        Description:

        **Parameters**

        app : Application
                Name of the Application.

        pipeline : Pipeline
                Name of the Pipeline.

        id : ID, default = None
                ID

        config : JSON, default = None
                Configuration file with additional information.
                path : str (required)
                        Path to the file. Can be a glob pattern to select multiple files.
                mode : str, default = 'rb'
                        Mode in which the file is opened.
                newline : str, default = os.linesep
                        Newline character.
                post : str, default = 'move'
                        One of 'delete', 'noop' and 'move'.
                exclude : str, default = ''
                        Glob of filenames that should be excluded (has precedence over 'include').
                include : str, default = ''
                        Glob of filenames that should be included.
                encoding : str, default = ''
                        Encoding of the file.
                move_destination : str, default = ''
                        Destination folder for 'move'. Make sure it's outside of the glob search.
                lines_per_event : int, default = 10000
                        The number of lines after which the read method enters the idle state to allow other operations to perform their tasks.
                event_idle_time : float, default = 0.01
                        The time for which the read method enters the idle state (see above).
                files_per_cycle : int, default = 1
                        The number of files that are processed in one cycle.
        """
        super().__init__(app, pipeline, id=id, config=config)
        self.path = self.Config["path"]
        self.mode = self.Config["mode"]
        self.newline = self.Config["newline"]
        self.post = self.Config["post"]
        if self.post not in ["delete", "noop", "move"]:
            L.warning(
                "Incorrect/unknown 'post' configuration value '{}' - defaulting to 'move'".format(
                    self.post
                )
            )
            self.post = "move"
        self.include = self.Config["include"]
        self.exclude = self.Config["exclude"]
        conf_encoding = self.Config["encoding"]
        conf_encoding = self.Config["encoding"]
        self.files_per_cycle = self.Config["files_per_cycle"]
        if type(self.files_per_cycle) is not int:
            try:
                self.files_per_cycle = int(self.files_per_cycle)
            except ValueError:
                L.error(
                    "Incorrect 'files_per_cycle' configuration value '{}'".format(
                        self.files_per_cycle
                    )
                )
        self.encoding = conf_encoding if len(conf_encoding) > 0 else None

        self.MoveDestination = self.Config["move_destination"]

        if self.MoveDestination != "":
            if (self.post == "move") and (not os.path.isdir(self.MoveDestination)):
                os.makedirs(self.MoveDestination)
        else:
            self.MoveDestination = None

        metrics_service = app.get_service("asab.MetricsService")
        self.Gauge = metrics_service.create_gauge(
            "file_count",
            tags={
                "pipeline": pipeline.Id,
            },
            init_values={
                "processed": 0,
                "failed": 0,
                "locked": 0,
                "unprocessed": 0,
                "all_files": 0,
                "scan_time": 0.0,
            },
        )

        self.Loop = app.Loop
        self.ProactorService = app.get_service("asab.ProactorService")

        self.LinesCounter = 0
        self.LinesPerEvent = int(self.Config["lines_per_event"])
        self.EventIdleTime = float(self.Config["event_idle_time"])

    async def cycle(self):
        """
        Cycles through files that match the glob pattern.
        """
        filename = None

        start_time = time.time()
        filenames = []
        for path in self.path.split(os.pathsep):
            these_filenames = list(
                await self.ProactorService.execute(
                    iter_files_glob,
                    path,
                    self.Gauge,
                    self.Loop,
                    self.exclude,
                    self.include,
                )
            )
            filenames.extend(these_filenames)
            if len(filenames) >= self.files_per_cycle:
                break
        end_time = time.time()
        self.Gauge.set("scan_time", end_time - start_time)

        if len(filenames) == 0:
            self.Pipeline.PubSub.publish("bspump.file_source.no_files!")
            return  # No file to read

        await self.Pipeline.ready()
        for filename in filenames[: self.files_per_cycle]:
            await self.lock_and_read_file(filename)

    async def lock_and_read_file(self, filename):
        # Lock the file
        L.debug("Locking file '{}'".format(filename))
        locked_filename = filename + "-locked"
        try:
            os.rename(filename, locked_filename)
        except FileNotFoundError:
            return
        except (OSError, PermissionError):  # OSError - UNIX, PermissionError - Windows
            L.exception(
                "Error when locking the file '{}'  - will try again".format(filename)
            )
            return
        except BaseException as e:
            L.exception("Error when locking the file '{}'".format(filename))
            self.Pipeline.set_error(None, None, e)
            return

        try:
            if filename.endswith(".gz"):
                import gzip

                f = gzip.open(locked_filename, self.mode, encoding=self.encoding)

            elif filename.endswith(".bz2"):
                import bz2

                f = bz2.open(locked_filename, self.mode, encoding=self.encoding)

            elif filename.endswith(".xz") or filename.endswith(".lzma"):
                import lzma

                f = lzma.open(locked_filename, self.mode, encoding=self.encoding)

            else:
                if "b" in self.mode:  # Binary mode doesn't take a newline argument
                    self.newline = None
                f = open(
                    locked_filename,
                    self.mode,
                    newline=self.newline,
                    encoding=self.encoding,
                )

        except (OSError, PermissionError):  # OSError - UNIX, PermissionError - Windows
            L.exception(
                "Error when opening the file '{}' - will try again".format(filename)
            )
            return
        except BaseException as e:
            L.exception("Error when opening the file '{}'".format(filename))
            self.Pipeline.set_error(None, None, e)
            return

        L.debug("Processing file '{}'".format(filename))

        try:
            await self.read(filename, f)
        except Exception:
            try:
                if self.post == "noop":
                    # When we should stop, rename file back to original
                    os.rename(locked_filename, filename)
                else:
                    # Otherwise rename to ...-failed and continue processing
                    os.rename(locked_filename, filename + "-failed")
            except BaseException:
                L.exception(
                    "Error when renaming the file '{}'  - will try again".format(
                        filename
                    )
                )
            return
        finally:
            f.close()

        L.debug("File '{}' processed {}".format(filename, "succefully"))

        # Finalize
        try:
            if self.post == "delete":
                os.unlink(locked_filename)
            elif self.post == "noop":
                os.rename(locked_filename, filename)
            else:
                if self.MoveDestination is not None:
                    file_from = os.path.abspath(locked_filename)
                    base = os.path.basename(filename)
                    file_to = os.path.abspath(
                        os.path.join(self.MoveDestination, base + "-processed")
                    )
                else:
                    file_from = locked_filename
                    file_to = filename + "-processed"

                os.rename(file_from, file_to)
        except (OSError, PermissionError):  # OSError - UNIX, PermissionError - Windows
            L.exception(
                "Error when finalizing the file '{}' - will try again".format(filename)
            )
            return
        except BaseException as e:
            L.exception("Error when finalizing the file '{}'".format(filename))
            self.Pipeline.set_error(None, None, e)
            return

    async def simulate_event(self):
        """
        The simulate_event method should be called in read method after a file line has been processed.

        It ensures that all other asynchronous events receive enough time to perform their tasks.
        Otherwise, the application loop is blocked by a file reader and no other activity makes a progress.

        """
        self.LinesCounter += 1
        if self.LinesCounter >= self.LinesPerEvent:
            await asyncio.sleep(self.EventIdleTime)
            self.LinesCounter = 0

    async def read(self, filename, f):
        """
        Description: Override this method to implement your File Source.
        `f` is an opened file object.

        **Parameters**

        filename : file
                Name of the file.

        f :

        """
        raise NotImplementedError()


try:
    import pytest

    @staticmethod
    @pytest.mark.asyncio
    async def test_file_abc_source():
        await run_file_abc_source(
            "move",
            ["1-processed", "2-processed", "3", "4-locked", "5-failed", "6-processed"],
        )
        await run_file_abc_source(
            "noop", ["1", "2", "3", "4-locked", "5-failed", "6-processed"]
        )
        await run_file_abc_source(
            "delete", ["3", "4-locked", "5-failed", "6-processed"]
        )

    async def run_file_abc_source(post, expected_resultant_files):
        read_files = []

        class TestFileABCSource(FileABCSource):
            async def read(self, filename, f):
                read_files.append(filename)

        # Copy test files to temp dir
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        # copy globscan test data ("bspump/test-data/globscan/") to temp dir
        shutil.copytree(
            os.path.join(os.path.dirname(__file__), "..", "test-data", "globscan"),
            os.path.join(temp_dir, "globscan"),
        )

        class FakePipeline:
            def __init__(self):
                self.Id = "FakePipeline"
                self.Loop = asyncio.get_event_loop()

                class FakePubSub:
                    def publish(self, *args, **kwargs):
                        pass

                self.PubSub = FakePubSub()

            async def ready(self):
                pass

            def get_service(self, *args, **kwargs):
                class FakeService:
                    def create_gauge(self, *args, **kwargs):
                        class FakeGauge:
                            def set(self, *args, **kwargs):
                                pass

                        return FakeGauge()

                    async def execute(self, fn, *args, **kwargs):
                        return fn(*args, **kwargs)

                return FakeService()

        testfilesource = TestFileABCSource(
            app=FakePipeline(),
            config={
                "path": os.path.join(temp_dir, "globscan", "*"),
                "files_per_cycle": "2",
                "post": post,
            },
            pipeline=FakePipeline(),
        )
        await testfilesource.cycle()
        assert len(read_files) == 2
        assert read_files[0] == os.path.join(temp_dir, "globscan", "1")
        assert read_files[1] == os.path.join(temp_dir, "globscan", "2")
        # Make sure that the files have been renamed as being processed
        # Get file listing and compare for easy debugging
        assert sorted(os.listdir(os.path.join(temp_dir, "globscan"))) == sorted(
            expected_resultant_files
        )

except ImportError:
    pass
