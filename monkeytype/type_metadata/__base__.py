from enum import Enum
from functools import reduce
from typing import (
    NamedTuple, Dict, Set,
    Any, Optional,
    Callable,
)


class TypeMetadataKind(str, Enum):
    DictTypeMetadata = 'DictTypeMetadata'
    ListTypeMetadata = 'ListTypeMetadata'
    UnionTypeMetadata = 'UnionTypeMetadata'
    TypTypeMetadata = 'TypTypeMetadata'
    __Base__ = '__BaseTypeMetadataKind'


class TypeMetadata(NamedTuple):
    val: Any
    kind: TypeMetadataKind = TypeMetadataKind.__Base__


class DictTypeMetadata(TypeMetadata):
    val: Dict[
        str,
        Optional[TypeMetadata],
    ]
    kind = TypeMetadataKind.DictTypeMetadata


class ListTypeMetadata(TypeMetadata):
    val: TypeMetadata
    kind = TypeMetadataKind.ListTypeMetadata


class UnionTypeMetadata(TypeMetadata):
    val: Set[TypeMetadata]
    kind = TypeMetadataKind.UnionTypeMetadata


class TypTypeMetadata(TypeMetadata):
    val: type
    kind = TypeMetadataKind.TypTypeMetadata


class AnyTypeMetadata(TypeMetadata):
    val: None


def combine(
        recursion_nth: int,
        recursion_max: int,
) -> Callable[[UnionTypeMetadata, Any], UnionTypeMetadata]:
    def __combine(
            union_meta: UnionTypeMetadata,
            current: Any,
    ) -> UnionTypeMetadata:
        type_metadata = get_type_metadata(current, recursion_nth + 1, recursion_max)
        if type_metadata is None:
            return union_meta
        unions = union_meta.val or set()
        unions.add(type_metadata)
        return UnionTypeMetadata(unions)
    return __combine


def get_type_metadata(
        obj: Any,
        recursion_nth: int = 0,
        recursion_max: int = 10
) -> Optional[TypeMetadata]:
    if recursion_nth > recursion_max:
        return AnyTypeMetadata(None)
    typ = type(obj)
    if typ is dict:
        return DictTypeMetadata({
            key: get_type_metadata(
                value,
                recursion_nth + 1,
                recursion_max,
            ) for key, value in obj.items()
        })
    if typ is list:
        combined_metadata = reduce(
            combine(recursion_nth, recursion_max),
            obj,
            UnionTypeMetadata(set()),
        )
        return ListTypeMetadata(
            combined_metadata
        )

    return TypTypeMetadata(
        typ,
    )


def combine_type_metadata(a: Optional[TypeMetadata], b: Optional[TypeMetadata]) -> Optional[TypeMetadata]:
    if a is None or b is None or a == b:
        return a or b
    if isinstance(a, UnionTypeMetadata) and isinstance(b, UnionTypeMetadata):
        return UnionTypeMetadata(
            a.val.union(b.val)
        )
    elif isinstance(a, UnionTypeMetadata):
        return UnionTypeMetadata(
            a.val.union([b])
        )
    elif isinstance(b, UnionTypeMetadata):
        return UnionTypeMetadata(
            b.val.union([a])
        )
    return UnionTypeMetadata(
        set([a, b])
    )
