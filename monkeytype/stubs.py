# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import asyncio
import collections
import enum
import inspect
import logging
import re
from abc import ABCMeta, abstractmethod
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    ForwardRef,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from monkeytype.compat import (
    cached_property,
    is_any,
    is_forward_ref,
    is_generic,
    is_union,
    make_forward_ref,
    qualname_of_generic,
)
from monkeytype.tracing import CallTrace, CallTraceLogger
from monkeytype.typing import (
    GenericTypeRewriter,
    NoneType,
    NoOpRewriter,
    TypeRewriter,
    field_annotations,
    make_generator,
    make_iterator,
    shrink_types,
)
from monkeytype.util import get_name_in_module, pascal_case

logger = logging.getLogger(__name__)


class FunctionKind(enum.Enum):
    MODULE = 0
    CLASS = 1
    INSTANCE = 2
    STATIC = 3
    # Properties are really instance methods, but this is fine for now...
    PROPERTY = 4
    DJANGO_CACHED_PROPERTY = 5

    @classmethod
    def from_callable(cls, func: Callable[..., Any]) -> "FunctionKind":
        if "." not in func.__qualname__:
            return FunctionKind.MODULE
        func_or_desc = get_name_in_module(
            func.__module__, func.__qualname__, inspect.getattr_static
        )
        if isinstance(func_or_desc, classmethod):
            return FunctionKind.CLASS
        elif isinstance(func_or_desc, staticmethod):
            return FunctionKind.STATIC
        elif isinstance(func_or_desc, property):
            return FunctionKind.PROPERTY
        elif cached_property and isinstance(func_or_desc, cached_property):
            return FunctionKind.DJANGO_CACHED_PROPERTY
        return FunctionKind.INSTANCE


class ExistingAnnotationStrategy(enum.Enum):
    """Strategies for handling existing annotations in the source."""

    # Attempt to replicate existing source annotations in the stub. Useful for
    # generating complete-looking stubs for inspection.
    REPLICATE = 0
    # Ignore existing annotations entirely and generate a stub purely from trace
    # data. Probably won't apply cleanly, but useful for comparison purposes.
    IGNORE = 1
    # Generate a stub that omits annotations anywhere the existing source has
    # them. Maximizes likelihood that the stub will cleanly apply using retype.
    OMIT = 2


class ImportMap(DefaultDict[Any, Any]):
    """A mapping of module name to the set of names to be imported."""

    def __init__(self) -> None:
        super().__init__(set)

    def merge(self, other: "ImportMap") -> None:
        for module, names in other.items():
            self[module].update(names)


def _get_import_for_qualname(qualname: str) -> str:
    # Nested classes are annotated using the path from the root class
    # (e.g. Parent.Child, where Child is defined inside Parent)
    return qualname.split(".")[0]


def get_imports_for_annotation(anno: Any) -> ImportMap:
    """Return the imports (module, name) needed for the type in the annotation"""
    imports = ImportMap()
    if (
        anno is inspect.Parameter.empty
        or anno is inspect.Signature.empty
        or not (
            isinstance(anno, type) or is_any(anno) or is_union(anno) or is_generic(anno)
        )
        or anno.__module__ == "builtins"
    ):
        return imports
    if is_any(anno):
        imports["typing"].add("Any")
    elif _is_optional(anno):
        imports["typing"].add("Optional")
        elem_type = _get_optional_elem(anno)
        elem_imports = get_imports_for_annotation(elem_type)
        imports.merge(elem_imports)
    elif is_generic(anno):
        if is_union(anno):
            imports["typing"].add("Union")
        else:
            imports[anno.__module__].add(
                _get_import_for_qualname(qualname_of_generic(anno))
            )
        elem_types = getattr(anno, "__args__", None) or []
        for et in elem_types:
            elem_imports = get_imports_for_annotation(et)
            imports.merge(elem_imports)
    else:
        name = _get_import_for_qualname(anno.__qualname__)
        imports[anno.__module__].add(name)
    return imports


