import json
import os
import sys
import tempfile

from bspump.jupyter import *  # noqa: F403
import bspump.jupyter
from bspump.notebook_compiler import NotebookCompiler

config = None
__bitswan_dev = False
__bs_step_locals = {}


def main():
    app = App()  # noqa: F405
    compiler = NotebookCompiler()

    if app.Test:
        bspump.jupyter.bitswan_test_mode.append(True)

    with tempfile.TemporaryDirectory() as tmpdirname:
        if os.path.exists(app.Notebook):
            with open(app.Notebook) as nb:
                notebook = json.load(nb)
                compiler.compile_notebook(
                    notebook, out_path=f"{tmpdirname}/autopipeline_tmp.py"
                )
                sys.path.insert(0, tmpdirname)
                tmp_module = __import__("autopipeline_tmp")  # noqa: F841
        else:
            print(f"Notebook {app.Notebook} not found")

        if bspump.jupyter.bitswan_auto_pipeline.get("sink") is not None:
            register_sink(  # noqa: F405
                bspump.jupyter.bitswan_auto_pipeline.get("sink")
            )  # noqa: F405
            end_pipeline()  # noqa: F405

        app.init_componets()
        app.run()


if __name__ == "__main__":
    main()
