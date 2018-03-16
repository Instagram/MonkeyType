# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from contextlib import contextmanager
import io
import os
import os.path
import pytest
import sqlite3
import subprocess
import sys
import tempfile
from typing import Iterator

from unittest import mock


from monkeytype import cli
from monkeytype.config import DefaultConfig
from monkeytype.db.sqlite import (
    create_call_trace_table,
    SQLiteStore,
    )
from monkeytype.tracing import CallTrace
from monkeytype.typing import NoneType

from .testmodule import Foo
from .test_tracing import trace_calls


def func_foo():
    Foo(arg1='string', arg2=1)


def func(a, b):
    pass


def func2(a, b):
    pass


def func_anno(a: int, b: str) -> None:
    pass


def func_anno2(a: str, b: str) -> None:
    pass


def super_long_function_with_long_params(
    long_param1: str,
    long_param2: str,
    long_param3: str,
    long_param4: str,
    long_param5: str,
) -> None:
    pass


class LoudContextConfig(DefaultConfig):
    @contextmanager
    def cli_context(self, command: str) -> Iterator[None]:
        print(f"IN SETUP: {command}")
        yield
        print(f"IN TEARDOWN: {command}")


@pytest.fixture
def store_data():
    db_file = tempfile.NamedTemporaryFile(prefix='monkeytype_tests')
    conn = sqlite3.connect(db_file.name)
    create_call_trace_table(conn)
    return SQLiteStore(conn), db_file


@pytest.fixture
def stdout():
    return io.StringIO()


@pytest.fixture
def stderr():
    return io.StringIO()


def test_generate_stub(store_data, stdout, stderr):
    store, db_file = store_data
    traces = [
        CallTrace(func, {'a': int, 'b': str}, NoneType),
        CallTrace(func2, {'a': int, 'b': int}, NoneType),
    ]
    store.add(traces)
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['stub', func.__module__], stdout, stderr)
    expected = """def func(a: int, b: str) -> None: ...


def func2(a: int, b: int) -> None: ...
"""
    assert stdout.getvalue() == expected
    assert stderr.getvalue() == ''
    assert ret == 0


def test_print_stub_ignore_existing_annotations(store_data, stdout, stderr):
    store, db_file = store_data
    traces = [
        CallTrace(func_anno, {'a': int, 'b': int}, int),
    ]
    store.add(traces)
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['stub', func.__module__, '--ignore-existing-annotations'],
                       stdout, stderr)
    expected = """def func_anno(a: int, b: int) -> int: ...
"""
    assert stdout.getvalue() == expected
    assert stderr.getvalue() == ''
    assert ret == 0


def test_get_diff(store_data, stdout, stderr):
    store, db_file = store_data
    traces = [
        CallTrace(func_anno, {'a': int, 'b': int}, int),
        CallTrace(func_anno2, {'a': str, 'b': str}, None),
    ]
    store.add(traces)
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['stub', func.__module__, '--diff'], stdout, stderr)
    expected = """- def func_anno(a: int, b: str) -> None: ...
?                          ^ -     ^^ ^
+ def func_anno(a: int, b: int) -> int: ...
?                          ^^      ^ ^
"""
    assert stdout.getvalue() == expected
    assert stderr.getvalue() == ''
    assert ret == 0


def test_get_diff2(store_data, stdout, stderr):
    store, db_file = store_data
    traces = [
        CallTrace(super_long_function_with_long_params, {
            'long_param1': str,
            'long_param2': str,
            'long_param3': int,
            'long_param4': str,
            'long_param5': int,
        }, None),
        CallTrace(func_anno, {'a': int, 'b': int}, int),
    ]
    store.add(traces)
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['stub', func.__module__, '--diff'], stdout, stderr)
    expected = """- def func_anno(a: int, b: str) -> None: ...
?                          ^ -     ^^ ^
+ def func_anno(a: int, b: int) -> int: ...
?                          ^^      ^ ^


  def super_long_function_with_long_params(
      long_param1: str,
      long_param2: str,
-     long_param3: str,
?                  ^ -
+     long_param3: int,
?                  ^^
      long_param4: str,
-     long_param5: str
?                  ^ -
+     long_param5: int
?                  ^^
  ) -> None: ...
"""
    assert stdout.getvalue() == expected
    assert stderr.getvalue() == ''
    assert ret == 0


