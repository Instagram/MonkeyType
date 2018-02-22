import inspect
from inspect import (
    Parameter,
    Signature,
)
from textwrap import dedent
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    NewType,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

import pytest

from monkeytype.stubs import (
    ClassStub,
    FunctionDefinition,
    FunctionStub,
    FunctionKind,
    ImportBlockStub,
    ImportMap,
    ModuleStub,
    StubIndexBuilder,
    build_module_stubs,
    build_module_stubs_from_traces,
    get_imports_for_annotation,
    has_unparsable_defaults,
    render_signature,
    shrink_traced_types,
    update_signature_args,
    update_signature_return,
)
from monkeytype.tracing import CallTrace
from monkeytype.typing import NoneType
from .util import Dummy

UserId = NewType('UserId', int)


class TestImportMap:
    def test_merge(self):
        a = ImportMap()
        a['module.a'] = {'ClassA', 'ClassB'}
        a['module.b'] = {'ClassE', 'ClassF'}
        b = ImportMap()
        b['module.a'] = {'ClassB', 'ClassC'}
        b['module.c'] = {'ClassX', 'ClassY'}
        expected = ImportMap()
        for mod in ('module.a', 'module.b', 'module.c'):
            expected[mod] = a[mod] | b[mod]
        a.merge(b)
        assert a == expected


class TestImportBlockStub:
    def test_single_import(self):
        """Single imports should be on one line"""
        imports = ImportMap()
        imports['a.module'] = {'AClass'}
        imports['another.module'] = {'AnotherClass'}
        stub = ImportBlockStub(imports)
        expected = "\n".join([
            'from a.module import AClass',
            'from another.module import AnotherClass',
        ])
        assert stub.render() == expected

    def test_io_import_single(self):
        """Single _io imports should convert to io"""
        imports = ImportMap()
        imports['_io'] = {'BytesIO'}
        stub = ImportBlockStub(imports)
        expected = "\n".join([
            'from io import BytesIO',
        ])
        assert stub.render() == expected

    def test_multiple_imports(self):
        """Multiple imports from a single module should each be on their own line"""
        imports = ImportMap()
        imports['a.module'] = {'AClass', 'AnotherClass', 'AThirdClass'}
        stub = ImportBlockStub(imports)
        expected = "\n".join([
            'from a.module import (',
            '    AClass,',
            '    AThirdClass,',
            '    AnotherClass,',
            ')',
        ])
        assert stub.render() == expected

    def test_multiple_io_imports(self):
        """Multiple imports from single _io module should be convert to io import"""
        imports = ImportMap()
        imports['_io'] = {'BytesIO', 'FileIO'}
        stub = ImportBlockStub(imports)
        expected = "\n".join([
            'from io import (',
            '    BytesIO,',
            '    FileIO,',
            ')',
        ])
        assert stub.render() == expected


def simple_add(a: int, b: int) -> int:
    return a + b


def strip_modules_helper(d1: Dummy, d2: Dummy) -> None:
    pass


class HasInvalidRepr:
    def __init__(self, value: int) -> None:
        self.value = value

    def __repr__(self) -> str:
        return '<HasInvalidRepr: %s>' % (self.value,)


def has_parsable_defaults(x: int = 1234, gate: bool = True, opt: str = None, s: str = '123') -> None:
    pass


def has_unparsable_default(x: HasInvalidRepr = HasInvalidRepr(123)) -> None:
    pass


def has_optional_param(x: Optional[int] = None) -> None:
    pass


def has_optional_union_param(x: Optional[Union[int, float]]) -> None:
    pass


def has_optional_return() -> Optional[int]:
    return None


def default_none_parameter(x: int = None) -> None:
    pass


def has_length_exceeds_120_chars(
    very_long_name_parameter_1: float,
    very_long_name_parameter_2: float
) -> Optional[float]:
    return None


def has_newtype_param(user_id: UserId) -> None:
    pass


