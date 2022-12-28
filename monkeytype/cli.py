# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import argparse
import collections
import difflib
import importlib
import inspect
import os
import os.path
import runpy
import sys
from pathlib import Path
from typing import (
    IO,
    TYPE_CHECKING,
    List,
    Optional,
    Tuple,
    Dict,
    Set,
    Union,
)

import libcst
from libcst import (
    parse_module,
    Module,
    CSTTransformer,
    RemovalSentinel,
    FlattenSentinel,
    BaseSmallStatement,
    MaybeSentinel,
    RemoveFromParent,
)
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import (
    ApplyTypeAnnotationsVisitor,
    AddImportsVisitor,
    GatherImportsVisitor,
    ImportItem,
)
from libcst.helpers import get_absolute_module_from_package_for_import

from monkeytype import trace
from monkeytype.config import Config
from monkeytype.exceptions import MonkeyTypeError
from monkeytype.stubs import (
    ExistingAnnotationStrategy,
    Stub,
    build_module_stubs_from_traces,
)
from monkeytype.tracing import CallTrace
from monkeytype.typing import NoOpRewriter
from monkeytype.util import get_name_in_module

if TYPE_CHECKING:
    # This is not present in Python 3.6.1, so not safe for runtime import
    from typing import NoReturn  # noqa


def module_path(path: str) -> Tuple[str, Optional[str]]:
    """Parse <module>[:<qualname>] into its constituent parts."""
    parts = path.split(":", 1)
    module = parts.pop(0)
    qualname = parts[0] if parts else None
    if os.sep in module:  # Smells like a path
        raise argparse.ArgumentTypeError(
            f"{module} does not look like a valid Python import path"
        )

    return module, qualname


def module_path_with_qualname(path: str) -> Tuple[str, str]:
    """Require that path be of the form <module>:<qualname>."""
    module, qualname = module_path(path)
    if qualname is None:
        raise argparse.ArgumentTypeError("must be of the form <module>:<qualname>")
    return module, qualname


def complain_about_no_traces(args: argparse.Namespace, stderr: IO[str]) -> None:
    module, qualname = args.module_path
    if qualname:
        print(f"No traces found for specifier {module}:{qualname}", file=stderr)
    # When there is no trace and a top level module's filename is passed, print
    # a useful error message.
    elif os.path.exists(module):
        print(
            f"No traces found for {module}; did you pass a filename instead of a module name? "
            f"Maybe try just '{os.path.splitext(module)[0]}'.",
            file=stderr,
        )
    else:
        print(f"No traces found for module {module}", file=stderr)


def get_monkeytype_config(path: str) -> Config:
    """Imports the config instance specified by path.

    Path should be in the form module:qualname. Optionally, path may end with (),
    in which case we will call/instantiate the given class/function.
    """
    should_call = False
    if path.endswith("()"):
        should_call = True
        path = path[:-2]
    module, qualname = module_path_with_qualname(path)
    try:
        config = get_name_in_module(module, qualname)
    except MonkeyTypeError as mte:
        raise argparse.ArgumentTypeError(f"cannot import {path}: {mte}")
    if should_call:
        config = config()
    return config  # type: ignore[no-any-return]


def display_sample_count(traces: List[CallTrace], stderr: IO[str]) -> None:
    """Print to stderr the number of traces each stub is based on."""
    sample_counter = collections.Counter([t.funcname for t in traces])
    for name, count in sample_counter.items():
        print(f"Annotation for {name} based on {count} call trace(s).", file=stderr)


def get_stub(
    args: argparse.Namespace, stdout: IO[str], stderr: IO[str]
) -> Optional[Stub]:
    module, qualname = args.module_path
    thunks = args.config.trace_store().filter(module, qualname, args.limit)
    traces = []
    failed_to_decode_count = 0
    for thunk in thunks:
        try:
            traces.append(thunk.to_trace())
        except MonkeyTypeError as mte:
            if args.verbose:
                print(f"WARNING: Failed decoding trace: {mte}", file=stderr)
            failed_to_decode_count += 1
    if failed_to_decode_count and not args.verbose:
        print(
            f"{failed_to_decode_count} traces failed to decode; use -v for details",
            file=stderr,
        )
    if not traces:
        return None
    rewriter = args.config.type_rewriter()
    if args.disable_type_rewriting:
        rewriter = NoOpRewriter()
    stubs = build_module_stubs_from_traces(
        traces,
        args.config.max_typed_dict_size(),
        existing_annotation_strategy=args.existing_annotation_strategy,
        rewriter=rewriter,
    )
    if args.sample_count:
        display_sample_count(traces, stderr)
    return stubs.get(module, None)


