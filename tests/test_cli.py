# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from contextlib import contextmanager
import io
import os
import pytest
import sqlite3
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


def func(a, b):
    pass


def func2(a, b):
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


def test_no_traces(store_data, stdout, stderr):
    store, db_file = store_data
    with mock.patch.dict(os.environ, {DefaultConfig.DB_PATH_VAR: db_file.name}):
        ret = cli.main(['stub', func.__module__], stdout, stderr)
    assert stderr.getvalue() == "No traces found\n"
    assert stdout.getvalue() == ''
    assert ret == 0


def test_cli_context_manager_activated(capsys, stdout, stderr):
    ret = cli.main(['-c', f'{__name__}:LoudContextConfig()', 'stub', 'some.module'], stdout, stderr)
    out, err = capsys.readouterr()
    assert out == "IN SETUP: stub\nIN TEARDOWN: stub\n"
    assert err == ""
    assert ret == 0
