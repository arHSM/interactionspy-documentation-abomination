import ast
import pathlib
import shutil

HERE = pathlib.Path(__file__).parent.resolve()


def mod_comment_scanner(data: str) -> list[str] | None:
    index = 0
    stuff = ""
    opened = False
    while index != len(data):
        if data[index] == "\n" and data[index + 1] != "#":
            break

        if data[index:].startswith("# doc: module ignore"):
            return None

        if data[index:].startswith("# doc: ignore"):
            opened = True
            index += len("# doc: ignore")
            continue

        if data[index:].startswith("# doc: end ignore"):
            if not opened:
                raise RuntimeError("'# doc: end ignore' without '# doc: ignore'")
            break

        stuff += data[index]

        index += 1

    return stuff.replace("#", "").split(",") if stuff else []


class Parser:
    _data: str
    data: ast.Module
    target_dir: str
    ignore: list[str]
    template: str = "{heading} {name}\n\n{body}"

    def __init__(self, target_dir: str) -> None:
        self.target_dir = target_dir
        self.ignore = []

    def parse(self, path: str, name: str, data: str) -> None:
        if data.startswith("#"):
            ignore = mod_comment_scanner(data)
            if ignore is None:
                print("Ignoring file", name)
                return
            self.ignore = ignore

        self._data = data
        self.data = ast.parse(data)
        self.write(path, name, self._parse_module().strip())

    def write(self, path: str, name: str, buffer: str) -> None:
        name = name + ".md"
        folder = HERE.joinpath(self.target_dir, path)
        folder.mkdir(parents=True, exist_ok=True)
        with open((folder / name), "w") as f:
            f.write(buffer)

    def _parse_module(self) -> str:
        buffer = ""
        for node in self.data.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                buffer += self._parse_class(node)
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                buffer += self._parse_function(node)

        return buffer

    def _parse_class(self, node: ast.ClassDef) -> str:

        if node.name in self.ignore:
            print("Ignoring class", node.name)
            return ""

        name = f"class {node.name}"
        signature = ""
        doc_string = ast.get_docstring(node)
        body = f"{doc_string}\n\n"

        for subnode in node.body:
            if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if subnode.name == "__init__":
                    signature = (
                        ast.unparse(subnode.args)
                        .replace("self, ", "")
                        .replace("self", "")
                    )
                    continue
                if not subnode.name.startswith("_"):
                    body += f"{self._parse_method(node.name, subnode)}"

        name = f"{node.name}({signature})"

        return self.template.format(heading="##", name=name, body=body)

    def _parse_method(
        self, class_name: str, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:

        doc_str = ast.get_docstring(node)

        if not doc_str:
            return ""

        if f"{class_name}.{node.name}" in self.ignore:
            print("Ignoring method", node.name, "in", class_name)
            return ""

        if len(node.args.args) == 1 and node.args.args[0].arg == "self":
            node.args.args = []
        elif len(node.args.args) > 1:
            node.args.args = (
                node.args.args[1:]
                if node.args.args[0].arg == "self"
                else node.args.args[0:]
            )

        signature = ast.unparse(node).split("\n", 1)[0]

        if isinstance(node, ast.AsyncFunctionDef):
            signature = signature[10:-1].replace("self, ", "").replace("self", "")
            name = f"async {class_name}.{signature}"
        else:
            signature = signature[4:-1].replace("self, ", "").replace("self", "")
            name = f"{class_name}.{signature}"

        return self.template.format(heading="###", name=name, body=f"{doc_str}\n\n\n")

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:

        doc_str = ast.get_docstring(node)

        if not doc_str:
            return ""

        name = ""
        if node.name in self.ignore:
            print("Ignoring function", name)
            return ""

        signature = ast.unparse(node.args)
        if isinstance(node, ast.AsyncFunctionDef):
            name = f"async {signature}"
        else:
            name = f"{signature}"
        return self.template.format(
            heading="##", name=node.name, body=f"{doc_str}\n\n\n"
        )


def recurse_dir(path: pathlib.Path, sub: int, parser: Parser) -> None:
    for subpath in path.iterdir():
        if subpath.is_dir():
            recurse_dir(subpath, sub, parser)
        elif (
            subpath.is_file()
            and subpath.suffix == ".py"
            and not subpath.name.startswith("_")
        ):
            with open(subpath, "r") as file:
                parser.parse(str(subpath.parent)[sub:], subpath.stem, file.read())


def main(base: pathlib.Path, parser: Parser) -> None:
    sub = len(str(base)) + 1

    for path in base.iterdir():
        if path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
            with open(path, "r") as file:
                parser.parse(str(path.parent)[sub:], path.stem, file.read())
        elif path.is_dir():
            recurse_dir(path, sub, parser)

    return 0


if __name__ == "__main__":
    parser = Parser("book")
    base = HERE / "interactions"
    book = HERE / "book"

    if not base.exists():
        print("src directory does not exist!")
        raise SystemExit(1)

    if book.exists():
        shutil.rmtree(book)

    raise SystemExit(main(base, parser))