class HandlerError(Exception):
    pass


def add_type_checking_import(source_module: Module) -> Module:
    context = CodemodContext()
    AddImportsVisitor.add_needed_import(context, "typing", "TYPE_CHECKING")
    transformer = AddImportsVisitor(context)
    transformed_source_module = transformer.transform_module(source_module)
    return transformed_source_module


class RemoveImportsTransformer(CSTTransformer):
    def __init__(
        self,
        import_modules_to_remove: Set[str],
        import_objects_to_remove: Dict[str, Set[str]],
    ) -> None:
        self.import_modules_to_remove = import_modules_to_remove
        self.import_objects_to_remove = import_objects_to_remove

    def leave_Import(
        self, original_node: libcst.Import, updated_node: libcst.Import
    ) -> Union[
        BaseSmallStatement, FlattenSentinel[BaseSmallStatement], RemovalSentinel
    ]:
        names_to_keep = []
        for name in updated_node.names:
            module_name = name.evaluated_name
            if module_name not in self.import_modules_to_remove:
                names_to_keep.append(name.with_changes(comma=MaybeSentinel.DEFAULT))

        if not names_to_keep:
            return RemoveFromParent()
        else:
            return updated_node.with_changes(names=names_to_keep)

    def leave_ImportFrom(
        self, original_node: libcst.ImportFrom, updated_node: libcst.ImportFrom
    ) -> Union[
        BaseSmallStatement, FlattenSentinel[BaseSmallStatement], RemovalSentinel
    ]:
        names_to_keep = []
        module_name = get_absolute_module_from_package_for_import(None, updated_node)
        for name in updated_node.names:
            name_value = name.name.value
            if name_value not in self.import_objects_to_remove.get(module_name, {}):
                names_to_keep.append(name.with_changes(comma=MaybeSentinel.DEFAULT))

        if not names_to_keep:
            return RemoveFromParent()
        else:
            return updated_node.with_changes(names=names_to_keep)


def remove_new_imports(
    source_module: Module,
    import_modules_to_remove: Set[str],
    import_objects_to_remove: Dict[str, Set[str]],
) -> Module:
    transformer = RemoveImportsTransformer(import_modules_to_remove, import_objects_to_remove)
    transformed_source_module = source_module.visit(transformer)
    return transformed_source_module


def get_import_module(
    newly_imported_modules: Set[str],
    newly_imported_objects: Dict[str, Set[str]],
) -> Module:
    empty_code = libcst.parse_module("")
    context = CodemodContext()
    imports: List[ImportItem] = []
    for k, v_list in newly_imported_objects.items():
        for v in v_list:
            imports.append(ImportItem(k, v))

    for mod in newly_imported_modules:
        imports.append(ImportItem(mod))

    context.scratch[AddImportsVisitor.CONTEXT_KEY] = imports
    transformer = AddImportsVisitor(context)
    transformed_source_module = transformer.transform_module(empty_code)

    return transformed_source_module


def replace_pass_with_imports(
    placeholder_module: Module,
    import_module: Module
) -> Module:
    return placeholder_module.with_deep_changes(
        old_node=placeholder_module.body[0].body,
        body=import_module.body,
    )


class TypeCheckingImportVisitor(libcst.CSTVisitor):
    def __init__(self):
        self.found = False

    def visit_ImportFrom(self, node: libcst.ImportFrom) -> Optional[bool]:
        module_name = get_absolute_module_from_package_for_import(None, node)
        if module_name != "typing":
            return False

        for name in node.names:
            name_value = name.name.value
            if name_value == "TYPE_CHECKING":
                self.found = True
                return False

        return True


def get_type_checking_import_index(source_module: Module) -> int:
    type_checking_import_index = 0
    for idx, node in enumerate(source_module.body):
        visitor = TypeCheckingImportVisitor()
        node.visit(visitor)
        if visitor.found:
            type_checking_import_index = idx
            break

    return type_checking_import_index


