import json
from typing import (
    Any,
    Dict,
)

from monkeytype.compat import is_any, is_union, is_generic, qualname_of_generic
from monkeytype.exceptions import InvalidTypeError
from monkeytype.typing import NoneType
from monkeytype.util import (
    get_name_in_module,
)

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
    if is_union(typ):
        qualname = 'Union'
    elif is_any(typ):
        qualname = 'Any'
    elif is_generic(typ):
        qualname = qualname_of_generic(typ)
    else:
        qualname = typ.__qualname__
    d: TypeDict = {
        'module': typ.__module__,
        'qualname': qualname,
    }
    elem_types = getattr(typ, '__args__', None)
    if elem_types and is_generic(typ):
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
    if not (
        isinstance(typ, type) or
        is_any(typ) or
        is_generic(typ)
    ):
        raise InvalidTypeError(
            f"Attribute specified by '{qualname}' in module '{module}' "
            f"is of type {type(typ)}, not type."
        )
    elem_type_dicts = d.get('elem_types')
    if elem_type_dicts and is_generic(typ):
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
    return {
        name: type_from_dict(type_dict)
        for name, type_dict in arg_types.items()
    }