def get_imports_for_signature(sig: inspect.Signature) -> ImportMap:
    """Return the imports (module, name) needed for all types in annotations"""
    imports = ImportMap()
    for param in sig.parameters.values():
        param_imports = get_imports_for_annotation(param.annotation)
        if not _is_optional(param.annotation) and param.default is None:
            imports["typing"].add("Optional")
        imports.merge(param_imports)
    return_imports = get_imports_for_annotation(sig.return_annotation)
    imports.merge(return_imports)
    return imports


def update_signature_args(
    sig: inspect.Signature,
    arg_types: Dict[str, type],
    has_self: bool,
    existing_annotation_strategy: ExistingAnnotationStrategy = ExistingAnnotationStrategy.REPLICATE,
) -> inspect.Signature:
    """Update argument annotations with the supplied types"""
    params = []
    for arg_idx, name in enumerate(sig.parameters):
        param = sig.parameters[name]
        typ = arg_types.get(name)
        typ = inspect.Parameter.empty if typ is None else typ
        is_self = has_self and arg_idx == 0
        annotated = param.annotation is not inspect.Parameter.empty
        if (
            annotated
            and existing_annotation_strategy == ExistingAnnotationStrategy.OMIT
        ):
            # generate no annotation for already-annotated args when generating
            # a stub to apply, avoiding the possibility of "incompatible
            # annotation" errors
            param = param.replace(annotation=inspect.Parameter.empty)
        # Don't touch existing annotations unless asked to ignore them
        if not is_self and (
            (existing_annotation_strategy == ExistingAnnotationStrategy.IGNORE)
            or not annotated
        ):
            param = param.replace(annotation=typ)
        params.append(param)
    return sig.replace(parameters=params)


def update_signature_return(
    sig: inspect.Signature,
    return_type: Optional[type] = None,
    yield_type: Optional[type] = None,
    existing_annotation_strategy: ExistingAnnotationStrategy = ExistingAnnotationStrategy.REPLICATE,
) -> inspect.Signature:
    """Update return annotation with the supplied types"""
    anno = sig.return_annotation
    if anno is not inspect.Signature.empty:
        # If generating a stub to apply and there's already a return type
        # annotation, generate a stub with no return type annotation, to avoid
        # the possibility of "incompatible annotation" errors.
        if existing_annotation_strategy == ExistingAnnotationStrategy.OMIT:
            return sig.replace(return_annotation=inspect.Signature.empty)
        # Don't change pre-existing annotations unless asked to
        if existing_annotation_strategy == ExistingAnnotationStrategy.REPLICATE:
            return sig
    # NB: We cannot distinguish between functions that explicitly only
    # return None and those that do so implicitly. In the case of generator
    # functions both are typed as Iterator[<yield_type>]
    if (yield_type is not None) and (
        (return_type is None) or (return_type == NoneType)
    ):
        anno = make_iterator(yield_type)
    elif (yield_type is not None) and (return_type is not None):
        anno = make_generator(yield_type, NoneType, return_type)
    elif return_type is not None:
        anno = return_type
    return sig.replace(return_annotation=anno)


def shrink_traced_types(
    traces: Iterable[CallTrace],
    max_typed_dict_size: int,
) -> Tuple[Dict[str, type], Optional[type], Optional[type]]:
    """Merges the traced types and returns the minimally equivalent types"""
    arg_types: DefaultDict[str, Set[type]] = collections.defaultdict(set)
    return_types: Set[type] = set()
    yield_types: Set[type] = set()
    for t in traces:
        for arg, typ in t.arg_types.items():
            arg_types[arg].add(typ)
        if t.return_type is not None:
            return_types.add(t.return_type)
        if t.yield_type is not None:
            yield_types.add(t.yield_type)
    shrunken_arg_types = {
        name: shrink_types(ts, max_typed_dict_size) for name, ts in arg_types.items()
    }
    return_type = (
        shrink_types(return_types, max_typed_dict_size) if return_types else None
    )
    yield_type = shrink_types(yield_types, max_typed_dict_size) if yield_types else None
    return (shrunken_arg_types, return_type, yield_type)


