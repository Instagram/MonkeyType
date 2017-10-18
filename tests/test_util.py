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

from monkeytype.exceptions import (
    InvalidTypeError,
    NameLookupError,
)
from monkeytype.typing import NoneType
from monkeytype.util import (
    get_func_in_module,
    get_name_in_module,
    type_from_dict,
    type_to_dict,
)
from .util import Dummy


def a_module_func():
    pass


class Outer:
    class Inner:
        def f(self) -> None:
            pass


NOT_A_FUNCTION = "not_a_function"


class TestGetNameInModule:
    def test_get_existing_name(self):
        obj = get_name_in_module(
            a_module_func.__module__, a_module_func.__qualname__)
        assert obj == a_module_func
        # Make sure we handle nested classes
        obj = get_name_in_module(Outer.__module__, Outer.Inner.f.__qualname__)
        assert obj == Outer.Inner.f

    def test_get_nonexistant_module(self):
        with pytest.raises(NameLookupError):
            get_name_in_module('xxx.dontexist', 'foo')

    def test_get_nonexistant_qualname(self):
        with pytest.raises(NameLookupError):
            get_name_in_module(
                a_module_func.__module__, 'Outer.xxx_i_dont_exist_xxx')


class TestGetFuncInModule:
    def test_get_method(self):
        """Make sure we return the underyling function for boundmethods"""
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

    def test_get_non_function(self):
        """Raise an error if lookup returns something that isn't a function"""
        with pytest.raises(InvalidTypeError):
            get_func_in_module(__name__, 'NOT_A_FUNCTION')


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
    def test_round_trip(self, typ):
        assert type_from_dict(type_to_dict(typ)) == typ

    def test_convert_non_type(self):
        with pytest.raises(InvalidTypeError):
            type_from_dict({
                'module': Outer.Inner.f.__module__,
                'qualname': Outer.Inner.f.__qualname__,
            })


class Derived(Dummy):
    def an_instance_method(self):
        pass
