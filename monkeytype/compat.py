# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from typing import Any
from mypy_extensions import _TypedDictMeta  # type: ignore


def is_typed_dict(typ: type) -> bool:
    """Test indirectly using _TypedDictMeta because TypedDict does not support `isinstance`."""
    return isinstance(typ, _TypedDictMeta)


try:
    # Python 3.7
    from typing import Union, _GenericAlias, ForwardRef  # type: ignore

    def is_any(typ: Any) -> bool:
        return typ is Any

    def is_union(typ: Any) -> bool:
        return typ is Union or is_generic(typ) and typ.__origin__ is Union

    try:
        # Python 3.9
        from typing import _SpecialGenericAlias  # type: ignore

        def is_generic(typ: Any) -> bool:
            return typ is Union or isinstance(typ, _GenericAlias) or isinstance(typ, _SpecialGenericAlias)

    except ImportError:
        def is_generic(typ: Any) -> bool:
            return typ is Union or isinstance(typ, _GenericAlias)

    def is_generic_of(typ: Any, gen: Any) -> bool:
        return is_generic(typ) and typ.__origin__ is gen.__origin__

    def qualname_of_generic(typ: Any) -> str:
        return typ._name or typ.__origin__.__qualname__

    def name_of_generic(typ: Any) -> str:
        return typ._name or typ.__origin__.__name__

    def is_forward_ref(typ: Any) -> bool:
        return isinstance(typ, ForwardRef)

    def make_forward_ref(s: str) -> type:
        return ForwardRef(s)

    def repr_forward_ref() -> str:
        """For checking the test output when ForwardRef is printed."""
        return 'ForwardRef'

    def __are_typed_dict_types_equal(type1: type, type2: type) -> bool:
        """Return true if the two TypedDicts are equal.
        Doing this explicitly because
        TypedDict('Foo', {'a': int}) != TypedDict('Foo', {'a': int})."""

        if not is_typed_dict(type2):
            return False
        total1 = getattr(type1, "__total__", True)
        total2 = getattr(type2, "__total__", True)
        return (
            type1.__name__ == type2.__name__
            and total1 == total2
            and type1.__annotations__ == type2.__annotations__
        )

    def types_equal(typ: type, other_type: type) -> bool:
        return typ == other_type

except ImportError:
    # Python 3.6
    from typing import _Any, _Union, GenericMeta, _ForwardRef  # type: ignore

    def is_any(typ: Any) -> bool:
        return isinstance(typ, _Any)

    def is_union(typ: Any) -> bool:
        return isinstance(typ, _Union)

    def is_generic(typ: Any) -> bool:
        return isinstance(typ, (GenericMeta, _Union))

    def is_generic_of(typ: Any, gen: Any) -> bool:
        return issubclass(typ, gen)

    def qualname_of_generic(typ: Any) -> str:
        return typ.__qualname__

    def name_of_generic(typ: Any) -> str:
        return typ.__name__

    def is_forward_ref(typ: Any) -> bool:
        return isinstance(typ, _ForwardRef)

    def make_forward_ref(s: str) -> type:
        return _ForwardRef(s)

    def repr_forward_ref() -> str:
        """For checking the test output when ForwardRef is printed."""
        return '_ForwardRef'

    def __are_typed_dict_types_equal(type1: type, type2: type) -> bool:
        """Return true if the two TypedDicts are equal.
        Doing this explicitly because
        TypedDict('Foo', {'a': int}) != TypedDict('Foo', {'a': int})."""

        if not is_typed_dict(type2):
            return False
        total1 = getattr(type1, "__total__", True)
        total2 = getattr(type2, "__total__", True)
        return (type1.__name__ == type2.__name__
                and total1 == total2
                and type1.__annotations__.keys() == type2.__annotations__.keys()
                and all(types_equal(type1.__annotations__[key], type2.__annotations__[key])
                        for key in type1.__annotations__.keys()))

    def types_equal(typ: type, other_type: type) -> bool:
        # Types for which equality with inner TypedDict doesn't work correctly on 3.6.
        special_container_types = ["List", "Dict", "Tuple", "Set", "DefaultDict"]

        if (
            (is_any(typ) and is_any(other_type))
            or (is_union(typ) and is_union(other_type))
            or (is_typed_dict(typ) and is_typed_dict(other_type))
        ):
            pass
        elif is_generic(typ) and is_generic(other_type):
            if (
                name_of_generic(typ) in special_container_types
                and name_of_generic(other_type) in special_container_types
            ):
                args = getattr(typ, "__args__", [])
                other_args = getattr(other_type, "__args__", [])
                return (
                    name_of_generic(typ) == name_of_generic(other_type)
                    and len(args) == len(other_args)
                    and all(types_equal(arg_type, other_arg_type)
                            for arg_type, other_arg_type in zip(args, other_args))
                )
        return typ == other_type


# HACK: MonkeyType monkey-patches _TypedDictMeta!
# We need this to compare TypedDicts recursively.
_TypedDictMeta.__eq__ = __are_typed_dict_types_equal