class ImportVisitorWithScope(libcst.CSTVisitor):
    def __init__(self):
        self.found = False

    def visit_ClassDef(self, node: libcst.ClassDef) -> Optional[bool]:
        return False

    def visit_FunctionDef(self, node: libcst.FunctionDef) -> Optional[bool]:
        return False

    def visit_Import(self, node: libcst.Import) -> Optional[bool]:
        self.found = True
        return True

    def visit_ImportFrom(self, node: libcst.ImportFrom) -> Optional[bool]:
        self.found = True
        return True


def get_first_non_import_idx(source_module: Module, type_checking_import_index: int) -> int:
    first_non_import_idx = type_checking_import_index + 1
    for idx, node in enumerate(source_module.body):
        if idx <= type_checking_import_index:
            continue
        visitor = ImportVisitorWithScope()
        node.visit(visitor)
        if not visitor.found:
            first_non_import_idx = idx
            break

    return first_non_import_idx


def add_if_type_checking_block(
    source_module: Module,
    newly_imported_modules: Set[str],
    newly_imported_objects: Dict[str, Set[str]],
) -> Module:
    import_module = get_import_module(newly_imported_modules, newly_imported_objects)
    placeholder_module = libcst.parse_module("\nif TYPE_CHECKING:\n    pass\n")
    type_checking_block_module = replace_pass_with_imports(placeholder_module, import_module)

    # Find the node number where TYPE_CHECKING was imported
    type_checking_import_index = get_type_checking_import_index(source_module)

    # Find the first non import statement after type_checking_import_index
    first_non_import_idx = get_first_non_import_idx(source_module, type_checking_import_index)

    # Insert type_checking_block_module at first_non_import_idx
    updated_body_list = [
        *source_module.body[:first_non_import_idx],
        type_checking_block_module,
        *source_module.body[first_non_import_idx:],
    ]
    return source_module.with_changes(body=updated_body_list)


def add_new_imports_in_type_checking_block(
    source_module: Module,
    newly_imported_modules: Set[str],
    newly_imported_objects: Dict[str, Set[str]],
) -> Module:
    source_module = add_type_checking_import(source_module)

    # Remove typing library since we do not want it
    # to be imported inside the if TYPE_CHECKING block
    newly_imported_objects.pop("typing", None)
    newly_imported_modules.discard("typing")

    # Remove the newer imports since those are to be
    # shifted inside the if TYPE_CHECKING block
    source_module = remove_new_imports(
        source_module,
        newly_imported_modules,
        newly_imported_objects,
    )

    # Add the new imports inside if TYPE_CHECKING block
    source_module = add_if_type_checking_block(
        source_module,
        newly_imported_modules,
        newly_imported_objects,
    )

    return source_module


def get_newly_imported_objects_and_modules(
    stub_module: Module,
    source_module: Module
) -> Tuple[Dict[str, Set[str]], Set[str]]:
    context = CodemodContext()
    gatherer = GatherImportsVisitor(context)
    stub_module.visit(gatherer)
    stub_object_mapping = gatherer.object_mapping
    stub_module_imports = gatherer.module_imports

    context = CodemodContext()
    gatherer = GatherImportsVisitor(context)
    source_module.visit(gatherer)
    source_object_mapping = gatherer.object_mapping
    source_module_imports = gatherer.module_imports

    for k, v in stub_object_mapping.items():
        stub_object_mapping[k] = v.difference(source_object_mapping.get(k, {}))

    return stub_object_mapping, stub_module_imports.difference(source_module_imports)


def apply_stub_using_libcst(
    stub: str,
    source: str,
    overwrite_existing_annotations: bool,
    contain_new_imports_in_type_checking_block: bool = False,
) -> str:
    try:
        stub_module = parse_module(stub)
        source_module = parse_module(source)
        newly_imported_objects, newly_imported_modules = get_newly_imported_objects_and_modules(
            stub_module, source_module)
        context = CodemodContext()
        ApplyTypeAnnotationsVisitor.store_stub_in_context(
            context,
            stub_module,
            overwrite_existing_annotations,
            use_future_annotations=contain_new_imports_in_type_checking_block,
        )
        transformer = ApplyTypeAnnotationsVisitor(context)
        transformed_source_module = transformer.transform_module(source_module)

        if contain_new_imports_in_type_checking_block:
            transformed_source_module = add_new_imports_in_type_checking_block(
                transformed_source_module,
                newly_imported_modules,
                newly_imported_objects,
            )

    except Exception as exception:
        raise HandlerError(f"Failed applying stub with libcst:\n{exception}")
    return transformed_source_module.code