def get_typed_dict_class_name(parameter_name: str) -> str:
    """Return the name for a TypedDict class generated for parameter `parameter_name`."""
    return f"{pascal_case(parameter_name)}TypedDict__RENAME_ME__"


class Stub(metaclass=ABCMeta):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    @abstractmethod
    def render(self) -> str:
        pass


class ImportBlockStub(Stub):
    def __init__(self, imports: Optional[ImportMap] = None) -> None:
        self.imports = imports if imports else ImportMap()

    def render(self) -> str:
        imports = []
        for module in sorted(self.imports.keys()):
            names = sorted(self.imports[module])
            if module == "_io":
                module = module[1:]
            if len(names) == 1:
                imports.append("from %s import %s" % (module, names[0]))
            else:
                stanza = ["from %s import (" % (module,)]
                stanza.extend(["    %s," % (name,) for name in names])
                stanza.append(")")
                imports.append("\n".join(stanza))
        return "\n".join(imports)

    def __repr__(self) -> str:
        return "ImportBlockStub(%s)" % (repr(self.imports),)


def _is_optional(anno: Any) -> bool:
    """Is the supplied annotation an instance of the 'virtual' Optional type?

    Optional isn't really a type. It's an alias to Union[T, NoneType]
    """
    return is_union(anno) and NoneType in anno.__args__


def _get_optional_elem(anno: Any) -> Any:
    """Get the non-null type from an optional."""
    if not _is_optional(anno):
        raise TypeError("Supplied annotation isn't an optional")
    elems = tuple(e for e in anno.__args__ if e is not NoneType)
    if len(elems) == 1:
        return elems[0]
    return Union[elems]


class RenderAnnotation(GenericTypeRewriter[str]):
    """Render annotation recursively."""

    def make_anonymous_typed_dict(
        self, required_fields: Dict[str, str], optional_fields: Dict[str, str]
    ) -> str:
        raise Exception(
            "Should not receive an anonymous TypedDict in RenderAnnotation,"
            f" but was called with required_fields={required_fields}, optional_fields={optional_fields}."
        )

    def make_builtin_typed_dict(
        self, name: str, annotations: Dict[str, str], total: bool
    ) -> str:
        raise Exception(
            "Should not receive a TypedDict type in RenderAnnotation,"
            f" but was called with name={name}, annotations={annotations}, total={total}."
        )

    def generic_rewrite(self, typ: Any) -> str:
        if hasattr(typ, "__supertype__"):
            rendered = str(typ.__name__)
        elif is_forward_ref(typ):
            rendered = repr(typ.__forward_arg__)
        elif isinstance(typ, NoneType) or typ is NoneType:
            rendered = "None"
        elif is_generic(typ):
            rendered = repr(typ)
        elif isinstance(typ, type):
            if typ.__module__ in ("builtins",):
                rendered = typ.__qualname__
            else:
                rendered = typ.__module__ + "." + typ.__qualname__
        elif isinstance(typ, str):
            rendered = typ
        else:
            rendered = repr(typ)
        return rendered

    def rewrite_container_type(self, container_type: Any) -> str:
        return repr(container_type)

    def rewrite_malformed_container(self, container: Any) -> str:
        return repr(container)

    def rewrite_type_variable(self, type_variable: Any) -> str:
        rendered = str(type_variable)
        tilde_prefix = "~"
        return (
            rendered[len(tilde_prefix) :]
            if rendered.startswith(tilde_prefix)
            else rendered
        )

    def make_builtin_tuple(self, elements: Iterable[str]) -> str:
        elems = list(elements)
        return ", ".join(elems) if elems else "()"

    def make_container_type(self, container_type: str, elements: str) -> str:
        return f"{container_type}[{elements}]"

    def rewrite_Union(self, union: type) -> str:
        if _is_optional(union):
            elem_type = _get_optional_elem(union)
            return "Optional[" + self.rewrite(elem_type) + "]"
        return self._rewrite_container(Union, union)

    def rewrite(self, typ: type) -> str:
        rendered = super().rewrite(typ)
        if getattr(typ, "__module__", None) == "typing":
            rendered = rendered.replace("typing.", "")
        # Temporary hacky workaround for #76 to fix remaining NoneType hints by search-replace
        rendered = rendered.replace("NoneType", "None")
        return rendered


