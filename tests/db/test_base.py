# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import pytest
from monkeytype.db.base import CallTraceStoreLogger
from monkeytype.db.sqlite import (
    SQLiteStore,
)
from monkeytype.tracing import trace_calls
from unittest.mock import patch


def normal_func(a, b):
    pass


def main_func(a, b):
    pass


@pytest.fixture
def logger() -> CallTraceStoreLogger:
    store = SQLiteStore.make_store(':memory:')
    return CallTraceStoreLogger(store)


def test_round_trip(logger):
    with patch.object(main_func, '__module__', '__main__'):
        with trace_calls(logger, max_typed_dict_size=0):
            main_func(int, str)
            assert not logger.traces
            normal_func(int, str)
            assert logger.traces

    assert not logger.store.filter('__main__')
    assert logger.store.filter(normal_func.__module__)