def apply_stub_handler(
    args: argparse.Namespace, stdout: IO[str], stderr: IO[str]
) -> None:
    stub = get_stub(args, stdout, stderr)
    if stub is None:
        complain_about_no_traces(args, stderr)
        return
    module = args.module_path[0]
    mod = importlib.import_module(module)

    source_path = Path(inspect.getfile(mod))
    source_with_types = apply_stub_using_libcst(
        stub=stub.render(),
        source=source_path.read_text(),
        overwrite_existing_annotations=args.existing_annotation_strategy
        == ExistingAnnotationStrategy.IGNORE,
        contain_new_imports_in_type_checking_block=args.pep_563,
    )
    source_path.write_text(source_with_types)
    print(source_with_types, file=stdout)


def get_diff(
    args: argparse.Namespace, stdout: IO[str], stderr: IO[str]
) -> Optional[str]:
    args.existing_annotation_strategy = ExistingAnnotationStrategy.REPLICATE
    stub = get_stub(args, stdout, stderr)
    args.existing_annotation_strategy = ExistingAnnotationStrategy.IGNORE
    stub_ignore_anno = get_stub(args, stdout, stderr)
    if stub is None or stub_ignore_anno is None:
        return None
    diff = []
    seq1 = (s + "\n" for s in stub.render().split("\n\n\n"))
    seq2 = (s + "\n" for s in stub_ignore_anno.render().split("\n\n\n"))
    for stub1, stub2 in zip(seq1, seq2):
        if stub1 != stub2:
            stub_diff = "".join(
                difflib.ndiff(
                    stub1.splitlines(keepends=True), stub2.splitlines(keepends=True)
                )
            )
            diff.append(stub_diff[:-1])
    return "\n\n\n".join(diff)


def print_stub_handler(
    args: argparse.Namespace, stdout: IO[str], stderr: IO[str]
) -> None:
    output, file = None, stdout
    if args.diff:
        output = get_diff(args, stdout, stderr)
    else:
        stub = get_stub(args, stdout, stderr)
        if stub is not None:
            output = stub.render()
    if output is None:
        complain_about_no_traces(args, stderr)
        return
    print(output, file=file)


def list_modules_handler(
    args: argparse.Namespace, stdout: IO[str], stderr: IO[str]
) -> None:
    output, file = None, stdout
    modules = args.config.trace_store().list_modules()
    output = "\n".join(modules)
    print(output, file=file)


def run_handler(args: argparse.Namespace, stdout: IO[str], stderr: IO[str]) -> None:
    # remove initial `monkeytype run`
    old_argv = sys.argv.copy()
    try:
        with trace(args.config):
            sys.argv = [args.script_path] + args.script_args
            if args.m:
                runpy.run_module(args.script_path, run_name="__main__", alter_sys=True)
            else:
                runpy.run_path(args.script_path, run_name="__main__")
    finally:
        sys.argv = old_argv


def update_args_from_config(args: argparse.Namespace) -> None:
    """Pull values from config for unspecified arguments."""
    if args.limit is None:
        args.limit = args.config.query_limit()


