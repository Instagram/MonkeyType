# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import inspect
from types import FrameType
from typing import (
    Callable,
    Iterator,
    Optional,
    Tuple,
)

import pytest

from monkeytype.compat import cached_property
from monkeytype.tracing import (
    CallTrace,
    CallTraceLogger,
    get_func,
    trace_calls,
)
from monkeytype.typing import NoneType


class TraceCollector(CallTraceLogger):
    def __init__(self):
        super(TraceCollector, self).__init__()
        self.traces = []
        self.flushed = False

    def log(self, trace: CallTrace):
        self.traces.append(trace)

    def flush(self):
        self.flushed = True


def simple_add(a: int, b: int) -> int:
    return a + b


def uses_kw_only_arg(a: int, *, b: int) -> int:
    return a + b


def has_locals(foo: str) -> Optional[FrameType]:
    bar = "baz"  # noqa - Needed to ensure non-argument locals are present in the returned frame
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

    if cached_property:

        @cached_property
        def a_cached_property(self) -> Optional[FrameType]:
            return inspect.currentframe()


def a_module_function() -> Optional[FrameType]:
    return inspect.currentframe()


class TestGetFunc:
    cases = [
        (GetFuncHelper.a_static_method(), GetFuncHelper.a_static_method),
        (GetFuncHelper.a_class_method(), GetFuncHelper.a_class_method.__func__),
        (GetFuncHelper().an_instance_method(), GetFuncHelper.an_instance_method),
        (a_module_function(), a_module_function),
        (GetFuncHelper().a_property, GetFuncHelper.a_property.fget),
    ]
    if cached_property:
        cases.append(
            (GetFuncHelper().a_cached_property, GetFuncHelper.a_cached_property.func)
        )

    @pytest.mark.parametrize("frame, expected_func", cases)
    def test_get_func(self, frame, expected_func):
        assert get_func(frame) == expected_func


def throw(should_recover: bool) -> None:
    try:
        raise Exception("Testing 123")
    except Exception:
        if should_recover:
            return None
        raise


def nested_throw(should_recover: bool) -> str:
    throw(should_recover)
    return "Testing 123"


def recover_from_nested_throw() -> str:
    try:
        throw(False)
    except Exception:
        pass
    return "Testing 123"


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


def call_method_on_locally_defined_class(n: int) -> Tuple[type, Callable]:
    class Math:
        def square(self, n: int) -> int:
            return n * n

    Math().square(n)
    return Math, Math.square


def call_locally_defined_function(n: int) -> Callable:
    def square(n: int) -> int:
        return n * n

    square(n)
    return square


def implicit_return_none() -> None:
    pass


def explicit_return_none() -> None:
    return


class Oracle:
    @property
    def meaning_of_life(self) -> int:
        return 42


@pytest.fixture
def collector() -> TraceCollector:
    return TraceCollector()


class lazy_property:
    def __init__(self, fget, doc=None):
        self.fget = fget
        self.__doc__ = doc or fget.__doc__
        self.__name__ = fget.__name__

    def get_target_obj(self, obj, cls):
        return obj

    def __get__(self, obj, cls):
        target_obj = self.get_target_obj(obj, cls)
        if target_obj is None:
            return self
        result = self.fget(target_obj)
        setattr(target_obj, self.__name__, result)
        return result


class LazyValue:
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    @lazy_property
    def value(self):
        result = self.func(*self.args, **self.kwargs)
        # Clear the references
        self.func = None
        self.args = None
        self.kwargs = None
        return result


