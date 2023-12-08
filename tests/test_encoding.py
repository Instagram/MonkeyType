# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from typing import (
    Any,
    Callable,
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
from mypy_extensions import TypedDict
from monkeytype.tracing import CallTrace
from monkeytype.typing import DUMMY_TYPED_DICT_NAME, NoneType, NotImplementedType, mappingproxy
from monkeytype.db.base import CallTraceStore

from .util import Outer

from unittest.mock import Mock


class EmptyStore(CallTraceStore):
    def add(self, traces):
        pass

    def filter(self, module, qualname_prefix=None, limit=2000):
        return []

    def list_modules(self):
        return []


def dummy_func(a, b):
    return a + b


def typed_func(a: int, b: float) -> int:
    return a + int(b)


class TestTypeConversion:
    @pytest.mark.parametrize(
        'typ',
        [
            # Non-generics
            NoneType,
            NotImplementedType,
            mappingproxy,
            int,
            Outer,
            Outer.Inner,
            Any,
            # Simple generics
            Dict,
            Dict[Any, Any],
            Dict[int, str],
            List,
            List[str],
            Optional[str],
            Set[int],
            Tuple[int, str, str],
            Tuple,
            Tuple[()],  # empty tuple
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
        store = EmptyStore()
        assert type_from_dict(type_to_dict(typ), store) == typ
        assert type_from_json(type_to_json(typ), store) == typ

    @pytest.mark.parametrize(
        'typ, expected',
        [
            (
                Dict[str, int],
                {
                    'elem_types': [
                        {'module': 'builtins', 'qualname': 'str'},
                        {'module': 'builtins', 'qualname': 'int'},
                    ],
                    'module': 'typing',
                    'qualname': 'Dict',
                },
            ),
            (
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str}),
                {
                    'elem_types': {
                        'a': {'module': 'builtins', 'qualname': 'int'},
                        'b': {'module': 'builtins', 'qualname': 'str'},
                    },
                    'is_typed_dict': True,
                    'module': 'tests.test_encoding',
                    'qualname': DUMMY_TYPED_DICT_NAME,
                },
            ),
            (
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str})}),
                {
                    'elem_types': {
                        'a': {
                            'elem_types': {
                                'a': {'module': 'builtins', 'qualname': 'int'},
                                'b': {'module': 'builtins', 'qualname': 'str'},
                            },
                            'is_typed_dict': True,
                            'module': 'tests.test_encoding',
                            'qualname': DUMMY_TYPED_DICT_NAME,
                        },
                    },
                    'is_typed_dict': True,
                    'module': 'tests.test_encoding',
                    'qualname': DUMMY_TYPED_DICT_NAME,
                },
            ),
        ],
    )
    def test_type_to_dict(self, typ, expected):
        assert type_to_dict(typ) == expected

    @pytest.mark.parametrize(
        'type_dict, expected',
        [
            (
                {
                    'elem_types': {
                        'a': {'module': 'builtins', 'qualname': 'int'},
                        'b': {'module': 'builtins', 'qualname': 'str'},
                    },
                    'is_typed_dict': True,
                    'module': 'tests.test_encoding',
                    'qualname': DUMMY_TYPED_DICT_NAME,
                },
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str}),
            ),
        ],
    )
    def test_type_from_dict(self, type_dict, expected):
        store = EmptyStore()
        assert type_from_dict(type_dict, store) == expected

    @pytest.mark.parametrize(
        'type_dict, expected',
        [
            (
                {
                    'elem_types': {
                        'a': {
                            'elem_types': {
                                'a': {'module': 'builtins', 'qualname': 'int'},
                                'b': {'module': 'builtins', 'qualname': 'str'},
                            },
                            'is_typed_dict': True,
                            'module': 'tests.test_encoding',
                            'qualname': DUMMY_TYPED_DICT_NAME,
                        },
                    },
                    'is_typed_dict': True,
                    'module': 'tests.test_encoding',
                    'qualname': DUMMY_TYPED_DICT_NAME,
                },
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str})}),
            ),
        ],
    )
    def test_type_from_dict_nested(self, type_dict, expected):
        store = EmptyStore()
        assert type_from_dict(type_dict, store) == expected

    @pytest.mark.parametrize(
        'type_dict, expected',
        [
            (
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str}),
                '{"elem_types": {"a": {"module": "builtins", "qualname": "int"},'
                + ' "b": {"module": "builtins", "qualname": "str"}},'
                + ' "is_typed_dict": true, "module": "tests.test_encoding", "qualname": "DUMMY_NAME"}',
            ),
        ],
    )
    def test_type_to_json(self, type_dict, expected):
        assert type_to_json(type_dict) == expected

    @pytest.mark.parametrize(
        'type_dict_string, expected',
        [
            (
                '{"elem_types": {"a": {"module": "builtins", "qualname": "int"},'
                + ' "b": {"module": "builtins", "qualname": "str"}},'
                + ' "is_typed_dict": true, "module": "tests.test_encoding", "qualname": "DUMMY_NAME"}',
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str}),
            ),
        ],
    )
    def test_type_from_json(self, type_dict_string, expected):
        store = EmptyStore()
        assert type_from_json(type_dict_string, store) == expected

    @pytest.mark.parametrize(
        'type_dict',
        [
            (TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str})),
        ],
    )
    def test_type_round_trip_typed_dict(self, type_dict):
        store = EmptyStore()
        assert type_from_dict(type_to_dict(type_dict), store) == type_dict
        assert type_from_json(type_to_json(type_dict), store) == type_dict

    def test_trace_round_trip(self):
        trace = CallTrace(dummy_func, {'a': int, 'b': int}, int)
        store = EmptyStore()
        assert CallTraceRow.from_trace(trace, store).to_trace(store) == trace

    @pytest.mark.parametrize(
        'obj, type',
        [
            ({
                'module': typed_func.__module__,
                'qualname': typed_func.__qualname__,
            },
             Callable[[int, float], int]),
            ({
                'module': Outer.Inner.f.__module__,
                'qualname': Outer.Inner.f.__qualname__,
            },
             Callable[[], None]
             ),
        ],
    )
    def test_func_types(self, obj, type):
        store = EmptyStore()
        assert type_from_dict(obj, store) == type

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
        store = EmptyStore()
        ret = maybe_decode_type(encoder, typ, store)
        if should_call_encoder:
            encoder.assert_called_with(typ, store)

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
        store = EmptyStore()
        rows = list(serialize_traces(traces, store))
        store = EmptyStore()
        expected = [
            CallTraceRow.from_trace(traces[0], store),
            CallTraceRow.from_trace(traces[2], store),
        ]
        assert rows == expected
        assert [r.msg for r in caplog.records] == ["Failed to serialize trace"]
