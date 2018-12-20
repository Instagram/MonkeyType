import json
from dataclasses import dataclass
from enum import Enum
from functools import reduce
from typing import Dict, Any, Optional, Set

from mypy_extensions import TypedDict

from monkeytype.type_dict import type_to_dict, type_from_dict


class TypeMetadataKind(str, Enum):
    DictTypeMetadata = 'DictTypeMetadata'
    ListTypeMetadata = 'ListTypeMetadata'
    UnionTypeMetadata = 'UnionTypeMetadata'
    TypTypeMetadata = 'TypTypeMetadata'


class TypeMetadata:
    val: Any
    kind: TypeMetadataKind


@dataclass(
    frozen=True,
)
class DictTypeMetadata(TypeMetadata):
    val: Dict[
        str,
        Optional[TypeMetadata],
    ]
    kind = TypeMetadataKind.DictTypeMetadata


@dataclass(
    frozen=True,
)
class ListTypeMetadata(TypeMetadata):
    val: TypeMetadata
    kind = TypeMetadataKind.ListTypeMetadata


@dataclass(
    frozen=True,
)
class UnionTypeMetadata(TypeMetadata):
    val: Set[TypeMetadata]
    kind = TypeMetadataKind.UnionTypeMetadata


@dataclass(
    frozen=True,
)
class TypTypeMetadata(TypeMetadata):
    val: type
    kind = TypeMetadataKind.TypTypeMetadata


EncodedTypeMetadata = TypedDict('EncodedTypeMetadata', {
    'kind': TypeMetadataKind,
    'val': Any,
})


def get_type_metadata(
        obj: Any,
        recursion_nth: int = 0,
        recursion_max: int = 10
) -> Optional[TypeMetadata]:
    if recursion_nth > recursion_max:
        return None
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
        def combine(union_meta: UnionTypeMetadata, current: Any) -> UnionTypeMetadata:
            type_metadata = get_type_metadata(current, recursion_nth + 1, recursion_max)
            if type_metadata is None:
                return union_meta
            unions = union_meta.val or set()
            unions.add(type_metadata)
            return UnionTypeMetadata(unions)

        combined_metadata = reduce(combine, obj, UnionTypeMetadata(set()))
        return ListTypeMetadata(
            combined_metadata
        )

    return TypTypeMetadata(
        typ,
    )


def encode_type_metadata(type_metadata: Optional[TypeMetadata]) -> Optional[EncodedTypeMetadata]:
    if type_metadata is None:
        return None
    kind = type_metadata.kind
    val = type_metadata.val

    if isinstance(type_metadata, DictTypeMetadata):
        encoded_structure = {
            key: encode_type_metadata(value)
            for key, value in val.items()
        }
        return EncodedTypeMetadata({
            'kind': kind,
            'val': encoded_structure,
        })

    elif isinstance(type_metadata, ListTypeMetadata):
        return EncodedTypeMetadata({
            'kind': kind,
            'val': encode_type_metadata(type_metadata.val),
        })
    elif isinstance(type_metadata, UnionTypeMetadata):
        unions = [
            encode_type_metadata(a)
            for a in list(type_metadata.val)
        ]
        return EncodedTypeMetadata({
            'kind': kind,
            'val': unions,
        })
    elif isinstance(type_metadata, TypTypeMetadata):
        return EncodedTypeMetadata({
            'kind': kind,
            'val': type_to_dict(type_metadata.val),
        })
    return None


def combine_type_metadata(a: TypeMetadata, b: TypeMetadata) -> TypeMetadata:
    if a is None:
        return b
    elif b is None:
        return a
    elif a == b:
        return a
    if isinstance(a, UnionTypeMetadata) and isinstance(b, UnionTypeMetadata):
        return UnionTypeMetadata(
            a.val.union(b.val)
        )
    elif isinstance(a, UnionTypeMetadata):
        return UnionTypeMetadata(
            a.val.add(b.val)
        )
    elif isinstance(b, UnionTypeMetadata):
        return UnionTypeMetadata(
            b.val.add(a.val)
        )
    else:
        return UnionTypeMetadata(
            set([a, b])
        )


def decode_arg_types_metadata_from_json(
        args_type_metadata_json: Optional[str],
) -> Optional[Dict[str, TypeMetadata]]:
    if args_type_metadata_json is None:
        return None

    loaded_args_type_metadata = json.loads(args_type_metadata_json)
    if type(loaded_args_type_metadata) != dict:
        return None
    decoded = {
        key: decode_type_metadata_from_dict(value)
        for (key, value) in loaded_args_type_metadata.items()
        if value is not None
    }
    return {
        key: value
        for (key, value) in decoded.items()
        if value is not None
    }


def decode_type_metadata_from_json(type_metadata_json: Optional[str]) -> Optional[TypeMetadata]:
    if type_metadata_json is None:
        return None

    json_loaded = json.loads(type_metadata_json)
    if type(json_loaded) != dict:
        return None
    return decode_type_metadata_from_dict(json_loaded)


def decode_type_metadata_from_dict(
        type_metadata_dict: Optional[Dict[str, Any]],
) -> Optional[TypeMetadata]:
    if type_metadata_dict is None:
        return None
    try:
        encoded_type_metadata = EncodedTypeMetadata({
            'kind': type_metadata_dict['kind'],
            'val': type_metadata_dict['val'],
        })
        return decode_type_metadata(encoded_type_metadata)
    except Exception:
        return None


def decode_type_metadata(encoded_type_metadata: EncodedTypeMetadata) -> Optional[TypeMetadata]:
    if encode_type_metadata is None:
        return None

    encoded_kind = encoded_type_metadata.get('kind')
    encoded_val = encoded_type_metadata.get('val')
    if encoded_kind is None or encoded_val is None:
        return None

    elif encoded_kind == TypeMetadataKind.DictTypeMetadata:
        structure = {
            key: decode_type_metadata(value)
            for (key, value) in encoded_val.items()
            if value is not None
        }
        return DictTypeMetadata(structure)

    elif encoded_kind == TypeMetadataKind.ListTypeMetadata:
        val = decode_type_metadata(encoded_val)
        if val is None:
            return None
        return ListTypeMetadata(val)

    elif encoded_kind == TypeMetadataKind.UnionTypeMetadata:
        encoded_unions = [
            e
            for e in encoded_val
            if e is not None
        ]
        unions_list = [
            decode_type_metadata(a)
            for a in encoded_unions
        ]
        return UnionTypeMetadata(
            set([a for a in unions_list if a is not None])
        )
    elif encoded_kind == TypeMetadataKind.TypTypeMetadata:
        typ = type_from_dict(encoded_val)
        return TypTypeMetadata(typ)

    return None