def render_annotation(anno: Any) -> str:
    """Convert an annotation into its stub representation."""
    return RenderAnnotation().rewrite(anno)


def render_parameter(param: inspect.Parameter) -> str:
    """Convert a parameter into its stub representation.

    NB: This is copied almost entirely from https://github.com/python/cpython/blob/3.6/Lib/inspect.py
    with the modification that it calls our own rendering functions for annotations.

    TODO: push a patch upstream so we don't have to do this on Python 3.x.
    """
    kind = param.kind
    formatted = param.name

    # Add annotation and default value
    if param.annotation is not inspect.Parameter.empty:
        anno = param.annotation
        if not _is_optional(anno) and param.default is None:
            anno = Optional[anno]
        rendered = render_annotation(anno)
        formatted = "{}: {}".format(formatted, rendered)

    if param.default is not inspect.Parameter.empty:
        formatted = "{} = ...".format(formatted)

    if kind == inspect.Parameter.VAR_POSITIONAL:
        formatted = "*" + formatted
    elif kind == inspect.Parameter.VAR_KEYWORD:
        formatted = "**" + formatted

    return formatted


def render_signature(
    sig: inspect.Signature, max_line_len: Optional[int] = None, prefix: str = ""
) -> str:
    """Convert a signature into its stub representation.

    NB: This is copied almost entirely from https://github.com/python/cpython/blob/3.6/Lib/inspect.py
    with the modification that it calls our own rendering functions for annotations.

    TODO: push a patch upstream so we don't have to do this on Python 3.x.
    """
    formatted_params = []
    render_pos_only_separator = False
    render_kw_only_separator = True
    for param in sig.parameters.values():
        formatted = render_parameter(param)
        kind = param.kind

        if kind == inspect.Parameter.POSITIONAL_ONLY:
            render_pos_only_separator = True
        elif render_pos_only_separator:
            # It's not a positional-only parameter, and the flag
            # is set to 'True' (there were pos-only params before.)
            formatted_params.append("/")
            render_pos_only_separator = False

        if kind == inspect.Parameter.VAR_POSITIONAL:
            # OK, we have an '*args'-like parameter, so we won't need
            # a '*' to separate keyword-only arguments
            render_kw_only_separator = False
        elif kind == inspect.Parameter.KEYWORD_ONLY and render_kw_only_separator:
            # We have a keyword-only parameter to render and we haven't
            # rendered an '*args'-like parameter before, so add a '*'
            # separator to the parameters list ("foo(arg1, *, arg2)" case)
            formatted_params.append("*")
            # This condition should be only triggered once, so
            # reset the flag
            render_kw_only_separator = False

        formatted_params.append(formatted)

    if render_pos_only_separator:
        # There were only positional-only parameters, hence the
        # flag was not reset to 'False'
        formatted_params.append("/")

    rendered_return = ""
    if sig.return_annotation is not inspect.Signature.empty:
        anno = render_annotation(sig.return_annotation)
        rendered_return = " -> {}".format(anno)

    # first try render it into one single line, if it doesn't exceed
    # the limit then just use it
    rendered_single_line = "({})".format(", ".join(formatted_params)) + rendered_return
    if max_line_len is None or len(rendered_single_line) <= max_line_len:
        return rendered_single_line

    # add prefix to all lines except the first one
    rendered_multi_lines = ["("]
    for i, f_param in enumerate(formatted_params):
        line = "    " + f_param
        if i != len(formatted_params) - 1:
            line += ","
        rendered_multi_lines.append(prefix + line)
    rendered_multi_lines.append(prefix + ")" + rendered_return)
    return "\n".join(rendered_multi_lines)


