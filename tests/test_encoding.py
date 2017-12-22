# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

import pytest

from monkeytype.encoding import (
    CallTraceRow,
    maybe_decode_type,
    maybe_encode_type,
    type_from_dict,
    type_from_json,
    type_to_dict,
    type_to_json,
    serialize_traces,
)
from monkeytype.exceptions import InvalidTypeError
from monkeytype.tracing import CallTrace
from monkeytype.typing import NoneType
from .util import Outer

from unittest.mock import Mock


def dummy_func(a, b):
    return a + b


class TestTypeConversion:
    @pytest.mark.parametrize(
        'typ',
        [
            # Non-generics
            NoneType,
            int,
            Outer,
            Outer.Inner,
            Any,
            # Simple generics
            Dict[Any, Any],
            Dict[int, str],
            List[str],
            Optional[str],
            Set[int],
            Tuple[int, str, str],
            Type[Outer],
            Union[Outer.Inner, str, None],
            # Nested generics
            Dict[str, Union[str, int]],
            List[Optional[str]],
            # Let's get craaaazy
            Dict[
                str,
                Union[
                    Dict[str, int],
                    Set[Outer.Inner],
                    Optional[Dict[str, int]]
                ]
            ],
        ],
    )
    def test_type_round_trip(self, typ):
        assert type_from_dict(type_to_dict(typ)) == typ
        assert type_from_json(type_to_json(typ)) == typ

    def test_trace_round_trip(self):
        trace = CallTrace(dummy_func, {'a': int, 'b': int}, int)
        assert CallTraceRow.from_trace(trace).to_trace() == trace

    def test_convert_non_type(self):
        with pytest.raises(InvalidTypeError):
            type_from_dict({
                'module': Outer.Inner.f.__module__,
                'qualname': Outer.Inner.f.__qualname__,
            })

    @pytest.mark.parametrize(
        'encoder, typ, expected, should_call_encoder',
        [
            (Mock(), None, None, False),
            (Mock(return_value='foo'), str, 'foo', True),
        ]
    )
    def test_maybe_encode_type(self, encoder, typ, expected, should_call_encoder):
        ret = maybe_encode_type(encoder, typ)
        if should_call_encoder:
            encoder.assert_called_with(typ)
        else:
            encoder.assert_not_called()
        assert ret == expected

    @pytest.mark.parametrize(
        'encoder, typ, expected, should_call_encoder',
        [
            (Mock(), None, None, False),
            (Mock(), 'null', None, False),
            (Mock(return_value='foo'), 'str', 'foo', True),
        ]
    )
    def test_maybe_decode_type(self, encoder, typ, expected, should_call_encoder):
        ret = maybe_decode_type(encoder, typ)
        if should_call_encoder:
            encoder.assert_called_with(typ)

        else:
            encoder.assert_not_called()
        assert ret == expected


class TestSerializeTraces:
    def test_log_failure_and_continue(self, caplog):
        traces = [
            CallTrace(dummy_func, {'a': int, 'b': int}, int),
            CallTrace(object(), {}),  # object() will fail to serialize
            CallTrace(dummy_func, {'a': str, 'b': str}, str),
        ]
        rows = list(serialize_traces(traces))
        expected = [
            CallTraceRow.from_trace(traces[0]),
            CallTraceRow.from_trace(traces[2]),
        ]
        assert rows == expected
        assert [r.msg for r in caplog.records] == ["Failed to serialize trace"]
