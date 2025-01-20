from bspump.main import NotebookCompiler
import json
import ast
import pytest


def test_notebook_parse_valid():
    compiler = NotebookCompiler()
    with open("jupyter/parse_example.ipynb", "r") as ntbf:
        ntb = json.load(ntbf)
    compiler.compile_notebook(ntb, "jupyter/tmp.py")
    with open("jupyter/tmp.py", "r") as outf:
        out = ast.parse(outf.read())
    with open("jupyter/expected.py", "r") as expectf:
        expect = ast.parse(expectf.read())
    assert ast.dump(out) == ast.dump(expect)


def test_notebook_formatting():
    compiler = NotebookCompiler()
    with open("jupyter/parse_example.ipynb", "r") as ntbf:
        ntb = json.load(ntbf)
    compiler.compile_notebook(ntb, "jupyter/tmp.py")
    with open("jupyter/tmp.py", "r") as outf:
        out = outf.read()
    with open("jupyter/expected.py", "r") as expectf:
        expect = expectf.read()
    assert out == expect