class AttributeStub(Stub):
    def __init__(
        self,
        name: str,
        typ: type,
    ) -> None:
        self.name = name
        self.typ = typ

    def render(self, prefix: str = "") -> str:
        return f"{prefix}{self.name}: {render_annotation(self.typ)}"

    def __repr__(self) -> str:
        return f"AttributeStub({self.name}, {self.typ})"


class FunctionStub(Stub):
    def __init__(
        self,
        name: str,
        signature: inspect.Signature,
        kind: FunctionKind,
        strip_modules: Optional[Iterable[str]] = None,
        is_async: bool = False,
    ) -> None:
        self.name = name
        self.signature = signature
        self.kind = kind
        self.strip_modules = strip_modules or []
        self.is_async = is_async

    def render(self, prefix: str = "") -> str:
        s = prefix
        if self.is_async:
            s += "async "
        s += "def " + self.name
        s += render_signature(self.signature, 120 - len(s), prefix) + ": ..."
        # Yes, this is a horrible hack, but inspect.py gives us no way to
        # specify the function that should be used to format annotations.
        for module in self.strip_modules:
            s = s.replace(module + ".", "")
        if self.kind == FunctionKind.CLASS:
            s = prefix + "@classmethod\n" + s
        elif self.kind == FunctionKind.STATIC:
            s = prefix + "@staticmethod\n" + s
        elif self.kind == FunctionKind.PROPERTY:
            s = prefix + "@property\n" + s
        elif self.kind == FunctionKind.DJANGO_CACHED_PROPERTY:
            s = prefix + "@cached_property\n" + s
        return s

    def __repr__(self) -> str:
        return "FunctionStub(%s, %s, %s, %s, %s)" % (
            repr(self.name),
            repr(self.signature),
            repr(self.kind),
            repr(self.strip_modules),
            self.is_async,
        )


class ClassStub(Stub):
    def __init__(
        self,
        name: str,
        function_stubs: Optional[Iterable[FunctionStub]] = None,
        attribute_stubs: Optional[Iterable[AttributeStub]] = None,
    ) -> None:
        self.name = name
        self.function_stubs: Dict[str, FunctionStub] = {}
        self.attribute_stubs = attribute_stubs or []
        if function_stubs is not None:
            self.function_stubs = {stub.name: stub for stub in function_stubs}

    def render(self) -> str:
        parts = [
            f"class {self.name}:",
            *[
                stub.render(prefix="    ")
                for stub in sorted(self.attribute_stubs, key=lambda stub: stub.name)
            ],
            *[
                stub.render(prefix="    ")
                for _, stub in sorted(self.function_stubs.items())
            ],
        ]
        return "\n".join(parts)

    def __repr__(self) -> str:
        return "ClassStub(%s, %s, %s)" % (
            repr(self.name),
            tuple(self.function_stubs.values()),
            tuple(self.attribute_stubs),
        )


