from typing import Any

try:
    # Python 3.7
    from typing import Union, _GenericAlias  # type: ignore

    def is_any(typ: Any) -> bool:
        return typ is Any

    def is_union(typ: Any) -> bool:
        return typ is Union or is_generic(typ) and typ.__origin__ is Union

    def is_generic(typ: Any) -> bool:
        return typ is Union or isinstance(typ, _GenericAlias)

    def is_generic_of(typ: Any, gen: Any) -> bool:
        return is_generic(typ) and typ.__origin__ is gen.__origin__

    def qualname_of_generic(typ: Any) -> str:
        return typ._name or typ.__origin__.__qualname__

    def name_of_generic(typ: Any) -> str:
        return typ._name or typ.__origin__.__name__

except ImportError:
    # Python 3.6
    from typing import _Any, _Union, GenericMeta  # type: ignore

    def is_any(typ: Any) -> bool:
        return isinstance(typ, _Any)

    def is_union(typ: Any) -> bool:
        return isinstance(typ, _Union)

    def is_generic(typ: Any) -> bool:
        return isinstance(typ, (GenericMeta, _Union))

    def is_generic_of(typ: Any, gen: Any) -> bool:
        return issubclass(typ, gen)

    def qualname_of_generic(typ: Any) -> str:
        return typ.__qualname__

    def name_of_generic(typ: Any) -> str:
        return typ.__name__
