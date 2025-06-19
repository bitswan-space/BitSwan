import ast
import re

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


def sanitize_flow_name(flow_name: str) -> str:
    sanitized = flow_name.lstrip("/")
    sanitized = re.sub(r"\W+", "_", sanitized)
    if not sanitized[0].isalpha() and sanitized[0] != "_":
        sanitized = f"_{sanitized}"
    return f"flow_{sanitized}"


def clean_webchat_flow_code(steps) -> list[str]:
    return [
        step.strip() for step in (s.replace("\n", "") for s in steps) if step.strip()
    ]


class NotebookCompiler:
    _in_autopipeline = False
    _cell_number: int = 0
    _cell_processor_contents: dict[int, str] = {}
    _webchat_flows: dict[str, list[str]] = {}
    _current_flow_name: str | None = None

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
                if contains_function_call(parsed_ast, "create_webchat_flow"):
                    for node in ast.walk(parsed_ast):
                        if isinstance(node, ast.Expr) and isinstance(
                            node.value, ast.Call
                        ):
                            call = node.value
                            if (
                                isinstance(call, ast.Call)
                                and isinstance(call.func, ast.Name)
                                and call.func.id == "create_webchat_flow"
                            ):
                                arg0 = call.args[0]
                                if isinstance(arg0, ast.Constant):
                                    flow_name = arg0.value
                                elif isinstance(arg0, ast.Name):
                                    flow_name = arg0.id
                                else:
                                    flow_name = self._cell_number
                                sanitized_flow_name = sanitize_flow_name(flow_name)
                                self._current_flow_name = sanitized_flow_name
                                self._webchat_flows[sanitized_flow_name] = []
                                return

                if self._current_flow_name is not None:
                    self._webchat_flows[self._current_flow_name].append(clean_code)
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

        elif cell["cell_type"] == "markdown":
            if self._current_flow_name is not None:
                markdown_content = cell["source"]
                if isinstance(markdown_content, list):
                    markdown_content = "".join(markdown_content)
                markdown_content = markdown_content.strip()
                if markdown_content:
                    response_code = f"WebChatResponse(input_html={markdown_content!r})"
                    if self._current_flow_name is not None:
                        self._webchat_flows[self._current_flow_name].append(
                            response_code
                        )

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
            for flow_name, steps in self._webchat_flows.items():
                cleaned_steps = clean_webchat_flow_code(steps)
                flow_func_code = (
                    f"@create_webchat_flow('/{flow_name.replace('-', '_')}')\n"
                    + f"async def {flow_name.replace('-', '_')}(request):\n"
                    + f"    return {cleaned_steps}\n"
                )
                f.write(flow_func_code)

        # Print the contents of the written file
        with open(out_path, "r") as f:
            print(f"\n--- Contents of {out_path} ---\n")
            print(f.read())