def main(argv: List[str], stdout: IO[str], stderr: IO[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate and apply stub files from collected type information.",
    )
    parser.add_argument(
        "--disable-type-rewriting",
        action="store_true",
        default=False,
        help="Show types without rewrite rules applied (default: False)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help=(
            "How many traces to return from storage"
            " (default: 2000, unless changed in your config)"
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Show verbose output (e.g. include trace-decoding-failed errors)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="monkeytype.config:get_default_config()",
        help=(
            "The <module>:<qualname> of the config to use"
            " (default: monkeytype_config:CONFIG if it exists, "
            "else monkeytype.config:DefaultConfig())"
        ),
    )

    subparsers = parser.add_subparsers(title="commands", dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Run a Python script under MonkeyType tracing",
        description="Run a Python script under MonkeyType tracing",
    )
    run_parser.add_argument(
        "script_path",
        type=str,
        help="""Filesystem path to a Python script file to run under tracing""",
    )
    run_parser.add_argument(
        "-m", action="store_true", help="Run a library module as a script"
    )
    run_parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
    )
    run_parser.set_defaults(handler=run_handler)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Generate and apply a stub",
        description="Generate and apply a stub",
    )
    apply_parser.add_argument(
        "module_path",
        type=module_path,
        help="""A string of the form <module>[:<qualname>] (e.g.
my.module:Class.method). This specifies the set of functions/methods for which
we want to generate stubs.  For example, 'foo.bar' will generate stubs for
anything in the module 'foo.bar', while 'foo.bar:Baz' will only generate stubs
for methods attached to the class 'Baz' in module 'foo.bar'. See
https://www.python.org/dev/peps/pep-3155/ for a detailed description of the
qualname format.""",
    )
    apply_parser.add_argument(
        "--sample-count",
        action="store_true",
        default=False,
        help="Print to stderr the numbers of traces stubs are based on",
    )
    apply_parser.add_argument(
        "--ignore-existing-annotations",
        action="store_const",
        dest="existing_annotation_strategy",
        default=ExistingAnnotationStrategy.REPLICATE,
        const=ExistingAnnotationStrategy.IGNORE,
        help="Ignore existing annotations when applying stubs from traces.",
    )
    apply_parser.add_argument(
        "--pep_563",
        action="store_true",
        default=False,
        help="""Add the "from __future__ import annotation" import at the top
and keep the newly imported modules inside the "if TYPE_CHECKING" block."""
    )
    apply_parser.set_defaults(handler=apply_stub_handler)

    stub_parser = subparsers.add_parser(
        "stub", help="Generate a stub", description="Generate a stub"
    )
    stub_parser.add_argument(
        "module_path",
        type=module_path,
        help="""A string of the form <module>[:<qualname>] (e.g.
my.module:Class.method). This specifies the set of functions/methods for which
we want to generate stubs.  For example, 'foo.bar' will generate stubs for
anything in the module 'foo.bar', while 'foo.bar:Baz' will only generate stubs
for methods attached to the class 'Baz' in module 'foo.bar'. See
https://www.python.org/dev/peps/pep-3155/ for a detailed description of the
qualname format.""",
    )
    stub_parser.add_argument(
        "--sample-count",
        action="store_true",
        default=False,
        help="Print to stderr the numbers of traces stubs are based on",
    )
    group = stub_parser.add_mutually_exclusive_group()
    group.add_argument(
        "--ignore-existing-annotations",
        action="store_const",
        dest="existing_annotation_strategy",
        default=ExistingAnnotationStrategy.REPLICATE,
        const=ExistingAnnotationStrategy.IGNORE,
        help="Ignore existing annotations and generate stubs only from traces.",
    )
    group.add_argument(
        "--omit-existing-annotations",
        action="store_const",
        dest="existing_annotation_strategy",
        default=ExistingAnnotationStrategy.REPLICATE,
        const=ExistingAnnotationStrategy.OMIT,
        help="Omit from stub any existing annotations in source. Implied by --apply.",
    )
    stub_parser.add_argument(
        "--diff",
        action="store_true",
        default=False,
        help="Compare stubs generated with and without considering existing annotations.",
    )
    stub_parser.set_defaults(handler=print_stub_handler)

    list_modules_parser = subparsers.add_parser(
        "list-modules",
        help="Listing of the unique set of module traces",
        description="Listing of the unique set of module traces",
    )
    list_modules_parser.set_defaults(handler=list_modules_handler)

    args = parser.parse_args(argv)
    args.config = get_monkeytype_config(args.config)
    update_args_from_config(args)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help(file=stderr)
        return 1

    with args.config.cli_context(args.command):
        try:
            handler(args, stdout, stderr)
        except HandlerError as err:
            print(f"ERROR: {err}", file=stderr)
            return 1

    return 0


def entry_point_main() -> "NoReturn":
    """Wrapper for main() for setuptools console_script entry point."""
    # Since monkeytype needs to import the user's code (and possibly config
    # code), the user's code must be on the Python path. But when running the
    # CLI script, it won't be. So we add the current working directory to the
    # Python path ourselves.
    sys.path.insert(0, os.getcwd())
    sys.exit(main(sys.argv[1:], sys.stdout, sys.stderr))
