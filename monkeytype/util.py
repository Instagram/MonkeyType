# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import importlib
import inspect
import types

try:
    from django.utils.functional import cached_property  # type: ignore
except ImportError:
    cached_property = None

from typing import (
    Any,
    Callable,
)

from monkeytype.exceptions import (
    InvalidTypeError,
    NameLookupError,
)


def get_func_fqname(func: Callable) -> str:
    """Return the fully qualified function name."""
    return func.__module__ + '.' + func.__qualname__


def get_func_in_module(module: str, qualname: str) -> Callable:
    """Return the function specified by qualname in module.

    Raises:
        NameLookupError if we can't find the named function
        InvalidTypeError if we the name isn't a function
    """
    func = get_name_in_module(module, qualname)
    # TODO: Incorrect typeshed stub, stop arg should be optional
    # https://github.com/python/typeshed/blob/master/stdlib/3/inspect.pyi#L213
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
    elif cached_property and isinstance(func, cached_property):
        func = func.func
    elif not isinstance(func, (types.FunctionType, types.BuiltinFunctionType)):
        raise InvalidTypeError(
            f"{module}.{qualname} is of type '{type(func)}', not function.")
    return func


def get_name_in_module(
    module: str,
    qualname: str,
    attr_getter: Callable[[Any, str], Any] = None,
) -> Any:
    """Return the python object specified by qualname in module.

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
