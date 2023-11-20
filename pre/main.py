import json

with open("./main.ipynb") as nb:
    notebook = json.load(nb)
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            source = cell["source"]
            if len(source) > 0 and "#ignore" not in source[0]:
                code = "\n".join(cell["source"])
                exec(code)

App().run()
