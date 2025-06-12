import json
import os
import ast
import sys
import tempfile
import re

from bspump.jupyter import *  # noqa: F403
import bspump.jupyter

config = None
__bitswan_dev = False
__bs_step_locals = {}


def contains_function_call(ast_tree, function_name):
    for node in ast.walk(ast_tree):
        if isinstance(node, ast.Call):  # Check if the node is a function call
            if isinstance(node.func, ast.Name) and node.func.id == function_name:
                return True
    return False


def indent_code(lines: list[str]) -> list[str]:
    multiline = False
    double_quotes = False
    indent_lines = []
    lines_out = []
    for i, line in enumerate(lines):
        if not multiline and line.strip(" ") != "":
            indent_lines.append(i)
        if '"""' in line or "'''" in line:
            if not multiline:
                double_quotes = '"""' in line
            elif (double_quotes and "'''" in line) or (
                not double_quotes and '"""' in line
            ):
                continue
            multiline = not multiline
            continue
    for i in range(len(lines)):
        _indent = "    " if i in indent_lines else ""
        lines_out.append(_indent + lines[i])
    return lines_out


class NotebookCompiler:
    _in_autopipeline = False
    _cell_number: int = 0
    _cell_processor_contents: dict[int, str] = {}

    def parse_cell(self, cell, fout):
        if cell["cell_type"] == "code":
            source = cell["source"]
            if len(source) > 0 and "#ignore" not in source[0]:
                code = (
                    "".join(cell["source"])
                    if isinstance(cell["source"], list)
                    else cell["source"]
                )

                clean_code = (
                    "\n".join(
                        [
                            re.sub(r"^\t+(?=\S)", "", line)
                            if not line.startswith("!")
                            else ""
                            for line in code.split("\n")
                        ]
                    ).strip("\n")
                    + "\n"
                )

                if not clean_code.strip():
                    return
                if not self._in_autopipeline:
                    fout.write(clean_code + "\n\n")
                else:
                    self._cell_processor_contents[self._cell_number] = (
                        "\n".join(indent_code(clean_code.split("\n"))) + "\n\n"
                    )
                if not self._in_autopipeline and contains_function_call(
                    ast.parse(clean_code), "auto_pipeline"
                ):
                    self._in_autopipeline = True

    def compile_notebook(self, ntb, out_path="tmp.py"):
        self._cell_number = 0
        self._in_autopipeline = False
        self._cell_processor_contents = {}
        with open(out_path, "w") as f:
            for cell in ntb["cells"]:
                self._cell_number += 1
                self.parse_cell(cell, f)
            step_func_code = f"""@async_step
async def processor_internal(inject, event):
{''.join(list(self._cell_processor_contents.values()))}    await inject(event)
"""
            f.write(step_func_code)


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
            exit(f"Notebook {app.Notebook} not found")

        if bspump.jupyter.bitswan_auto_pipeline.get("sink") is not None:
            register_sink(  # noqa: F405
                bspump.jupyter.bitswan_auto_pipeline.get("sink")
            )  # noqa: F405
            end_pipeline()  # noqa: F405

        app.init_componets()
        app.run()


if __name__ == "__main__":
    main()
