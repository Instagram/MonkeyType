# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import json
import logging

# _Any and _Union aren't visible from stubs
from typing import (  # type: ignore
    Any,
    Callable,
    Dict,
    GenericMeta,
    Iterable,
    Optional,
    Type,
    TypeVar,
    _Any,
    _Union,
)

from monkeytype.db.base import CallTraceThunk
from monkeytype.exceptions import InvalidTypeError
from monkeytype.tracing import CallTrace
from monkeytype.typing import NoneType
from monkeytype.util import (
    get_func_in_module,
    get_name_in_module,
)


logger = logging.getLogger(__name__)


# Types are converted to dictionaries of the following form before
# being JSON encoded and sent to storage:
#
#     {
#         'module': '<module>',
#         'qualname': '<qualname>',
#         'elem_types': [type_dict],
#     }
#
# The corresponding type alias should actually be
#
#     TypeDict = Dict[str, Union[str, TypeDict]]
#
# (or better, a TypedDict) but mypy does not support recursive type aliases:
#  https://github.com/python/mypy/issues/731
TypeDict = Dict[str, Any]


def type_to_dict(typ: type) -> TypeDict:
    """Convert a type into a dictionary representation that we can store.

    The dictionary must:
        1. Be encodable as JSON
        2. Contain enough information to let us reify the type
    """
    # Union and Any are special cases that aren't actually types.
    if isinstance(typ, _Union):
        qualname = 'Union'
    elif isinstance(typ, _Any):
        qualname = 'Any'
    else:
        qualname = typ.__qualname__
    d: TypeDict = {
        'module': typ.__module__,
        'qualname': qualname,
    }
    elem_types = getattr(typ, '__args__', None)
    if elem_types and isinstance(typ, (_Union, GenericMeta)):
        d['elem_types'] = [type_to_dict(t) for t in elem_types]
    return d


_HIDDEN_BUILTIN_TYPES: Dict[str, type] = {
    # NoneType is only accessible via type(None)
    'NoneType': NoneType,
}


def type_from_dict(d: TypeDict) -> type:
    """Given a dictionary produced by type_to_dict, return the equivalent type.

    Raises:
        NameLookupError if we can't reify the specified type
        InvalidTypeError if the named type isn't actually a type
    """
    module, qualname = d['module'], d['qualname']
    if module == 'builtins' and qualname in _HIDDEN_BUILTIN_TYPES:
        typ = _HIDDEN_BUILTIN_TYPES[qualname]
    else:
        typ = get_name_in_module(module, qualname)
    if not isinstance(typ, (type, _Union, _Any)):
        raise InvalidTypeError(
            f"Attribute specified by '{qualname}' in module '{module}' "
            "is of type {type(typ)}, not type."
        )
    elem_type_dicts = d.get('elem_types')
    if elem_type_dicts and isinstance(typ, (_Union, GenericMeta)):
        elem_types = tuple(type_from_dict(e) for e in elem_type_dicts)
        # mypy complains that a value of type `type` isn't indexable. That's
        # true, but we know typ is a subtype that is indexable. Even checking
        # with hasattr(typ, '__getitem__') doesn't help
        typ = typ[elem_types]  # type: ignore
    return typ


def type_to_json(typ: type) -> str:
    """Encode the supplied type as json using type_to_dict."""
    type_dict = type_to_dict(typ)
    return json.dumps(type_dict, sort_keys=True)


def type_from_json(typ_json: str) -> type:
    """Reify a type from the format produced by type_to_json."""
    type_dict = json.loads(typ_json)
    return type_from_dict(type_dict)


def arg_types_to_json(arg_types: Dict[str, type]) -> str:
    """Encode the supplied argument types as json"""
    type_dict = {name: type_to_dict(typ) for name, typ in arg_types.items()}
    return json.dumps(type_dict, sort_keys=True)


def arg_types_from_json(arg_types_json: str) -> Dict[str, type]:
    """Reify the encoded argument types from the format produced by arg_types_to_json."""
    arg_types = json.loads(arg_types_json)
    return {name: type_from_dict(type_dict) for name, type_dict in arg_types.items()}


TypeEncoder = Callable[[type], str]


def maybe_encode_type(encode: TypeEncoder, typ: Optional[type]) -> Optional[str]:
    if typ is None:
        return None
    return encode(typ)


TypeDecoder = Callable[[str], type]


def maybe_decode_type(decode: TypeDecoder, encoded: Optional[str]) -> Optional[type]:
    if (encoded is None) or (encoded == 'null'):
        return None
    return decode(encoded)


CallTraceRowT = TypeVar('CallTraceRowT', bound='CallTraceRow')


class CallTraceRow(CallTraceThunk):
    """A semi-structured call trace where each field has been json encoded."""

    def __init__(
        self,
        module: str,
        qualname: str,
        arg_types: str,
        return_type: Optional[str],
        yield_type: Optional[str]
    ) -> None:
        self.module = module
        self.qualname = qualname
        self.arg_types = arg_types
        self.return_type = return_type
        self.yield_type = yield_type

    @classmethod
    def from_trace(cls: Type[CallTraceRowT], trace: CallTrace) -> CallTraceRowT:
        module = trace.func.__module__
        qualname = trace.func.__qualname__
        arg_types = arg_types_to_json(trace.arg_types)
        return_type = maybe_encode_type(type_to_json, trace.return_type)
        yield_type = maybe_encode_type(type_to_json, trace.yield_type)
        return cls(module, qualname, arg_types, return_type, yield_type)

    def to_trace(self) -> CallTrace:
        function = get_func_in_module(self.module, self.qualname)
        arg_types = arg_types_from_json(self.arg_types)
        return_type = maybe_decode_type(type_from_json, self.return_type)
        yield_type = maybe_decode_type(type_from_json, self.yield_type)
        return CallTrace(function, arg_types, return_type, yield_type)

    def __eq__(self, other):
        if isinstance(other, CallTraceRow):
            return (
                self.module,
                self.qualname,
                self.arg_types,
                self.return_type,
                self.yield_type,
            ) == (
                other.module,
                other.qualname,
                other.arg_types,
                other.return_type,
                other.yield_type,
            )
        return NotImplemented


def serialize_traces(traces: Iterable[CallTrace]) -> Iterable[CallTraceRow]:
    """Serialize an iterable of CallTraces to an iterable of CallTraceRow.

    Catches and logs exceptions, so a failure to serialize one CallTrace doesn't
    lose all traces.

    """
    for trace in traces:
        try:
            yield CallTraceRow.from_trace(trace)
        except Exception:
            logger.exception("Failed to serialize trace")
