# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import json
import logging
from typing import (
    Callable,
    Iterable,
    Optional,
    Type,
    TypeVar,
)

from monkeytype.db.base import CallTraceThunk
from monkeytype.tracing import CallTrace
from monkeytype.type_dict import (
    arg_types_from_json, arg_types_to_json,
    type_from_json, type_to_json,
)
from monkeytype.type_metadata import (
    encode_type_metadata,
    decode_type_metadata_from_json, decode_arg_types_metadata_from_json)
from monkeytype.util import (
    get_func_in_module,
)

logger = logging.getLogger(__name__)

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
        yield_type: Optional[str],
        arg_types_metadata: Optional[str],
        return_type_metadata: Optional[str],
        yield_type_metadata: Optional[str],
    ) -> None:
        self.module = module
        self.qualname = qualname
        self.arg_types = arg_types
        self.return_type = return_type
        self.yield_type = yield_type
        self.arg_types_metadata = arg_types_metadata
        self.return_type_metadata = return_type_metadata
        self.yield_type_metadata = yield_type_metadata

    @classmethod
    def from_trace(cls: Type[CallTraceRowT], trace: CallTrace) -> CallTraceRowT:
        return cls(
            module=trace.func.__module__,
            qualname=trace.func.__qualname__,
            arg_types=arg_types_to_json(trace.arg_types),
            return_type=maybe_encode_type(type_to_json, trace.return_type),
            yield_type=maybe_encode_type(type_to_json, trace.yield_type),
            arg_types_metadata=json.dumps({
                key: encode_type_metadata(value)
                for (key, value) in trace.arg_types_metadata.items()
            }) if trace.arg_types_metadata is not None
            else None,
            return_type_metadata=json.dumps(
                encode_type_metadata(trace.return_type_metadata)
            ),
            yield_type_metadata=json.dumps(
                encode_type_metadata(trace.yield_type_metadata)
            ),
        )

    def to_trace(self) -> CallTrace:
        return CallTrace(
            func=get_func_in_module(self.module, self.qualname),
            arg_types=arg_types_from_json(self.arg_types),
            return_type=maybe_decode_type(
                type_from_json, self.return_type,
            ),
            yield_type=maybe_decode_type(
                type_from_json, self.yield_type,
            ),
            arg_types_metadata=decode_arg_types_metadata_from_json(
                self.arg_types_metadata
            ) or {},
            return_type_metadata=decode_type_metadata_from_json(
                self.return_type_metadata,
            ),
            yield_type_metadata=decode_type_metadata_from_json(
                self.yield_type_metadata,
            )
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CallTraceRow):
            return (
                self.module,
                self.qualname,
                self.arg_types,
                self.return_type,
                self.yield_type,
                self.arg_types_metadata,
                self.return_type_metadata,
                self.yield_type_metadata,
            ) == (
                other.module,
                other.qualname,
                other.arg_types,
                other.return_type,
                other.yield_type,
                other.arg_types_metadata,
                other.return_type_metadata,
                other.yield_type_metadata,
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