class ReplaceTypedDictsWithStubs(TypeRewriter):
    """Replace TypedDicts in a generic type with class stubs and store all the stubs."""

    def __init__(self, class_name_hint: str) -> None:
        self._class_name_hint = class_name_hint
        self.stubs: List[ClassStub] = []

    def _rewrite_container(self, cls: type, container: type) -> type:
        """Rewrite while using the index of the inner type as a class name hint.

        Otherwise, Tuple[TypedDict(...), TypedDict(...)] would give the same
        name for both the generated classes."""
        if container.__module__ != "typing":
            return container
        args = getattr(container, "__args__", None)
        if args is None:
            return container
        elif args == ((),) or args == ():  # special case of empty tuple `Tuple[()]`
            elems: Tuple[Any, ...] = ()
        else:
            # Avoid adding a suffix for the first one so that
            # single-element containers don't have a numeric suffix.
            elems, stub_lists = zip(
                *[
                    self.rewrite_and_get_stubs(
                        elem,
                        class_name_hint=self._class_name_hint
                        + ("" if index == 0 else str(index + 1)),
                    )
                    for index, elem in enumerate(args)
                ]
            )
            for stubs in stub_lists:
                self.stubs.extend(stubs)
        # Value of type "type" is not indexable.
        return cls[elems]  # type: ignore[no-any-return,index]

    def _add_typed_dict_class_stub(
        self,
        fields: Dict[str, type],
        class_name: str,
        base_class_name: str = "TypedDict",
        total: bool = True,
    ) -> None:
        attribute_stubs = []
        for name, typ in fields.items():
            rewritten_type, stubs = self.rewrite_and_get_stubs(
                typ, class_name_hint=name
            )
            attribute_stubs.append(AttributeStub(name, rewritten_type))
            self.stubs.extend(stubs)
        total_flag = "" if total else ", total=False"
        self.stubs.append(
            ClassStub(
                name=f"{class_name}({base_class_name}{total_flag})",
                function_stubs=[],
                attribute_stubs=attribute_stubs,
            )
        )

    def rewrite_anonymous_TypedDict(self, typed_dict: type) -> ForwardRef:  # type: ignore[override]
        class_name = get_typed_dict_class_name(self._class_name_hint)
        required_fields, optional_fields = field_annotations(typed_dict)
        has_required_fields = len(required_fields) != 0
        has_optional_fields = len(optional_fields) != 0
        if not has_required_fields and not has_optional_fields:
            raise Exception(
                "Expected empty TypedDicts to be shrunk as Dict[Any, Any]"
                " but got an empty TypedDict anyway"
            )
        elif has_required_fields and not has_optional_fields:
            self._add_typed_dict_class_stub(required_fields, class_name)
        elif not has_required_fields and has_optional_fields:
            self._add_typed_dict_class_stub(optional_fields, class_name, total=False)
        else:
            self._add_typed_dict_class_stub(required_fields, class_name)
            base_class_name = class_name
            class_name = get_typed_dict_class_name(self._class_name_hint) + "NonTotal"
            self._add_typed_dict_class_stub(
                optional_fields, class_name, base_class_name, total=False
            )
        return make_forward_ref(class_name)

    @staticmethod
    def rewrite_and_get_stubs(
        typ: type, class_name_hint: str
    ) -> Tuple[type, List[ClassStub]]:
        rewriter = ReplaceTypedDictsWithStubs(class_name_hint)
        rewritten_type = rewriter.rewrite(typ)
        return rewritten_type, rewriter.stubs


class ModuleStub(Stub):
    def __init__(
        self,
        function_stubs: Optional[Iterable[FunctionStub]] = None,
        class_stubs: Optional[Iterable[ClassStub]] = None,
        imports_stub: Optional[ImportBlockStub] = None,
        typed_dict_class_stubs: Optional[Iterable[ClassStub]] = None,
    ) -> None:
        self.function_stubs: Dict[str, FunctionStub] = {}
        if function_stubs is not None:
            self.function_stubs = {stub.name: stub for stub in function_stubs}
        self.class_stubs: Dict[str, ClassStub] = {}
        if class_stubs is not None:
            self.class_stubs = {stub.name: stub for stub in class_stubs}
        self.imports_stub = imports_stub if imports_stub else ImportBlockStub()
        self.typed_dict_class_stubs: List[ClassStub] = []
        if typed_dict_class_stubs is not None:
            self.typed_dict_class_stubs = list(typed_dict_class_stubs)

    def render(self) -> str:
        parts = []
        if self.imports_stub.imports:
            parts.append(self.imports_stub.render())
        for typed_dict_class_stub in sorted(
            self.typed_dict_class_stubs, key=lambda s: s.name
        ):
            parts.append(typed_dict_class_stub.render())
        for func_stub in sorted(self.function_stubs.values(), key=lambda s: s.name):
            parts.append(func_stub.render())
        for class_stub in sorted(self.class_stubs.values(), key=lambda s: s.name):
            parts.append(class_stub.render())
        return "\n\n\n".join(parts)

    def __repr__(self) -> str:
        return "ModuleStub(%s, %s, %s, %s)" % (
            tuple(self.function_stubs.values()),
            tuple(self.class_stubs.values()),
            repr(self.imports_stub),
            tuple(self.typed_dict_class_stubs),
        )