@pytest.mark.parametrize('arg, error', [
    (func.__module__, f"No traces found for module {func.__module__}\n"),
    (func.__module__ + ':foo', f"No traces found for specifier {func.__module__}:foo\n"),
])
def test_no_traces(store_data, stdout, stderr, arg, error):
    store, db_file = store_data
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['stub', arg], stdout, stderr)
    assert stderr.getvalue() == error
    assert stdout.getvalue() == ''
    assert ret == 0


def test_display_list_of_modules(store_data, stdout, stderr):
    store, db_file = store_data
    traces = [
        CallTrace(func, {'a': int, 'b': str}, NoneType),
    ]
    store.add(traces)
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['list-modules'], stdout, stderr)

    expected = ""
    assert stderr.getvalue() == expected
    expected = "tests.test_cli\n"
    assert stdout.getvalue() == expected
    assert ret == 0


def test_display_sample_count(capsys, stderr):
    traces = [
        CallTrace(func, {'a': int, 'b': str}, NoneType),
        CallTrace(func, {'a': str, 'b': str}, NoneType),
        CallTrace(func2, {'a': str, 'b': int}, NoneType),
        CallTrace(func2, {'a': int, 'b': str}, NoneType),
        CallTrace(func2, {'a': str, 'b': int}, NoneType)
    ]
    cli.display_sample_count(traces, stderr)
    expected = """Annotation for tests.test_cli.func based on 2 call trace(s).
Annotation for tests.test_cli.func2 based on 3 call trace(s).
"""
    assert stderr.getvalue() == expected


def test_display_sample_count_from_cli(store_data, stdout, stderr):
    store, db_file = store_data
    traces = [
        CallTrace(func, {'a': int, 'b': str}, NoneType),
        CallTrace(func2, {'a': int, 'b': int}, NoneType),
    ]
    store.add(traces)
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['stub', func.__module__, '--sample-count'], stdout, stderr)
    expected = """Annotation for tests.test_cli.func based on 1 call trace(s).
Annotation for tests.test_cli.func2 based on 1 call trace(s).
"""
    assert stderr.getvalue() == expected
    assert ret == 0


def test_retype_failure(store_data, stdout, stderr):
    store, db_file = store_data
    traces = [
        CallTrace(func, {'a': int, 'b': str}, NoneType),
        CallTrace(func2, {'a': int, 'b': int}, NoneType),
    ]
    store.add(traces)
    msg = "this is a test"
    err = subprocess.CalledProcessError(returncode=100, cmd='retype')
    err.stdout = msg.encode()
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        with mock.patch('subprocess.run', side_effect=err):
            ret = cli.main(['apply', func.__module__], stdout, stderr)
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == f"ERROR: Failed applying stub with retype:\n{msg}\n"
    assert ret == 1


def test_cli_context_manager_activated(capsys, stdout, stderr):
    ret = cli.main(['-c', f'{__name__}:LoudContextConfig()', 'stub', 'some.module'], stdout, stderr)
    out, err = capsys.readouterr()
    assert out == "IN SETUP: stub\nIN TEARDOWN: stub\n"
    assert err == ""
    assert ret == 0


def test_pathlike_parameter(store_data, capsys):
    store, db_file = store_data
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        with pytest.raises(SystemExit):
            cli.main(['stub', 'test/foo.py:bar'], stdout, stderr)
        out, err = capsys.readouterr()
        assert "test/foo.py does not look like a valid Python import path" in err


@pytest.mark.usefixtures("collector")
def test_apply_stub_init(store_data, stdout, stderr, collector):
    """Regression test for applying stubs to testmodule/__init__.py style module layout"""
    store, db_file = store_data
    with trace_calls(collector):
        func_foo()

    store.add(collector.traces)

    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['apply', Foo.__module__], stdout, stderr)

    assert ret == 0
    assert 'warning:' not in stdout.getvalue()


def test_apply_stub_file_with_spaces(store_data, stdout, stderr):
    """Regression test for applying a stub to a filename containing spaces"""
    src = """
def my_test_function(a, b):
  return a + b
"""
    with tempfile.TemporaryDirectory(prefix='monkey type') as tempdir:
        module = 'my_test_module'
        src_path = os.path.join(tempdir, module + '.py')
        with open(src_path, 'w+') as f:
            f.write(src)
        with mock.patch('sys.path', sys.path + [tempdir]):
            import my_test_module as mtm
            traces = [CallTrace(mtm.my_test_function, {'a': int, 'b': str}, NoneType)]
            store, db_file = store_data
            store.add(traces)
            with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
                ret = cli.main(['apply', 'my_test_module'], stdout, stderr)
    assert ret == 0
    assert 'warning:' not in stdout.getvalue()
