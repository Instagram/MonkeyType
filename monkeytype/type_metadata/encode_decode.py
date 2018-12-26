import json
from typing import Any, Optional, Dict

from mypy_extensions import TypedDict

from monkeytype.type_dict import type_to_dict, type_from_dict
from monkeytype.type_metadata.__base__ import (
    TypeMetadataKind,
    TypeMetadata,
    DictTypeMetadata,
    ListTypeMetadata,
    UnionTypeMetadata,
    TypTypeMetadata
)

EncodedTypeMetadata = TypedDict('EncodedTypeMetadata', {
    'kind': TypeMetadataKind,
    'val': Any,
})


class TypeMetadataEncodeException(Exception):
    pass


class TypeMetadataDecodeException(Exception):
    pass


def encode_type_metadata(type_metadata: TypeMetadata) -> EncodedTypeMetadata:
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
    raise TypeMetadataEncodeException()


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


def decode_type_metadata_from_json(type_metadata_json: str) -> TypeMetadata:
    json_loaded = json.loads(type_metadata_json)
    if type(json_loaded) != dict:
        raise TypeMetadataDecodeException()
    return decode_type_metadata_from_dict(json_loaded)


def decode_type_metadata_from_dict(
        type_metadata_dict: Dict[str, Any],
) -> TypeMetadata:
    encoded_type_metadata = EncodedTypeMetadata({
        'kind': type_metadata_dict['kind'],
        'val': type_metadata_dict['val'],
    })
    return decode_type_metadata(encoded_type_metadata)


def decode_type_metadata(encoded_type_metadata: EncodedTypeMetadata) -> TypeMetadata:
    encoded_kind = encoded_type_metadata.get('kind')
    encoded_val = encoded_type_metadata.get('val')
    if encoded_kind is None or encoded_val is None:
        raise TypeMetadataDecodeException()

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

    raise TypeMetadataDecodeException()
