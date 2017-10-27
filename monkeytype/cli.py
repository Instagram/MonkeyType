# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
import argparse

from typing import (
    IO,
    List,
    Optional,
    Tuple,
    Type,
)

from monkeytype.db.base import CallTraceStore
from monkeytype.exceptions import MonkeyTypeError
from monkeytype.stubs import build_module_stubs_from_traces
from monkeytype.typing import (
    NoOpRewriter,
    TypeRewriter,
)

from monkeytype.util import get_name_in_module


def module_path(path: str) -> Tuple[str, Optional[str]]:
    """Parse <module>[:<qualname>] into its constituent parts."""
    parts = path.split(':', 1)
    module = parts.pop(0)
    qualname = parts[0] if parts else None
    return module, qualname


def module_path_with_qualname(path: str) -> Tuple[str, str]:
    """Require that path be of the form <module>:<qualname>."""
    module, qualname = module_path(path)
    if qualname is None:
        raise argparse.ArgumentTypeError('must be of the form <module>:<qualname>')
    return module, qualname


def trace_store_class(class_path: str) -> Type[CallTraceStore]:
    """Constructs a CallTraceStore using the class specified by class_path."""
    module, qualname = module_path_with_qualname(class_path)
    try:
        store_class = get_name_in_module(module, qualname)
    except MonkeyTypeError as mte:
        raise argparse.ArgumentTypeError(f'cannot import {class_path}: {mte}')
    if not issubclass(store_class, CallTraceStore):
        raise argparse.ArgumentTypeError(f'not a subclass of monkeytype.db.base.CallTraceStore')
    return store_class


def type_rewriter(instance_path: str) -> TypeRewriter:
    """Fetches the TypeRewriter specified by instance_path."""
    module, qualname = module_path_with_qualname(instance_path)
    try:
        rewriter = get_name_in_module(module, qualname)
    except MonkeyTypeError as mte:
        raise argparse.ArgumentTypeError(f'cannot import {instance_path}: {mte}')
    if not isinstance(rewriter, TypeRewriter):
        raise argparse.ArgumentTypeError(f'not an instance of monkeytype.typing.TypeRewriter')
    return rewriter


def print_stub_handler(args: argparse.Namespace, stdout: IO, stderr: IO) -> None:
    trace_store = args.trace_store_class.make_store(args.trace_store_dsn)
    module, qualname = args.module_path
    thunks = trace_store.filter(module, qualname, args.limit)
    traces = []
    for thunk in thunks:
        try:
            traces.append(thunk.to_trace())
        except MonkeyTypeError as mte:
            print(f'ERROR: Failed decoding trace: {mte}', file=stderr)
    if not traces:
        print(f'No traces found', file=stderr)
        return
    rewriter = args.type_rewriter
    if args.disable_type_rewriting:
        rewriter = NoOpRewriter()
    stubs = build_module_stubs_from_traces(traces, args.include_unparsable_defaults, rewriter)
    stub = stubs.get(module, None)
    if stub is None:
        print(f'No traces found', file=stderr)
        return
    print(stub.render(), file=stdout)


def main(argv: List[str], stdout: IO, stderr: IO) -> int:
    parser = argparse.ArgumentParser(
        description='Generate and apply stub files from collected type information.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--disable-type-rewriting',
        action='store_true', default=False,
        help='Show types without rewrite rules applied')
    parser.add_argument(
        '--include-unparsable-defaults',
        action='store_true', default=False,
        help="Include functions whose default values aren't valid Python expressions")
    parser.add_argument(
        '--limit',
        type=int, default=2000,
        help='How many traces to return from storage')
    parser.add_argument(
        '--trace-store-class',
        type=trace_store_class,
        default='monkeytype.db.sqlite:SQLiteStore',
        help='The <module>:<qualname> of the call trace store to use to retrieve traces.')
    parser.add_argument(
        '--trace-store-dsn',
        default='monkeytype.sqlite3',
        help='The connection string for the call trace store.')
    parser.add_argument(
        '--type-rewriter',
        type=type_rewriter,
        default='monkeytype.typing:DEFAULT_REWRITER',
        help='The <module>:<qualname> of the type rewriter to use during stub generation.')
    subparsers = parser.add_subparsers()

    stub_parser = subparsers.add_parser(
        'stub',
        help='Generate a stub',
        description='Generate a stub')
    stub_parser.add_argument(
        'module_path',
        type=module_path,
        help="""A string of the form <module>[:<qualname>] (e.g.
my.module:Class.method). This specifies the set of functions/methods for which
we want to generate stubs.  For example, 'foo.bar' will generate stubs for
anything in the module 'foo.bar', while 'foo.bar:Baz' will only generate stubs
for methods attached to the class 'Baz' in module 'foo.bar'. See
https://www.python.org/dev/peps/pep-3155/ for a detailed description of the
qualname format.""")
    stub_parser.set_defaults(handler=print_stub_handler)

    args = parser.parse_args(argv)
    handler = getattr(args, 'handler', None)
    if handler is None:
        parser.print_help(file=stderr)
        return 1
    handler(args, stdout, stderr)
    return 0