class TestHasUnparsableDefaults:
    @pytest.mark.parametrize(
        'func, expected',
        [
            # No defaults
            (simple_add, False),
            # All parsable
            (has_parsable_defaults, False),
            # Unparsable
            (has_unparsable_default, True),
        ],
    )
    def test_has_unparsable_defaults(self, func, expected):
        sig = inspect.signature(func)
        assert has_unparsable_defaults(sig) == expected


class TestFunctionStub:
    def test_classmethod(self):
        stub = FunctionStub('test', inspect.signature(Dummy.a_class_method), FunctionKind.CLASS)
        expected = "\n".join([
            '@classmethod',
            'def test%s: ...' % (render_signature(stub.signature),),
        ])
        assert stub.render() == expected

    def test_staticmethod(self):
        stub = FunctionStub('test', inspect.signature(Dummy.a_static_method), FunctionKind.STATIC)
        expected = "\n".join([
            '@staticmethod',
            'def test%s: ...' % (render_signature(stub.signature),),
        ])
        assert stub.render() == expected

    def test_property(self):
        stub = FunctionStub('test', inspect.signature(Dummy.a_property.fget), FunctionKind.PROPERTY)
        expected = "\n".join([
            '@property',
            'def test%s: ...' % (render_signature(stub.signature),),
        ])
        assert stub.render() == expected

    def test_cached_property(self):
        stub = FunctionStub('test',
                            inspect.signature(Dummy.a_cached_property.func), FunctionKind.DJANGO_CACHED_PROPERTY)
        expected = "\n".join([
            '@cached_property',
            'def test%s: ...' % (render_signature(stub.signature),),
        ])
        assert stub.render() == expected

    def test_simple(self):
        for kind in [FunctionKind.MODULE, FunctionKind.INSTANCE]:
            stub = FunctionStub('test', inspect.signature(simple_add), kind)
            expected = 'def test%s: ...' % (render_signature(stub.signature),)
            assert stub.render() == expected

    def test_with_prefix(self):
        stub = FunctionStub('test', inspect.signature(simple_add), FunctionKind.MODULE)
        expected = '  def test%s: ...' % (render_signature(stub.signature),)
        assert stub.render(prefix='  ') == expected

    def test_strip_modules(self):
        """We should strip modules from annotations in the signature"""
        to_strip = [Dummy.__module__]
        f = strip_modules_helper
        stub = FunctionStub(f.__name__, inspect.signature(f), FunctionKind.MODULE, to_strip)
        expected = 'def strip_modules_helper(d1: Dummy, d2: Dummy) -> None: ...'
        assert stub.render() == expected

    def test_async_function(self):
        stub = FunctionStub('test', inspect.signature(simple_add), FunctionKind.MODULE, is_async=True)
        expected = 'async def test%s: ...' % (render_signature(stub.signature),)
        assert stub.render() == expected

    def test_optional_parameter_annotation(self):
        """Optional should always be included in parameter annotations, even if the default value is None"""
        stub = FunctionStub('test', inspect.signature(has_optional_param), FunctionKind.MODULE)
        expected = 'def test(x: Optional[int] = None) -> None: ...'
        assert stub.render() == expected

    def test_optional_union_parameter_annotation(self):
        """Optional[Union[X, Y]] should always be rendered as such, not Union[X, Y, None]"""
        stub = FunctionStub('test', inspect.signature(has_optional_union_param), FunctionKind.MODULE)
        expected = 'def test(x: Optional[Union[int, float]]) -> None: ...'
        assert stub.render() == expected

    def test_optional_return_annotation(self):
        """Optional should always be included in return annotations"""
        stub = FunctionStub('test', inspect.signature(has_optional_return), FunctionKind.MODULE)
        expected = 'def test() -> Optional[int]: ...'
        assert stub.render() == expected

    def test_split_parameters_across_multiple_lines(self):
        """When single-line length exceeds 120 characters, parameters should be split into multiple lines."""
        stub = FunctionStub('has_length_exceeds_120_chars',
                            inspect.signature(has_length_exceeds_120_chars),
                            FunctionKind.MODULE)
        expected = dedent('''\
        def has_length_exceeds_120_chars(
            very_long_name_parameter_1: float,
            very_long_name_parameter_2: float
        ) -> Optional[float]: ...''')
        assert stub.render() == expected

        expected = '\n'.join([
            '    def has_length_exceeds_120_chars(',
            '        very_long_name_parameter_1: float,',
            '        very_long_name_parameter_2: float',
            '    ) -> Optional[float]: ...'])
        assert stub.render(prefix='    ') == expected

    def test_default_none_parameter_annotation(self):
        stub = FunctionStub('test', inspect.signature(default_none_parameter), FunctionKind.MODULE)
        expected = 'def test(x: Optional[int] = None) -> None: ...'
        assert stub.render() == expected

    def test_newtype_parameter_annotation(self):
        stub = FunctionStub('test', inspect.signature(has_newtype_param), FunctionKind.MODULE)
        expected = 'def test(user_id: UserId) -> None: ...'
        assert stub.render() == expected

    def test_nonetype_annotation(self):
        """NoneType should always be rendered as None"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(sig, {'a': Dict[str, NoneType]}, has_self=False,
                                    ignore_existing_annotations=True)
        stub = FunctionStub('test', sig, FunctionKind.MODULE)
        expected = 'def test(a: Dict[str, None], b) -> int: ...'
        assert stub.render() == expected


def _func_stub_from_callable(func: Callable, strip_modules: List[str] = None):
    kind = FunctionKind.from_callable(func)
    sig = Signature.from_callable(func)
    return FunctionStub(func.__name__, sig, kind, strip_modules)


class TestClassStub:
    def test_render(self):
        cm_stub = _func_stub_from_callable(Dummy.a_class_method.__func__)
        im_stub = _func_stub_from_callable(Dummy.an_instance_method)
        class_stub = ClassStub('Test', function_stubs=(cm_stub, im_stub))
        expected = "\n".join([
            'class Test:',
            cm_stub.render(prefix='    '),
            im_stub.render(prefix='    '),
        ])
        assert class_stub.render() == expected


class TestModuleStub:
    def test_render(self):
        cm_stub = _func_stub_from_callable(Dummy.a_class_method)
        im_stub = _func_stub_from_callable(Dummy.an_instance_method)
        func_stubs = (cm_stub, im_stub)
        test_stub = ClassStub('Test', function_stubs=func_stubs)
        test2_stub = ClassStub('Test2', function_stubs=func_stubs)
        class_stubs = (test_stub, test2_stub)
        mod_stub = ModuleStub(function_stubs=func_stubs, class_stubs=class_stubs)
        expected = "\n\n\n".join([
            cm_stub.render(),
            im_stub.render(),
            test_stub.render(),
            test2_stub.render(),
        ])
        assert mod_stub.render() == expected


class TestBuildModuleStubs:
    def test_build_module_stubs(self):
        entries = [
            FunctionDefinition.from_callable(Dummy.a_static_method),
            FunctionDefinition.from_callable(Dummy.a_class_method.__func__),
            FunctionDefinition.from_callable(Dummy.an_instance_method),
            FunctionDefinition.from_callable(simple_add),
        ]
        simple_add_stub = _func_stub_from_callable(simple_add)
        to_strip = ['typing']
        dummy_stub = ClassStub('Dummy', function_stubs=[
            _func_stub_from_callable(Dummy.a_class_method.__func__, to_strip),
            _func_stub_from_callable(Dummy.an_instance_method, to_strip),
            _func_stub_from_callable(Dummy.a_static_method, to_strip),
        ])
        imports = {'typing': {'Any', 'Optional'}}
        expected = {
            'tests.test_stubs': ModuleStub(function_stubs=[simple_add_stub]),
            'tests.util': ModuleStub(class_stubs=[dummy_stub], imports_stub=ImportBlockStub(imports)),
        }
        self.maxDiff = None
        assert build_module_stubs(entries) == expected


def untyped_helper(x, y):
    pass


class TestStubIndexBuilder:
    def test_ignore_non_matching_functions(self):
        b = StubIndexBuilder('foo.bar')
        b.log(CallTrace(untyped_helper, {'x': int, 'y': str}))
        assert len(b.index) == 0

    def test_build_index(self):
        idxb = StubIndexBuilder('tests')
        idxb.log(CallTrace(untyped_helper, {'x': int, 'y': str}, str))
        sig = Signature.from_callable(untyped_helper)
        sig = sig.replace(
            parameters=[
                Parameter('x', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                Parameter('y', Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
            ],
            return_annotation=str
        )
        mod_stub = ModuleStub(function_stubs=[FunctionStub('untyped_helper', sig, FunctionKind.MODULE)])
        expected = {'tests.test_stubs': mod_stub}
        assert idxb.get_stubs() == expected


# These functions are intentionally partially typed to ensure we do not modify pre-existing
# annotations as well as to ensure we update empty annotations.
class UpdateSignatureHelper:
    @staticmethod
    def has_annos(a: int, b) -> int:
        return 0

    @classmethod
    def a_class_method(cls):
        pass

    def an_instance_method(self):
        pass


class TestUpdateSignatureArgs:
    def test_update_arg(self):
        """Update arg annotations from types"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(sig, {'b': int}, False)
        params = [
            Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
            Parameter('b', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
        ]
        assert sig == Signature(parameters=params, return_annotation=int)

    def test_update_arg_with_anno(self):
        """Leave existing arg annotations alone"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(sig, {'a': str}, False)
        expected = Signature(
            parameters=[
                Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                Parameter('b', Parameter.POSITIONAL_OR_KEYWORD)
            ],
            return_annotation=int
        )
        assert sig == expected

    def test_update_self(self):
        """Don't annotate first arg of instance methods"""
        sig = Signature.from_callable(UpdateSignatureHelper.an_instance_method)
        sig = update_signature_args(sig, {'self': UpdateSignatureHelper}, True)
        expected = Signature(parameters=[Parameter('self', Parameter.POSITIONAL_OR_KEYWORD)])
        assert sig == expected

    def test_update_class(self):
        """Don't annotate the first arg of classmethods"""
        sig = Signature.from_callable(UpdateSignatureHelper.a_class_method.__func__)
        sig = update_signature_args(sig, {'cls': Type[UpdateSignatureHelper]}, True)
        expected = Signature(parameters=[Parameter('cls', Parameter.POSITIONAL_OR_KEYWORD)])
        assert sig == expected

    def test_update_arg_ignore_existing_anno(self):
        """Update stubs only bases on traces."""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(sig, {'a': str, 'b': bool}, has_self=False, ignore_existing_annotations=True)
        params = [
            Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
            Parameter('b', Parameter.POSITIONAL_OR_KEYWORD, annotation=bool),
        ]
        assert sig == Signature(parameters=params, return_annotation=int)

    def test_update_self_ignore_existing_anno(self):
        """Don't annotate first arg of instance methods with ignore_existing_annotations"""
        sig = Signature.from_callable(UpdateSignatureHelper.an_instance_method)
        sig = update_signature_args(sig, {'self': UpdateSignatureHelper}, has_self=True,
                                    ignore_existing_annotations=True)
        expected = Signature(parameters=[Parameter('self', Parameter.POSITIONAL_OR_KEYWORD)])
        assert sig == expected

    def test_update_arg_ignore_existing_anno_None(self):
        """Update arg annotations from types"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(sig, {'a': None, 'b': int}, has_self=False, ignore_existing_annotations=True)
        params = [
            Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=inspect.Parameter.empty),
            Parameter('b', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
        ]
        assert sig == Signature(parameters=params, return_annotation=int)


class TestUpdateSignatureReturn:
    def test_update_return(self):
        """Update return annotations from types"""
        sig = Signature.from_callable(UpdateSignatureHelper.a_class_method)
        sig = update_signature_return(sig, return_type=str)
        assert sig == Signature(return_annotation=str)

    def test_update_return_with_anno(self):
        """Leave existing return annotations alone"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_return(sig, return_type=str)
        expected = Signature(
            parameters=[
                Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                Parameter('b', Parameter.POSITIONAL_OR_KEYWORD)
            ],
            return_annotation=int
        )
        assert sig == expected

    def test_update_return_with_anno_ignored(self):
        """Leave existing return annotations alone"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_return(sig, return_type=str, ignore_existing_annotations=True)
        expected = Signature(
            parameters=[
                Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                Parameter('b', Parameter.POSITIONAL_OR_KEYWORD)
            ],
            return_annotation=str
        )
        assert sig == expected

    def test_update_yield(self):
        sig = Signature.from_callable(UpdateSignatureHelper.a_class_method)
        sig = update_signature_return(sig, yield_type=int)
        assert sig == Signature(return_annotation=Iterator[int])
        sig = update_signature_return(sig, return_type=NoneType, yield_type=int)
        assert sig == Signature(return_annotation=Iterator[int])

    def test_update_yield_and_return(self):
        sig = Signature.from_callable(UpdateSignatureHelper.a_class_method)
        sig = update_signature_return(sig, return_type=str, yield_type=int)
        assert sig == Signature(return_annotation=Generator[int, NoneType, str])

    def test_update_yield_none_and_return(self):
        sig = Signature.from_callable(UpdateSignatureHelper.a_class_method)
        sig = update_signature_return(sig, return_type=str, yield_type=NoneType)
        assert sig == Signature(return_annotation=Generator[NoneType, NoneType, str])

    def test_update_yield_and_return_none(self):
        sig = Signature.from_callable(UpdateSignatureHelper.a_class_method)
        sig = update_signature_return(sig, return_type=NoneType, yield_type=str)
        assert sig == Signature(return_annotation=Iterator[str])


def a_module_func() -> None:
    pass


async def an_async_func() -> None:
    pass


class TestFunctionKind:
    @pytest.mark.parametrize(
        'func, expected',
        [
            (Dummy.a_static_method, FunctionKind.STATIC),
            (Dummy.a_class_method.__func__, FunctionKind.CLASS),
            (Dummy.an_instance_method, FunctionKind.INSTANCE),
            (Dummy.a_property.fget, FunctionKind.PROPERTY),
            (Dummy.a_cached_property.func, FunctionKind.DJANGO_CACHED_PROPERTY),
            (a_module_func, FunctionKind.MODULE),
        ],
    )
    def test_from_callable(self, func, expected):
        assert FunctionKind.from_callable(func) == expected


class TestFunctionDefinition:
    @pytest.mark.parametrize(
        'func, expected',
        [
            (Dummy.a_static_method, False),
            (Dummy.a_class_method.__func__, True),
            (Dummy.an_instance_method, True),
            (Dummy.a_property.fget, True),
            (Dummy.a_cached_property.func, True),
            (a_module_func, False),
        ],
    )
    def test_has_self(self, func, expected):
        defn = FunctionDefinition.from_callable(func)
        assert defn.has_self == expected

    @pytest.mark.parametrize(
        'func, expected',
        [
            (Dummy.a_static_method, FunctionDefinition(
                'tests.util', 'Dummy.a_static_method', FunctionKind.STATIC,
                Signature.from_callable(Dummy.a_static_method))),
            (Dummy.a_class_method.__func__, FunctionDefinition(
                'tests.util', 'Dummy.a_class_method', FunctionKind.CLASS,
                Signature.from_callable(Dummy.a_class_method.__func__))),
            (Dummy.an_instance_method, FunctionDefinition(
                'tests.util', 'Dummy.an_instance_method', FunctionKind.INSTANCE,
                Signature.from_callable(Dummy.an_instance_method))),
            (Dummy.a_property.fget, FunctionDefinition(
                'tests.util', 'Dummy.a_property', FunctionKind.PROPERTY,
                Signature.from_callable(Dummy.a_property.fget))),
            (Dummy.a_cached_property.func, FunctionDefinition(
                'tests.util', 'Dummy.a_cached_property', FunctionKind.DJANGO_CACHED_PROPERTY,
                Signature.from_callable(Dummy.a_cached_property.func))),
            (a_module_func, FunctionDefinition(
                'tests.test_stubs', 'a_module_func', FunctionKind.MODULE,
                Signature.from_callable(a_module_func))),
            (an_async_func, FunctionDefinition(
                'tests.test_stubs', 'an_async_func', FunctionKind.MODULE,
                Signature.from_callable(a_module_func), is_async=True)),
        ],
    )
    def test_from_callable(self, func, expected):
        defn = FunctionDefinition.from_callable(func)
        assert defn == expected


def tie_helper(a, b):
    pass


class TestShrinkTracedTypes:
    def test_shrink_args(self):
        traces = [
            CallTrace(tie_helper, {'a': str, 'b': int}),
            CallTrace(tie_helper, {'a': str, 'b': NoneType}),
        ]
        assert shrink_traced_types(traces) == ({'a': str, 'b': Optional[int]}, None, None)

    def test_shrink_return(self):
        traces = [
            CallTrace(tie_helper, {}, NoneType),
            CallTrace(tie_helper, {}, str),
        ]
        assert shrink_traced_types(traces) == ({}, Optional[str], None)

    def test_shrink_yield(self):
        traces = [
            CallTrace(tie_helper, {}, yield_type=int),
            CallTrace(tie_helper, {}, yield_type=str),
        ]
        assert shrink_traced_types(traces) == ({}, None, Union[int, str])


class Parent:
    class Child:
        pass


class TestGetImportsForAnnotation:
    @pytest.mark.parametrize(
        'anno',
        [
            inspect.Parameter.empty,
            inspect.Signature.empty,
            'not a type',
            int,
        ],
    )
    def test_no_imports(self, anno):
        """We shouldn't import any builtins, non-types, or empty annos"""
        assert get_imports_for_annotation(anno) == {}

    @pytest.mark.parametrize(
        'anno, expected',
        [
            (Any, {'typing': {'Any'}}),
            (Union[int, str], {'typing': {'Union'}}),
        ],
    )
    def test_special_case_types(self, anno, expected):
        """Any and Union do not have module/qualname and need to be treated specially"""
        assert get_imports_for_annotation(anno) == expected

    def test_user_defined_class(self):
        assert get_imports_for_annotation(Dummy) == {'tests.util': {'Dummy'}}

    @pytest.mark.parametrize(
        'anno, expected',
        [
            (Dict[str, Dummy], {'tests.util': {'Dummy'}, 'typing': {'Dict'}}),
            (List[Dummy], {'tests.util': {'Dummy'}, 'typing': {'List'}}),
            (Set[Dummy], {'tests.util': {'Dummy'}, 'typing': {'Set'}}),
            (Tuple[str, Dummy], {'tests.util': {'Dummy'}, 'typing': {'Tuple'}}),
            (Type[Dummy], {'tests.util': {'Dummy'}, 'typing': {'Type'}}),
            (Union[str, Dummy], {'tests.util': {'Dummy'}, 'typing': {'Union'}}),
        ],
    )
    def test_container_types(self, anno, expected):
        """We need to descend into container types"""
        assert get_imports_for_annotation(anno) == expected

    def test_nested_class(self):
        assert get_imports_for_annotation(Parent.Child) == {Parent.__module__: {'Parent'}}


class TestBuildModuleStubsFromTraces:
    def test_remove_funcs_with_unparsable_defaults(self):
        """We should remove stubs for functions with default values whose reprs are unparsable.

        During application, retype needs to parse the stubs that we give it. We
        use repr() to produce what is used for the default value.
        """
        trace = CallTrace(has_unparsable_default, {})
        stubs = build_module_stubs_from_traces([trace])
        assert stubs == {}
