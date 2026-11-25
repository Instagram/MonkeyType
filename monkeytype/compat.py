# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import types
from typing import Any, ForwardRef, Optional, Tuple, Union
from typing import _GenericAlias  # type: ignore[attr-defined]

from mypy_extensions import _TypedDictMeta  # type: ignore[attr-defined]

try:
    from django.utils.functional import cached_property as cp

    cached_property = cp
except ImportError:
    # Django may not be installed
    cached_property = None


def is_typed_dict(typ: type) -> bool:
    """Test indirectly using _TypedDictMeta because TypedDict does not support `isinstance`."""
    return isinstance(typ, _TypedDictMeta)


def is_any(typ: Any) -> bool:
    return typ is Any


_UnionType: Optional[type] = getattr(types, "UnionType", None)
_GENERIC_TYPES: Tuple[type, ...] = (_GenericAlias,)

try:
    # Python 3.9
    from typing import _SpecialGenericAlias  # type: ignore[attr-defined]

    _GENERIC_TYPES = (*_GENERIC_TYPES, _SpecialGenericAlias)
except ImportError:
    pass

if _UnionType is not None:
    _GENERIC_TYPES = (*_GENERIC_TYPES, _UnionType)


def is_union(typ: Any) -> bool:
    return (
        typ is Union
        or (_UnionType is not None and isinstance(typ, _UnionType))
        or (is_generic(typ) and getattr(typ, "__origin__", None) is Union)
    )


def is_generic(typ: Any) -> bool:
    return typ is Union or isinstance(typ, _GENERIC_TYPES)


def is_generic_of(typ: Any, gen: Any) -> bool:
    origin = getattr(typ, "__origin__", None)
    return is_generic(typ) and origin is gen.__origin__


def qualname_of_generic(typ: Any) -> str:
    if is_union(typ):
        return "Union"
    return str(
        getattr(typ, "_name", None)
        or getattr(typ.__origin__, "_name", None)
        or typ.__origin__.__qualname__
    )


def name_of_generic(typ: Any) -> str:
    if is_union(typ):
        return "Union"
    return str(
        getattr(typ, "_name", None)
        or getattr(typ.__origin__, "_name", None)
        or typ.__origin__.__name__
    )


def is_forward_ref(typ: Any) -> bool:
    return isinstance(typ, ForwardRef)


def make_forward_ref(s: str) -> ForwardRef:
    return ForwardRef(s)


def repr_forward_ref() -> str:
    """For checking the test output when ForwardRef is printed."""
    return "ForwardRef"


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


# HACK: MonkeyType monkey-patches _TypedDictMeta!
# We need this to compare TypedDicts recursively.
_TypedDictMeta.__eq__ = __are_typed_dict_types_equal
