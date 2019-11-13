# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from collections import defaultdict
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple as typing_Tuple,
    Type,
    Union,
    Generator,
)

import pytest

from monkeytype.typing import (
    NoneType,
    RemoveEmptyContainers,
    RewriteConfigDict,
    RewriteLargeUnion,
    get_type,
    get_type_str,
    is_typed_dict,
    shrink_types,
    shrink_typed_dict_types,
    typed_dict_to_dict,
    RewriteGenerator,
    DUMMY_TYPED_DICT_NAME,
)

from mypy_extensions import TypedDict

from .util import Dummy


class TestShrinkType:
    @pytest.mark.parametrize(
        'types, expected_type',
        [
            (
                (
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                ),
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
            ),
            # Extra key in one dictionary - fall back to Union, which gives Dict[str, int].
            (
                (
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int}),
                ),
                Dict[str, int],
            ),
            # Same key has different value type - fall back to Union.
            (
                (
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': str, 'b': int}),
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                ),
                Union[Dict[str, Union[str, int]], Dict[str, int]],
            ),
            # Different keys -- fall back to union.
            (
                (
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': str}),
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'b': int}),
                ),
                Union[Dict[str, str], Dict[str, int]],
            ),
        ],
    )
    def test_shrink_typed_dict_types(self, types, expected_type):
        assert shrink_typed_dict_types(types) == expected_type

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

    @pytest.mark.parametrize(
        'types, expected_type',
        [
            # If all are TypedDicts, we get the shrunk TypedDict.
            (
                (
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                ),
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
            ),
            # If not all are TypedDicts, we get the Dict equivalents.
            (
                (
                    TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                    Dict[int, int]
                ),
                Union[Dict[str, int], Dict[int, int]],
            ),
        ],
    )
    def test_shrink_types_mixed_dicts(self, types, expected_type):
        assert shrink_types(types) == expected_type


class TestTypedDictToDict:
    @pytest.mark.parametrize(
        'typ, expected_type',
        [
            # TypedDicts would have been constructed only for string literal keys.
            (TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}), Dict[str, int]),
            (TypedDict(DUMMY_TYPED_DICT_NAME, {'a': str, 'b': int}), Dict[str, Union[str, int]]),
            (TypedDict(DUMMY_TYPED_DICT_NAME, {}), Dict[Any, Any]),
        ],
    )
    def test_typed_dict_to_dict(self, typ, expected_type):
        assert typed_dict_to_dict(typ) == expected_type


class TestTypedDictHelpers:
    @pytest.mark.parametrize(
        'typ, expected',
        [
            (TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}), True),
            (Dict[str, int], False),
            # Regression test.
            (lambda x: x, False),
        ],
    )
    def test_is_typed_dict(self, typ, expected):
        assert is_typed_dict(typ) == expected

    @pytest.mark.parametrize(
        'type1, type2, expected_value',
        [
            (
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                True,
            ),
            (
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}, total=False),
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                False,
            ),
            (
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                Dict[str, int],
                False,
            ),
            (
                Dict[str, int],
                TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
                False,
            ),
            (Dict[str, int], Dict[str, int], True),
            # Recursive equality checks.
            (
                TypedDict(DUMMY_TYPED_DICT_NAME,
                          {'a': TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str})}),
                TypedDict(DUMMY_TYPED_DICT_NAME,
                          {'a': TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str})}),
                True,
            ),
            (
                TypedDict(DUMMY_TYPED_DICT_NAME,
                          {'a': TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': str})}),
                TypedDict(DUMMY_TYPED_DICT_NAME,
                          {'a': TypedDict(DUMMY_TYPED_DICT_NAME, {'a': str, 'b': str})}),
                False,
            ),
        ],
    )
    def test_are_dict_types_equal(self, type1, type2, expected_value):
        assert (type1 == type2) == expected_value


def helper() -> None:
    pass


def generator() -> Iterator[int]:
    yield 1