class FunctionDefinition:
    _KIND_WITH_SELF = {
        FunctionKind.CLASS,
        FunctionKind.INSTANCE,
        FunctionKind.PROPERTY,
        FunctionKind.DJANGO_CACHED_PROPERTY,
    }

    def __init__(
        self,
        module: str,
        qualname: str,
        kind: FunctionKind,
        sig: inspect.Signature,
        is_async: bool = False,
        typed_dict_class_stubs: Optional[Iterable[ClassStub]] = None,
    ) -> None:
        self.module = module
        self.qualname = qualname
        self.kind = kind
        self.signature = sig
        self.is_async = is_async
        self.typed_dict_class_stubs = typed_dict_class_stubs or []

    @classmethod
    def from_callable(
        cls, func: Callable[..., Any], kind: Optional[FunctionKind] = None
    ) -> "FunctionDefinition":
        kind = FunctionKind.from_callable(func)
        sig = inspect.Signature.from_callable(func)
        is_async = asyncio.iscoroutinefunction(func)
        return FunctionDefinition(
            func.__module__, func.__qualname__, kind, sig, is_async
        )

    @classmethod
    def from_callable_and_traced_types(
        cls,
        func: Callable[..., Any],
        arg_types: Dict[str, type],
        return_type: Optional[type],
        yield_type: Optional[type],
        existing_annotation_strategy: ExistingAnnotationStrategy = ExistingAnnotationStrategy.REPLICATE,
    ) -> "FunctionDefinition":
        typed_dict_class_stubs: List[ClassStub] = []
        new_arg_types = {}
        for name, typ in arg_types.items():
            rewritten_type, stubs = ReplaceTypedDictsWithStubs.rewrite_and_get_stubs(
                typ, class_name_hint=name
            )
            new_arg_types[name] = rewritten_type
            typed_dict_class_stubs.extend(stubs)

        if return_type:
            # Replace the dot in a qualified name.
            class_name_hint = func.__qualname__.replace(".", "_")
            return_type, stubs = ReplaceTypedDictsWithStubs.rewrite_and_get_stubs(
                return_type, class_name_hint
            )
            typed_dict_class_stubs.extend(stubs)

        if yield_type:
            # Replace the dot in a qualified name.
            class_name_hint = func.__qualname__.replace(".", "_") + "Yield"
            yield_type, stubs = ReplaceTypedDictsWithStubs.rewrite_and_get_stubs(
                yield_type, class_name_hint
            )
            typed_dict_class_stubs.extend(stubs)

        function = FunctionDefinition.from_callable(func)
        signature = function.signature
        signature = update_signature_args(
            signature, new_arg_types, function.has_self, existing_annotation_strategy
        )
        signature = update_signature_return(
            signature, return_type, yield_type, existing_annotation_strategy
        )
        return FunctionDefinition(
            function.module,
            function.qualname,
            function.kind,
            signature,
            function.is_async,
            typed_dict_class_stubs,
        )

    @property
    def has_self(self) -> bool:
        return self.kind in self._KIND_WITH_SELF

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __repr__(self) -> str:
        return "FunctionDefinition('%s', '%s', %s, %s, %s, %s)" % (
            self.module,
            self.qualname,
            self.kind,
            self.signature,
            self.is_async,
            self.typed_dict_class_stubs,
        )


