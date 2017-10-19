# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
import inspect
from types import FrameType
from typing import (
    Iterator,
    Optional,
)

import pytest

from monkeytype.tracing import (
    CallTrace,
    CallTraceLogger,
    Env,
    get_func,
    trace_calls,
)
from monkeytype.typing import NoneType


class TraceCollector(CallTraceLogger):
    def __init__(self):
        super(TraceCollector, self).__init__()
        self.traces = []

    def log(self, trace: CallTrace):
        self.traces.append(trace)


def simple_add(a: int, b: int) -> int:
    return a + b


def has_optional_kwarg(a: int, b: str = None) -> Optional[FrameType]:
    return inspect.currentframe()


def has_locals(foo: str) -> Optional[FrameType]:
        bar = 'baz'  # noqa - Needed to ensure non-argument locals are present in the returned frame
        return inspect.currentframe()


class GetFuncHelper:
    @staticmethod
    def a_static_method() -> Optional[FrameType]:
        return inspect.currentframe()

    @classmethod
    def a_class_method(cls) -> Optional[FrameType]:
        return inspect.currentframe()

    def an_instance_method(self) -> Optional[FrameType]:
        return inspect.currentframe()

    @property
    def a_property(self) -> Optional[FrameType]:
        return inspect.currentframe()


def a_module_function() -> Optional[FrameType]:
    return inspect.currentframe()


class TestGetFunc:
    @pytest.mark.parametrize(
        'frame, expected_func',
        [
            (GetFuncHelper.a_static_method(), GetFuncHelper.a_static_method),
            (GetFuncHelper.a_class_method(), GetFuncHelper.a_class_method.__func__),
            (GetFuncHelper().an_instance_method(), GetFuncHelper.an_instance_method),
            (a_module_function(), a_module_function),
            (GetFuncHelper().a_property, GetFuncHelper.a_property.fget),
        ],
    )
    def test_get_func(self, frame, expected_func):
        assert get_func(frame) == expected_func


def throw(should_recover: bool) -> None:
    try:
        raise Exception('Testing 123')
    except Exception:
        if should_recover:
            return None
        raise


def nested_throw(should_recover: bool) -> str:
    throw(should_recover)
    return 'Testing 123'


def recover_from_nested_throw() -> str:
    try:
        throw(False)
    except Exception:
        pass
    return 'Testing 123'


def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * i


async def square(n: int) -> int:
    return n * n


async def sum_squares(n: int) -> int:
    tot = 0
    for i in range(n):
        tot += await square(i)
    return tot


def implicit_return_none() -> None:
    pass


def explicit_return_none() -> None:
    return


def call_trace(*args, **kwargs) -> CallTrace:
    return CallTrace(Env.TEST, *args, **kwargs)


class Oracle:
    @property
    def meaning_of_life(self) -> int:
        return 42


@pytest.fixture
def collector() -> TraceCollector:
    return TraceCollector()


class TestCallTracer:
    def test_simple_call(self, collector):
        with trace_calls(Env.TEST, collector):
            simple_add(1, 2)
        assert collector.traces == [call_trace(simple_add, {'a': int, 'b': int}, int)]

    def test_callee_throws(self, collector):
        with trace_calls(Env.TEST, collector):
            try:
                throw(should_recover=False)
            except Exception:
                pass
        assert collector.traces == [call_trace(throw, {'should_recover': bool})]

    def test_nested_callee_throws_caller_doesnt_recover(self, collector):
        with trace_calls(Env.TEST, collector):
            try:
                nested_throw(should_recover=False)
            except Exception:
                pass
        expected = [
            call_trace(throw, {'should_recover': bool}),
            call_trace(nested_throw, {'should_recover': bool}),
        ]
        assert collector.traces == expected

    def test_callee_throws_recovers(self, collector):
        with trace_calls(Env.TEST, collector):
            throw(should_recover=True)
        assert collector.traces == [call_trace(throw, {'should_recover': bool}, NoneType)]

    def test_nested_callee_throws_recovers(self, collector):
        with trace_calls(Env.TEST, collector):
            nested_throw(should_recover=True)
        expected = [
            call_trace(throw, {'should_recover': bool}, NoneType),
            call_trace(nested_throw, {'should_recover': bool}, str),
        ]
        assert collector.traces == expected

    def test_caller_handles_callee_exception(self, collector):
        with trace_calls(Env.TEST, collector):
            recover_from_nested_throw()
        expected = [
            call_trace(throw, {'should_recover': bool}),
            call_trace(recover_from_nested_throw, {}, str),
        ]
        assert collector.traces == expected

    def test_generator_trace(self, collector):
        with trace_calls(Env.TEST, collector):
            for _ in squares(3):
                pass
        assert collector.traces == [call_trace(squares, {'n': int}, NoneType, int)]

    def test_return_none(self, collector):
        """Ensure traces have a return_type of NoneType for functions that return a value of None"""
        with trace_calls(Env.TEST, collector):
            implicit_return_none()
            explicit_return_none()
        expected = [
            call_trace(implicit_return_none, {}, NoneType),
            call_trace(explicit_return_none, {}, NoneType),
        ]
        assert collector.traces == expected

    def test_access_property(self, collector):
        """Check that we correctly trace functions decorated with @property"""
        o = Oracle()
        with trace_calls(Env.TEST, collector):
            o.meaning_of_life
        assert collector.traces == [call_trace(Oracle.meaning_of_life.fget, {'self': Oracle}, int)]
