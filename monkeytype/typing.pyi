# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# The shrink_types and get_type functions construct new types at runtime. Mypy
# cannot currently type these functions, so the type signatures live here.
from typing import _Union  # type: ignore
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
)

NoneType: type = ...
NotImplementedType: type = ...
mappingproxy: type = ...


DUMMY_TYPED_DICT_NAME: str = ...


def is_typed_dict(typ: type) -> bool: ...


def is_anonymous_typed_dict(typ: type) -> bool: ...


def shrink_types(types: Iterable[type]) -> type: ...


def get_dict_type(dct: Any, max_typed_dict_size: Optional[int]) -> type: ...


def get_type(obj: Any, max_typed_dict_size: Optional[int]) -> type: ...


def get_type_str(t: type) -> str: ...


def make_iterator(typ: type) -> type: ...


def make_generator(yield_typ: type, send_typ: type, return_typ: type) -> type:
    ...


class TypeRewriter:
    def rewrite_Dict(self, dct: Dict) -> type: ...

    def rewrite_List(self, lst: List) -> type: ...

    def rewrite_Set(self, st: Set) -> type: ...

    def rewrite_Union(self, union: _Union) -> type:  ...

    def rewrite_TypedDict(self, typed_dict: type) -> type: ...

    def rewrite_Tuple(self, tup: Tuple) -> type: ...

    def generic_rewrite(self, typ: type) -> type: ...

    def rewrite(self, typ: type) -> type: ...


class RemoveEmptyContainers(TypeRewriter):
    ...


class RewriteConfigDict(TypeRewriter):
    ...


class RewriteLargeUnion(TypeRewriter):
    def __init__(self, max_union_len: int = 10) -> None: ...


class IGRewriter(TypeRewriter):
    ...


class NoOpRewriter(TypeRewriter):
    ...


class RewriteGenerator(TypeRewriter):
    ...


class RewriteTypedDictToDict(TypeRewriter):
    ...


class ChainedRewriter(TypeRewriter):
    def __init__(self, rewriters: Iterable[TypeRewriter]) -> None: ...


DEFAULT_REWRITER: TypeRewriter = ...
