import ast
import re
import markdown

config = None
__bitswan_dev = False
__bs_step_locals = {}


def contains_function_call(ast_tree, function_name):
    for node in ast.walk(ast_tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == function_name:
                return True
    return False


def indent_code(lines: list[str]) -> list[str]:
    multiline_quote_string = None
    indent_lines = []
    lines_out = []
    for i, line in enumerate(lines):
        if not multiline_quote_string and line.strip(" ") != "":
            indent_lines.append(i)
        if multiline_quote_string and multiline_quote_string in line:
            multiline_quote_string = None
            continue
        if line.count('"""') % 2 == 1:
            multiline_quote_string = '"""'
        if line.count("'''") % 2 == 1:
            multiline_quote_string = "'''"
    for i in range(len(lines)):
        _indent = "    " if i in indent_lines else ""
        lines_out.append(_indent + lines[i])
    return lines_out


def detect_webchat(ntb):
    """
    First pass: check if any code cell contains create_webchat_flow()
    """
    for cell in ntb["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = cell["source"]
        if isinstance(source, list):
            source = "".join(source)
        if not source.strip():
            continue

        try:
            parsed_ast = ast.parse(source)
        except SyntaxError:
            continue

        if contains_function_call(parsed_ast, "create_webchat_flow"):
            return True

    return False


class NotebookCompiler:
    _in_autopipeline = False
    _in_webchat_context = False
    _cell_number: int = 0
    _cell_processor_contents: dict[int, str] = {}
    _webchat_flows: dict[str, str] = {}
    _current_flow_name: str | None = None
    _current_chat_name: str | None = None
    _webchat_detected = False
    _auto_pipeline_added = False

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
                parsed_ast = ast.parse(clean_code)

                # Check if the cell contains create_webchat_flow
                if contains_function_call(parsed_ast, "create_webchat_flow"):
                    self._webchat_detected = True

                    for node in ast.walk(parsed_ast):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    variable_name = target.id
                                    if (
                                        isinstance(node.value, ast.Call)
                                        and isinstance(node.value.func, ast.Name)
                                        and node.value.func.id == "create_webchat_flow"
                                    ):
                                        if node.value.args:
                                            arg0 = node.value.args[0]

                                            if isinstance(arg0, ast.Constant):
                                                flow_name = arg0.value
                                            elif isinstance(arg0, ast.Name):
                                                flow_name = arg0.id
                                            else:
                                                flow_name = str(self._cell_number)
                                            self._current_flow_name = flow_name
                                            self._current_chat_name = variable_name
                                            self._webchat_flows[
                                                flow_name
                                            ] = f"@create_webchat_flow('{flow_name}')\nasync def {flow_name}({variable_name}):\n"
                                            return

                if self._current_flow_name is not None:
                    cleaned_lines = [
                        line
                        for line in clean_code.split("\n")
                        if line.strip() != "" and not line.strip().startswith("#")
                    ]
                    if cleaned_lines:
                        cleaned_code = "\n".join(cleaned_lines)
                        self._webchat_flows[self._current_flow_name] += (
                            "\n".join(indent_code(cleaned_code.split("\n"))) + "\n\n"
                        )
                    return

                # Handle regular code cells
                if not self._in_autopipeline:
                    fout.write(clean_code + "\n\n")
                else:
                    self._cell_processor_contents[self._cell_number] = (
                        "\n".join(indent_code(clean_code.split("\n"))) + "\n\n"
                    )
                if not self._in_autopipeline and contains_function_call(
                    parsed_ast, "auto_pipeline"
                ):
                    self._in_autopipeline = True
                    if "WebChatSource":
                        self._in_webchat_context = True
        elif (
            cell["cell_type"] == "markdown"
            and self._webchat_detected
            and self._current_chat_name is not None
        ):
            markdown_content = cell["source"]
            if isinstance(markdown_content, list):
                markdown_content = "".join(markdown_content)
            markdown_content = markdown_content.strip()
            if markdown_content:
                if self._current_flow_name is not None or (
                    self._in_autopipeline and self._in_webchat_context
                ):
                    html_content = markdown.markdown(
                        markdown_content,
                        extensions=["fenced_code", "tables", "codehilite"],
                    )
                    escaped_html = html_content.replace('"', '\\"').replace("'", "\\'")
                    response_code = f'    await {self._current_chat_name}.tell_user(f"""{escaped_html}""", is_html=True)\n'

                    if self._current_flow_name is not None:
                        self._webchat_flows[self._current_flow_name] += response_code
                    elif self._in_autopipeline and self._in_webchat_context:
                        self._cell_processor_contents[self._cell_number] = response_code

    def compile_notebook(self, ntb, out_path="tmp.py"):
        self._cell_number = 0
        self._in_autopipeline = False
        self._in_webchat_context = False
        self._cell_processor_contents = {}
        self._current_flow_name = None
        self._current_chat_name = None
        self._auto_pipeline_added = False
        self._webchat_detected = detect_webchat(ntb)

        with open(out_path, "w") as f:
            if self._webchat_detected:
                # Automatically add auto-pipeline
                if not self._auto_pipeline_added:
                    pipeline_setup = """from bspump.http_webchat.server import *\nfrom bspump.http_webchat.webchat import *\nfrom bspump.jupyter import *\n\n# Auto-generated pipeline setup for webchat
auto_pipeline(
    source=lambda app, pipeline: WebChatSource(app, pipeline),
    sink=lambda app, pipeline: WebchatSink(app, pipeline)
)
"""
                    f.write(pipeline_setup)
                    self._auto_pipeline_added = True
                    self._in_autopipeline = True
                    self._in_webchat_context = True
            for cell in ntb["cells"]:
                self._cell_number += 1
                self.parse_cell(cell, f)
            step_func_code = f"""@async_step
async def processor_internal(inject, event):
{''.join(list(self._cell_processor_contents.values()))}    await inject(event)
"""
            f.write(step_func_code)
            for flow_name, steps in self._webchat_flows.items():
                f.write(steps + "\n")
