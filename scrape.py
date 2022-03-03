from argparse import ArgumentParser
from ast import (
    AsyncFunctionDef,
    ClassDef,
    FunctionDef,
    Module,
    get_docstring,
    parse,
    unparse,
)
from pathlib import Path


def parse_summary(data: str, book: Path) -> dict[str, str]:
    # a very dumb parser
    # but, doesn't matter because we are just going to extract the list
    # items from the markdown, and a SUMMARY.md file just contains lists
    # and Headings, if you have anything else in it, then you are doing
    # it wrong

    out = []

    for line in data.splitlines():
        line = line.strip()

        # a TOC entry
        if line.startswith("- [") and line.endswith(")"):
            # empty, skip
            if line[-2:] == "()":
                continue
            # easy way to get name and file path
            name, path = line[3:-1].split("](", 1)
            out.append((name, book.joinpath(path)))

    return out


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
    data: Module
    target_dir: Path
    ignore: list[str]
    names: tuple[str]
    paths: tuple[str]
    template: str = "{heading} {name}\n\n{body}"

    def __init__(self, target_dir: Path, summary: dict[str, str]) -> None:
        self.target_dir = target_dir
        self.names, self.paths = list(zip(*summary))
        self.ignore = []

    def parse(self, path: str, name: str, data: str) -> None:
        folder = self.target_dir.joinpath(path)
        name = name + ".md"

        file = folder.joinpath(name)

        if not file in self.paths:
            return

        index = self.paths.index(file)
        chap_name = self.names[index]

        if data.startswith("#"):
            ignore = mod_comment_scanner(data)
            if ignore is None:
                print("Ignoring file", name)
                return
            self.ignore = ignore

        self._data = data
        self.data = parse(data)

        buffer = self._parse_module().strip()

        folder.mkdir(parents=True, exist_ok=True)
        with open(file, "w") as f:
            f.write(self.template.format(heading="#", name=chap_name, body=buffer))

        self._data = ""
        self.data = None  # type: ignore

    def _parse_module(self) -> str:
        buffer = ""
        for node in self.data.body:
            if isinstance(node, ClassDef) and not node.name.startswith("_"):
                buffer += self._parse_class(node)
            elif isinstance(
                node, (FunctionDef, AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                buffer += self._parse_function(node)

        return buffer

    def _parse_class(self, node: ClassDef) -> str:

        if node.name in self.ignore:
            print("Ignoring class", node.name)
            return ""

        signature = ""
        doc_string = get_docstring(node)
        body = f"{doc_string}\n\n"

        for subnode in node.body:
            if isinstance(subnode, (FunctionDef, AsyncFunctionDef)):
                if subnode.name == "__init__":
                    # self will be the first arg to __init__, if not
                    # then you are probably doing something wrongs
                    subnode.args.args = subnode.args.args[1:]
                    signature = unparse(subnode.args)
                    continue
                if not subnode.name.startswith("_"):
                    body += f"{self._parse_method(node.name, subnode)}"

        name = f"class {node.name}({signature})"

        return self.template.format(heading="##", name=name, body=body)

    def _parse_method(
        self, class_name: str, node: FunctionDef | AsyncFunctionDef
    ) -> str:

        doc_str = get_docstring(node)

        if not doc_str:
            return ""

        if f"{class_name}.{node.name}" in self.ignore:
            print("Ignoring method", node.name, "in", class_name)
            return ""

        prefix = ""

        for decor in filter(
            lambda decor: decor.id in {"classmethod", "staticmethod", "property"},  # type: ignore
            node.decorator_list,
        ):
            prefix = decor.id  # type: ignore

        if prefix != "property":
            if len(node.args.args) == 1 and node.args.args[0].arg == "self":
                node.args.args = []
            elif len(node.args.args) > 1:
                node.args.args = (
                    node.args.args[1:]
                    if node.args.args[0].arg == "self"
                    else node.args.args
                )

            signature = unparse(node).splitlines()
            if prefix:
                signature = signature[len(node.decorator_list)]
            else:
                signature = signature[0]

            if isinstance(node, AsyncFunctionDef):
                signature = signature[10:-1].replace("self, ", "").replace("self", "")
                name = f"async {prefix+' ' if prefix else ''}{class_name}.{signature}"
            else:
                signature = signature[4:-1].replace("self, ", "").replace("self", "")
                name = f"{prefix+' ' if prefix else ''}{class_name}.{signature}"
        else:
            name = f"property {class_name}.{node.name}: {unparse(node.returns) if node.returns else 'None'}"

        return self.template.format(heading="###", name=name, body=f"{doc_str}\n\n\n")

    def _parse_function(self, node: FunctionDef | AsyncFunctionDef) -> str:

        doc_str = get_docstring(node)

        if not doc_str:
            return ""

        name = ""
        if node.name in self.ignore:
            print("Ignoring function", name)
            return ""

        signature = unparse(node.args)
        if isinstance(node, AsyncFunctionDef):
            name = f"async {signature}"
        else:
            name = f"{signature}"
        return self.template.format(
            heading="##", name=node.name, body=f"{doc_str}\n\n\n"
        )


def recurse_dir(path: Path, sub: int, parser: Parser) -> None:
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


def main(base: Path, parser: Parser) -> int:
    sub = len(str(base)) + 1

    for path in base.iterdir():
        if path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
            with open(path, "r") as file:
                parser.parse(str(path.parent)[sub:], path.stem, file.read())
        elif path.is_dir():
            recurse_dir(path, sub, parser)

    return 0


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        description=(
            "Extract docstrings from all the files in `src`"
            " dir and write then to `out` dir"
        )
    )

    arg_parser.add_argument(
        "src",
        type=Path,
        help="The directory where the source files are located",
    )
    arg_parser.add_argument(
        "out",
        type=Path,
        help="The directory where the output files will be written",
    )

    args = arg_parser.parse_args()

    assert isinstance(args.src, Path)
    assert isinstance(args.out, Path)
    assert args.src.is_dir(), "src is not a directory directory or does not exist"

    base, book = (args.src.resolve(), args.out.resolve())
    summary = book / "SUMMARY.md"

    if not base.exists():
        print("src directory does not exist!")
        raise SystemExit(1)

    if not summary.exists():
        print("SUMMARY.md does not exist! Aborting...")
        raise SystemExit(1)

    parser = Parser(book, parse_summary(summary.read_text(), book))

    raise SystemExit(main(base, parser))