class TestTraceCalls:
    def test_simple_call(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            simple_add(1, 2)
        assert collector.traces == [CallTrace(simple_add, {"a": int, "b": int}, int)]

    def test_kw_only_arg(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            uses_kw_only_arg(1, b=2)
        assert collector.traces == [
            CallTrace(uses_kw_only_arg, {"a": int, "b": int}, int)
        ]

    def test_flushes(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            pass

        assert collector.flushed

    def test_callee_throws(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            try:
                throw(should_recover=False)
            except Exception:
                pass
        assert collector.traces == [CallTrace(throw, {"should_recover": bool})]

    def test_nested_callee_throws_caller_doesnt_recover(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            try:
                nested_throw(should_recover=False)
            except Exception:
                pass
        expected = [
            CallTrace(throw, {"should_recover": bool}),
            CallTrace(nested_throw, {"should_recover": bool}),
        ]
        assert collector.traces == expected

    def test_callee_throws_recovers(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            throw(should_recover=True)
        assert collector.traces == [
            CallTrace(throw, {"should_recover": bool}, NoneType)
        ]

    def test_nested_callee_throws_recovers(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            nested_throw(should_recover=True)
        expected = [
            CallTrace(throw, {"should_recover": bool}, NoneType),
            CallTrace(nested_throw, {"should_recover": bool}, str),
        ]
        assert collector.traces == expected

    def test_caller_handles_callee_exception(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            recover_from_nested_throw()
        expected = [
            CallTrace(throw, {"should_recover": bool}),
            CallTrace(recover_from_nested_throw, {}, str),
        ]
        assert collector.traces == expected

    def test_generator_trace(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            for _ in squares(3):
                pass
        assert collector.traces == [CallTrace(squares, {"n": int}, NoneType, int)]

    def test_locally_defined_class_trace(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            cls, method = call_method_on_locally_defined_class(3)
        assert len(collector.traces) == 2
        assert collector.traces[0] == CallTrace(method, {"self": cls, "n": int}, int)

    def test_locally_defined_function_trace(self, collector):
        with trace_calls(collector, max_typed_dict_size=0):
            function = call_locally_defined_function(3)
        assert len(collector.traces) == 2
        assert collector.traces[0] == CallTrace(function, {"n": int}, int)

    def test_return_none(self, collector):
        """Ensure traces have a return_type of NoneType for functions that return a value of None"""
        with trace_calls(collector, max_typed_dict_size=0):
            implicit_return_none()
            explicit_return_none()
        expected = [
            CallTrace(implicit_return_none, {}, NoneType),
            CallTrace(explicit_return_none, {}, NoneType),
        ]
        assert collector.traces == expected

    def test_access_property(self, collector):
        """Check that we correctly trace functions decorated with @property"""
        o = Oracle()
        with trace_calls(collector, max_typed_dict_size=0):
            o.meaning_of_life
        assert collector.traces == [
            CallTrace(Oracle.meaning_of_life.fget, {"self": Oracle}, int)
        ]

    def test_filtering(self, collector):
        """If supplied, the code filter should decide which code objects are traced"""
        with trace_calls(
            collector,
            max_typed_dict_size=0,
            code_filter=lambda code: code.co_name == "simple_add",
        ):
            simple_add(1, 2)
            explicit_return_none()
        assert collector.traces == [CallTrace(simple_add, {"a": int, "b": int}, int)]

    def test_lazy_value(self, collector):
        """Check that function lookup does not invoke custom descriptors.

        LazyValue is an interesting corner case. Internally, LazyValue stores a
        function and its arguments. When LazyValue.value is accessed for the
        first time, the stored function will be invoked, and its return value
        will be set as the value of LazyValue.value. Additionally, and this is
        important, the reference to the stored function and its arguments are
        cleared.

        When tracing, accessing LazyValue.value generates a 'call' event for a
        function named 'value'.  At the point where we receive the call event,
        the LazyValue.value function is about to begin execution. If we attempt
        to find the called function using getattr, value will be invoked again,
        and the reference to the stored function and its arguments will be
        cleared.  At this point the original call to LazyValue.value will
        resume execution, however, the stored arguments will have been cleared,
        and the attempt to invoke the stored function will fail.
        """
        lazy_val = LazyValue(explicit_return_none)
        with trace_calls(collector, max_typed_dict_size=0):
            lazy_val.value
