# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import pytest
from unittest import skipIf

from monkeytype.compat import cached_property
from monkeytype.exceptions import (
    InvalidTypeError,
    NameLookupError,
)
from monkeytype.util import (
    get_func_in_module,
    get_name_in_module,
    pascal_case,
)
from .util import Dummy, Outer


def a_module_func():
    pass


NOT_A_FUNCTION = "not_a_function"


class TestGetNameInModule:
    def test_get_existing_name(self):
        obj = get_name_in_module(a_module_func.__module__, a_module_func.__qualname__)
        assert obj == a_module_func
        # Make sure we handle nested classes
        obj = get_name_in_module(Outer.__module__, Outer.Inner.f.__qualname__)
        assert obj == Outer.Inner.f

    def test_get_nonexistent_module(self):
        with pytest.raises(NameLookupError):
            get_name_in_module("xxx.dontexist", "foo")

    def test_get_nonexistent_qualname(self):
        with pytest.raises(NameLookupError):
            get_name_in_module(a_module_func.__module__, "Outer.xxx_i_dont_exist_xxx")


class TestGetFuncInModule:
    def test_get_method(self):
        """Make sure we return the underlying function for boundmethods"""
        meth = Dummy.a_class_method
        obj = get_func_in_module(meth.__module__, meth.__qualname__)
        assert obj == meth.__func__

    def test_get_property(self):
        """We should be able to look up properties that are only getters"""
        func = Dummy.a_property.fget
        obj = get_func_in_module(func.__module__, func.__qualname__)
        assert obj == func

    def test_get_settable_property(self):
        """We can't disambiguate between getters, setters, and deleters"""
        func = Dummy.a_settable_property.fget
        with pytest.raises(InvalidTypeError):
            get_func_in_module(func.__module__, func.__qualname__)

    @skipIf(cached_property is None, "install Django to run this test")
    def test_get_cached_property(self):
        """We should be able to look up properties that are decorated
        with django.utils.functional.cached_property"""
        func = Dummy.a_cached_property.func
        obj = get_func_in_module(func.__module__, func.__qualname__)
        assert obj == func

    def test_get_non_function(self):
        """Raise an error if lookup returns something that isn't a function"""
        with pytest.raises(InvalidTypeError):
            get_func_in_module(__name__, "NOT_A_FUNCTION")


class Derived(Dummy):
    def an_instance_method(self):
        pass


class TestPascalCase:
    @pytest.mark.parametrize(
        "input_string, expected",
        [
            ("foo", "Foo"),
            ("foo_bar", "FooBar"),
            ("fooBar", "FooBar"),
            ("FooBar", "FooBar"),
            ("_foo___bar_baz__", "FooBarBaz"),
        ],
    )
    def test_pascal_case(self, input_string: str, expected: str):
        assert pascal_case(input_string) == expected
