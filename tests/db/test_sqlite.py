# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import pytest
import sqlite3

from monkeytype.db.sqlite import (
    create_call_trace_table,
    SQLiteStore,
)
from monkeytype.tracing import CallTrace


def func(a, b):
    pass


def func2(a, b):
    pass


@pytest.fixture
def store() -> SQLiteStore:
    conn = sqlite3.connect(":memory:")
    create_call_trace_table(conn)
    return SQLiteStore(conn)


def test_round_trip(store):
    """Save and retrieve a trace"""
    trace = CallTrace(func, {"a": int, "b": str}, None)
    store.add([trace])
    thunks = store.filter(func.__module__)
    assert len(thunks) == 1
    assert thunks[0].to_trace() == trace


def test_dedup(store):
    """The store shouldn't return duplicates"""
    trace = CallTrace(func, {"a": int, "b": str}, None)
    store.add([trace, trace, trace, trace])
    thunks = store.filter(func.__module__)
    assert len(thunks) == 1
    assert thunks[0].to_trace() == trace


def test_qualname_filtering(store):
    """Prefix match on qualname"""
    traces = [
        CallTrace(func, {"a": int, "b": str}, None),
        CallTrace(func2, {"a": int, "b": int}, None),
    ]
    store.add(traces)
    thunks = store.filter(func.__module__, qualname_prefix="func")
    assert len(thunks) == 2
    assert traces == [thunk.to_trace() for thunk in thunks]


def test_limit_resultset(store):
    """Limit the number of results returned"""
    traces = [
        CallTrace(func, {"a": int, "b": str}, None),
        CallTrace(func2, {"a": int, "b": int}, None),
    ]
    store.add(traces)
    thunks = store.filter(func.__module__, limit=1)
    assert len(thunks) == 1
