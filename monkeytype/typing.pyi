# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from abc import ABC, abstractmethod

# The shrink_types and get_type functions construct new types at runtime. Mypy
# cannot currently type these functions, so the type signatures live here.
from typing import _Union  # type: ignore
from typing import Any, Dict, Generic, Iterable, List, Optional, Set, Tuple, TypeVar

NoneType: type = ...
NotImplementedType: type = ...
mappingproxy: type = ...

DUMMY_TYPED_DICT_NAME: str = ...

def make_typed_dict(
    *,
    required_fields: Optional[Dict[str, type]] = None,
    optional_fields: Optional[Dict[str, type]] = None
) -> type: ...
def field_annotations(typed_dict: type) -> Tuple[Dict[str, type], Dict[str, type]]: ...
def is_typed_dict(typ: type) -> bool: ...
def is_anonymous_typed_dict(typ: type) -> bool: ...
def shrink_types(types: Iterable[type], max_typed_dict_size: int) -> type: ...
def get_dict_type(dct: Any, max_typed_dict_size: int) -> type: ...
def get_type(obj: Any, max_typed_dict_size: int) -> type: ...
def get_type_str(t: type) -> str: ...
def make_iterator(typ: type) -> type: ...
def make_generator(yield_typ: type, send_typ: type, return_typ: type) -> type: ...

T = TypeVar("T")

class GenericTypeRewriter(Generic[T], ABC):
    @abstractmethod
    def make_builtin_tuple(self, elements: Iterable[T]) -> T: ...
    @abstractmethod
    def make_container_type(self, container_type: T, element: T) -> T: ...
    @abstractmethod
    def make_anonymous_typed_dict(
        self, required_fields: Dict[str, T], optional_fields: Dict[str, T]
    ) -> T: ...
    @abstractmethod
    def make_builtin_typed_dict(
        self, name: str, annotations: Dict[str, T], total: bool
    ) -> T: ...
    @abstractmethod
    def generic_rewrite(self, typ: type) -> T: ...
    @abstractmethod
    def rewrite_container_type(self, container_type: Any) -> T: ...
    @abstractmethod
    def rewrite_malformed_container(self, container: Any) -> T: ...
    @abstractmethod
    def rewrite_type_variable(self, type_variable: Any) -> T: ...
    def _rewrite_container(self, cls: Any, container: Any) -> T: ...
    def rewrite_Dict(self, dct: Dict[Any, Any]) -> T: ...
    def rewrite_List(self, lst: List[Any]) -> T: ...
    def rewrite_Set(self, st: Set[Any]) -> T: ...
    def rewrite_Union(self, union: _Union) -> T: ...
    def rewrite_anonymous_TypedDict(self, typed_dict: type) -> T: ...
    def rewrite_TypedDict(self, typed_dict: type) -> T: ...
    def rewrite_Tuple(self, tup: Tuple[Any, ...]) -> T: ...
    def rewrite_Generator(self, generator: Any) -> T: ...
    def rewrite(self, typ: type) -> T: ...

class TypeRewriter(GenericTypeRewriter[type]):
    def make_builtin_tuple(self, elements: Iterable[type]) -> type: ...
    def make_container_type(self, container_type: type, element: type) -> type: ...
    def rewrite_malformed_container(self, container: Any) -> T: ...
    def rewrite_type_variable(self, type_variable: Any) -> T: ...
    def make_anonymous_typed_dict(
        self, required_fields: Dict[str, type], optional_fields: Dict[str, type]
    ) -> type: ...
    def make_builtin_typed_dict(
        self, name: str, annotations: Dict[str, type], total: bool
    ) -> type: ...
    def generic_rewrite(self, typ: type) -> type: ...
    def rewrite_container_type(self, container_type: Any) -> type: ...

class RemoveEmptyContainers(TypeRewriter): ...
class RewriteConfigDict(TypeRewriter): ...

class RewriteLargeUnion(TypeRewriter):
    def __init__(self, max_union_len: int = 10) -> None: ...

class IGRewriter(TypeRewriter): ...
class NoOpRewriter(TypeRewriter): ...
class RewriteGenerator(TypeRewriter): ...

DEFAULT_REWRITER: TypeRewriter = ...
