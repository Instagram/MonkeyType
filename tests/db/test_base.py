# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import pytest
import sqlite3

from monkeytype.db.base import CallTraceStoreLogger
from monkeytype.db.sqlite import (
    create_call_trace_table,
    SQLiteStore,
)
from monkeytype.tracing import trace_calls
from _pytest.monkeypatch import MonkeyPatch


def func(a, b):
    pass


def func2(a, b):
    pass


def func3(a, b):
    pass


@pytest.fixture
def logger() -> CallTraceStoreLogger:
    conn = sqlite3.connect(':memory:')
    create_call_trace_table(conn)
    return CallTraceStoreLogger(SQLiteStore(conn))


def test_round_trip(logger):
    from types import ModuleType
    module = ModuleType('__main__')
    module.func = func3
    MonkeyPatch().setattr(module.func, '__module__', '__main__', raising=False)
    assert module.func.__module__ == '__main__'

    with trace_calls(logger):
        module.func(int, str)
        assert len(logger.traces) == 0
        func(int, str)
        assert len(logger.traces) == 1
        func2(int, str)
        assert len(logger.traces) == 2

    assert len(logger.store.filter('__main__')) == 0
    assert len(logger.store.filter(func.__module__)) == 2
