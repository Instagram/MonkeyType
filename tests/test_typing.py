# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

import pytest

from monkeytype.typing import (
    NoneType,
    RemoveEmptyContainers,
    RewriteConfigDict,
    RewriteLargeUnion,
    get_type,
    get_type_str,
    shrink_types,
)
from .util import Dummy


class TestShrinkType:
    @pytest.mark.parametrize(
        'types, expected_type',
        [
            ([], Any),
            ((int,), int),
            ((int, int, int), int),
            ((int, NoneType), Optional[int]),
            ((int, str), Union[int, str]),
            ((int, str, NoneType), Optional[Union[int, str]]),
        ],
    )
    def test_shrink_types(self, types, expected_type):
        assert shrink_types(types) == expected_type


def helper() -> None:
    pass


def generator() -> Iterator[int]:
    yield 1


class TestGetType:
    @pytest.mark.parametrize(
        'value, expected_type',
        [
            (1, int),
            ('foo', str),
            (Dummy, Type[Dummy]),
            (1.1, float),
            (('a', 1, True), Tuple[str, int, bool]),
            (set(), Set[Any]),
            ({'a', 'b', 'c'}, Set[str]),
            ({'a', 1}, Set[Union[str, int]]),
            ([], List[Any]),
            ([1, 2, 3], List[int]),
            ([1, True], List[Union[int, bool]]),
            ({'a': 1, 'b': 2}, Dict[str, int]),
            ({'a': 1, 2: 'b'}, Dict[Union[str, int], Union[str, int]]),
            (tuple(), Tuple),
            (helper, Callable),
            (lambda x: x, Callable),
            (Dummy().an_instance_method, Callable),
            (len, Callable),
            (generator(), Iterator[Any]),
        ],
    )
    def test_builtin_types(self, value, expected_type):
        """Return the appropriate type for builtins"""
        assert get_type(value) == expected_type

    def test_instance_type(self):
        """Return appropriate type for an instance of a user defined class"""
        assert get_type(Dummy()) == Dummy

    def test_class_type(self):
        """Return the correct type for classes"""
        assert get_type(Dummy) == Type[Dummy]


class TestGetTypeStr:
    @pytest.mark.parametrize(
        'typ, typ_str',
        [
            (str, 'str'),
            (Dummy, 'tests.util.Dummy'),
            (Optional[str], 'typing.Optional[str]'),
            (Dict[str, Dummy], 'typing.Dict[str, tests.util.Dummy]'),
        ],
    )
    def test_get_type_str(self, typ, typ_str):
        assert get_type_str(typ) == typ_str


class TestRemoveEmptyContainers:
    @pytest.mark.parametrize(
        'typ, expected',
        [
            (Union[Set[Any], Set[int]], Set[int]),
            (Union[Dict[Any, Any], Dict[int, int]], Dict[int, int]),
            (
                Union[Set[Any], Set[int], Dict[int, str]],
                Union[Set[int], Dict[int, str]],
            ),
            (Union[str, int], Union[str, int]),
            (Dict[str, Union[List[str], List[Any]]], Dict[str, List[str]]),
            (Union[List[Any], Set[Any]], Union[List[Any], Set[Any]])
        ],
    )
    def test_rewrite(self, typ, expected):
        rewritten = RemoveEmptyContainers().rewrite(typ)
        assert rewritten == expected


class TestRewriteConfigDict:
    @pytest.mark.parametrize(
        'typ,expected',
        [
            # Not all dictionaries; shouldn't rewrite
            (
                Union[Dict[str, int], List[str]],
                Union[Dict[str, int], List[str]],
            ),
            # Not the same key type; shouldn't rewrite
            (
                Union[Dict[str, int], Dict[int, int]],
                Union[Dict[str, int], Dict[int, int]],
            ),
            # Should rewrite
            (
                Union[
                    Dict[str, int],
                    Dict[str, str],
                    Dict[str, Union[int, str]]
                ],
                Dict[str, Union[int, str]],
            ),
        ],
    )
    def test_rewrite(self, typ, expected):
        rewritten = RewriteConfigDict().rewrite(typ)
        assert rewritten == expected


class TestRewriteLargeUnion:
    #        A
    #      __|__
    #     |     |
    #     B     C
    #    _|_   _|_
    #   |   | |   |
    #   D   E F   G
    class A:
        pass

    class B(A):
        pass

    class C(A):
        pass

    class D(B):
        pass

    class E(B):
        pass

    class F(C):
        pass

    class G(C):
        pass

    @pytest.mark.parametrize(
        'typ, expected',
        [
            # Too few elements; shouldn't rewrite
            (Union[int, str], Union[int, str]),
            # Not all tuples; should rewrite to Any
            (Union[Tuple[int, int], List[int], Tuple[int]], Any),
            # Not the same value type for all tuples; should rewrite to Any
            (Union[Tuple[int, str], Tuple[int, int], Tuple[int]], Any),
            # Should rewrite to Tuple[int, ...]
            (
                Union[Tuple[int, int], Tuple[int, int, int], Tuple[int]],
                Tuple[int, ...],
            ),
            # Should rewrite to Tuple[G, ...]
            (Union[Tuple[G, G], Tuple[G, G, G], Tuple[G]], Tuple[G, ...]),
            (Union[B, D, E], B),
            (Union[D, E, F, G], A),
            (Union[int, str, float, bytes], Any),
        ],
    )
    def test_rewrite(self, typ, expected):
        rewritten = RewriteLargeUnion(2).rewrite(typ)
        assert rewritten == expected