def get_updated_definition(
    func: Callable[..., Any],
    traces: Iterable[CallTrace],
    max_typed_dict_size: int,
    rewriter: Optional[TypeRewriter] = None,
    existing_annotation_strategy: ExistingAnnotationStrategy = ExistingAnnotationStrategy.REPLICATE,
) -> FunctionDefinition:
    """Update the definition for func using the types collected in traces."""
    if rewriter is None:
        rewriter = NoOpRewriter()
    arg_types, return_type, yield_type = shrink_traced_types(
        traces, max_typed_dict_size
    )
    arg_types = {name: rewriter.rewrite(typ) for name, typ in arg_types.items()}
    if return_type is not None:
        return_type = rewriter.rewrite(return_type)
    if yield_type is not None:
        yield_type = rewriter.rewrite(yield_type)
    return FunctionDefinition.from_callable_and_traced_types(
        func, arg_types, return_type, yield_type, existing_annotation_strategy
    )


def build_module_stubs(entries: Iterable[FunctionDefinition]) -> Dict[str, ModuleStub]:
    """Given an iterable of function definitions, build the corresponding stubs"""
    mod_stubs: Dict[str, ModuleStub] = {}
    for entry in entries:
        path = entry.qualname.split(".")
        name = path.pop()
        class_path = path
        # TODO: Handle nested classes
        klass = None
        if len(class_path) > 0:
            klass = ".".join(class_path)
        if entry.module not in mod_stubs:
            mod_stubs[entry.module] = ModuleStub()
        mod_stub = mod_stubs[entry.module]
        imports = get_imports_for_signature(entry.signature)
        # Import TypedDict, if needed.
        if entry.typed_dict_class_stubs:
            imports["mypy_extensions"].add("TypedDict")
        func_stub = FunctionStub(
            name, entry.signature, entry.kind, list(imports.keys()), entry.is_async
        )
        # Don't need to import anything from the same module
        imports.pop(entry.module, None)
        mod_stub.imports_stub.imports.merge(imports)
        if klass is not None:
            if klass not in mod_stub.class_stubs:
                mod_stub.class_stubs[klass] = ClassStub(klass)
            class_stub = mod_stub.class_stubs[klass]
            class_stub.function_stubs[func_stub.name] = func_stub
        else:
            mod_stub.function_stubs[func_stub.name] = func_stub

        mod_stub.typed_dict_class_stubs.extend(entry.typed_dict_class_stubs)

    return mod_stubs


def build_module_stubs_from_traces(
    traces: Iterable[CallTrace],
    max_typed_dict_size: int,
    existing_annotation_strategy: ExistingAnnotationStrategy = ExistingAnnotationStrategy.REPLICATE,
    rewriter: Optional[TypeRewriter] = None,
) -> Dict[str, ModuleStub]:
    """Given an iterable of call traces, build the corresponding stubs."""
    index: DefaultDict[Callable[..., Any], Set[CallTrace]] = collections.defaultdict(
        set
    )
    for trace in traces:
        index[trace.func].add(trace)
    defns = []
    for func, traces in index.items():
        defn = get_updated_definition(
            func, traces, max_typed_dict_size, rewriter, existing_annotation_strategy
        )
        defns.append(defn)
    return build_module_stubs(defns)


class StubIndexBuilder(CallTraceLogger):
    """Builds type stub index directly from collected call traces."""

    def __init__(self, module_re: str, max_typed_dict_size: int) -> None:
        self.re = re.compile(module_re)
        self.index: DefaultDict[Callable[..., Any], Set[CallTrace]] = (
            collections.defaultdict(set)
        )
        self.max_typed_dict_size = max_typed_dict_size

    def log(self, trace: CallTrace) -> None:
        if not self.re.match(trace.funcname):
            return
        self.index[trace.func].add(trace)

    def get_stubs(self) -> Dict[str, ModuleStub]:
        defs = (
            get_updated_definition(func, traces, self.max_typed_dict_size)
            for func, traces in self.index.items()
        )
        return build_module_stubs(defs)