def get_default_dict(key, value):
    m = defaultdict(lambda: 1)
    m[key] += value
    return m


def get_nested_default_dict(key, value):
    m = defaultdict(lambda: defaultdict(lambda: 1))
    m[key][key] += value
    return m


class TestGetType:

    @pytest.mark.parametrize(
        'value, expected_type',
        [
            (1, int),
            ('foo', str),
            (Dummy, Type[Dummy]),
            (1.1, float),
            (('a', 1, True), typing_Tuple[str, int, bool]),
            (set(), Set[Any]),
            ({'a', 'b', 'c'}, Set[str]),
            ({'a', 1}, Set[Union[str, int]]),
            ([], List[Any]),
            ([1, 2, 3], List[int]),
            ([1, True], List[Union[int, bool]]),
            (tuple(), typing_Tuple[()]),
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

    @pytest.mark.parametrize(
        'value, max_typed_dict_size, expected_dict_type',
        [
            ({}, None, TypedDict(DUMMY_TYPED_DICT_NAME, {})),
            ({'a': 1, 'b': 2}, None, TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int})),
            ({'a': 1, 'b': 2}, 2, TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int})),
            ({'a': 1, 'b': 2}, 1, Dict[str, int]),
            ({'a': 1, 2: 'b'}, None, Dict[Union[str, int], Union[str, int]]),
            (get_default_dict(key=1, value=1), None, DefaultDict[int, int]),
            (get_nested_default_dict(key=1, value=1.0), None, DefaultDict[int, DefaultDict[int, float]]),
        ],
    )
    def test_dict_type(self, value, max_typed_dict_size, expected_dict_type):
        """Return the appropriate type for dictionaries."""
        assert get_type(value, max_typed_dict_size) == expected_dict_type

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
            (TypedDict(DUMMY_TYPED_DICT_NAME, {'a': int, 'b': int}),
             'tests.test_typing.' + DUMMY_TYPED_DICT_NAME),
        ],
    )
    def test_get_type_str(self, typ, typ_str):
        assert get_type_str(typ) == typ_str


class Tuple:
    """A name conflict that is not generic."""
    pass


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
            (Union[List[Any], Set[Any]], Union[List[Any], Set[Any]]),
            (Tuple, Tuple),
            (typing_Tuple[()], typing_Tuple[()]),
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
            (Union[typing_Tuple[int, int], List[int], typing_Tuple[int]], Any),
            # Not the same value type for all tuples; should rewrite to Any
            (
                Union[
                    typing_Tuple[int, str], typing_Tuple[int, int], typing_Tuple[int]
                ],
                Any,
            ),
            # Should rewrite to Tuple[int, ...]
            (
                Union[
                    typing_Tuple[int, int],
                    typing_Tuple[int, int, int],
                    typing_Tuple[int],
                ],
                typing_Tuple[int, ...],
            ),
            # Should rewrite to Tuple[G, ...]
            (
                Union[
                    typing_Tuple[G, G], typing_Tuple[G, G, G], typing_Tuple[G]
                ],
                typing_Tuple[G, ...],
            ),
            (Union[B, D, E], B),
            (Union[D, E, F, G], A),
            (Union[int, str, float, bytes], Any),
        ],
    )
    def test_rewrite(self, typ, expected):
        rewritten = RewriteLargeUnion(2).rewrite(typ)
        assert rewritten == expected


class TestRewriteGenerator:
    @pytest.mark.parametrize(
        'typ, expected',
        [
            # Should not rewrite
            (Generator[int, None, int], Generator[int, None, int]),

            # Should not rewrite
            (Generator[int, int, None], Generator[int, int, None]),

            # Should rewrite to Iterator[int]
            (Generator[int, NoneType, NoneType], Iterator[int])
        ],
    )
    def test_rewrite(self, typ, expected):
        rewritten = RewriteGenerator().rewrite(typ)
        assert rewritten == expected
