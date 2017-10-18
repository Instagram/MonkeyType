import importlib
import inspect
import types
# _Any and _Union aren't visible from stubs
from typing import (  # type: ignore
    Any,
    Callable,
    Dict,
    GenericMeta,
    _Any,
    _Union,
)

from monkeytype.exceptions import (
    InvalidTypeError,
    NameLookupError,
)
from monkeytype.typing import NoneType


def get_func_fqname(func: Callable) -> str:
    """Return the fully qualified function name"""
    return func.__module__ + '.' + func.__qualname__


def get_func_in_module(module: str, qualname: str) -> Callable:
    """Return the function specified by qualname in module.

    Raises:
        NameLookupError if we can't find the named function
        InvalidTypeError if we the name isn't a function
    """
    func = get_name_in_module(module, qualname)
    # TODO: Incorrect typeshed stub T19057121
    func = inspect.unwrap(func)  # type: ignore
    if isinstance(func, types.MethodType):
        func = func.__func__
    elif isinstance(func, property):
        if func.fget is not None:
            if (func.fset is None) and (func.fdel is None):
                func = func.fget
            else:
                raise InvalidTypeError(
                    f"Property {module}.{qualname} has setter or deleter.")
        else:
            raise InvalidTypeError(
                f"Property {module}.{qualname} is missing getter")
    elif not isinstance(func, (types.FunctionType, types.BuiltinFunctionType)):
        raise InvalidTypeError(
            f"{module}.{qualname} is of type '{type(func)}', not function.")
    return func


def get_name_in_module(
    module: str,
    qualname: str,
    attr_getter: Callable[[Any, str], Any] = None,
) -> Any:
    """Return the python object specified by qualname in module

    Raises:
        NameLookupError if the module/qualname cannot be retrieved.
    """
    if attr_getter is None:
        attr_getter = getattr
    try:
        obj = importlib.import_module(module)
    except ModuleNotFoundError:
        raise NameLookupError("No module named '%s'" % (module,))
    walked = []
    for part in qualname.split('.'):
        walked.append(part)
        try:
            obj = attr_getter(obj, part)
        except AttributeError:
            raise NameLookupError(
                "Module '%s' has no attribute '%s'"
                % (module, '.'.join(walked))
            )
    return obj


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
    """Given a dictionary produced by type_to_dict, return the equivalent type

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
        # mypy compains that a value of type `type` isn't indexable. That's
        # true, but we know typ is a subtype that is indexable. Even checking
        # with hasattr(typ, '__getitem__') doesn't help
        typ = typ[elem_types]  # type: ignore
    return typ
