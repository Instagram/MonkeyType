# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
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
    Iterable,
    Iterator,
    List,
    NewType,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from unittest import skipIf

import pytest

from monkeytype.compat import cached_property, make_forward_ref
from monkeytype.stubs import (
    AttributeStub,
    ClassStub,
    ExistingAnnotationStrategy,
    FunctionDefinition,
    FunctionStub,
    FunctionKind,
    ImportBlockStub,
    ImportMap,
    ModuleStub,
    ReplaceTypedDictsWithStubs,
    StubIndexBuilder,
    build_module_stubs,
    get_imports_for_annotation,
    get_imports_for_signature,
    render_annotation,
    render_signature,
    shrink_traced_types,
    update_signature_args,
    update_signature_return,
)
from monkeytype.tracing import CallTrace
from monkeytype.typing import NoneType, make_typed_dict
from mypy_extensions import TypedDict
from .util import Dummy

UserId = NewType('UserId', int)
T = TypeVar("T")


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


def has_forward_ref() -> Optional["TestFunctionStub"]:
    pass


def has_forward_ref_within_generator() -> Generator['TestFunctionStub', None, int]:
    pass


class TestAttributeStub:
    @pytest.mark.parametrize(
        'stub, expected',
        [
            (AttributeStub(name='foo', typ=int), '    foo: int'),
            (AttributeStub(name='foo', typ=make_forward_ref('Foo')), '    foo: \'Foo\''),
        ],
    )
    def test_simple_attribute(self, stub, expected):
        assert stub.render('    ') == expected


class TestRenderAnnotation:
    @pytest.mark.parametrize(
        'annotation, expected',
        [
            (make_forward_ref('Foo'), '\'Foo\''),
            (List[make_forward_ref('Foo')], 'List[\'Foo\']'),
            (List[List[make_forward_ref('Foo')]], 'List[List[\'Foo\']]'),
            (Optional[int], 'Optional[int]'),
            (List[Optional[int]], 'List[Optional[int]]'),
            (UserId, 'UserId'),
            (List[UserId], 'List[UserId]'),
            (List[int], 'List[int]'),
            (List[List[int]], 'List[List[int]]'),
            (None, 'None'),
            (List[None], 'List[None]'),
            (int, 'int'),
            (Dummy, 'tests.util.Dummy'),
            (List[Dummy], 'List[tests.util.Dummy]'),
            ('some_string', 'some_string'),
            (Iterable[None], 'Iterable[None]'),
            (List[Iterable[None]], 'List[Iterable[None]]'),
            (Generator[make_forward_ref('Foo'), None, None], 'Generator[\'Foo\', None, None]'),
            (List[Generator[make_forward_ref('Foo'), None, None]], 'List[Generator[\'Foo\', None, None]]'),
            (T, 'T'),
            (Dict[str, T], 'Dict[str, T]'),
            (Tuple[()], 'Tuple[()]'),
        ],
    )
    def test_render_annotation(self, annotation, expected):
        assert render_annotation(annotation) == expected


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

    @skipIf(cached_property is None, "install Django to run this test")
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
        expected = 'def test(x: Optional[int] = ...) -> None: ...'
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
        expected = 'def test(x: Optional[int] = ...) -> None: ...'
        assert stub.render() == expected

    def test_newtype_parameter_annotation(self):
        stub = FunctionStub('test', inspect.signature(has_newtype_param), FunctionKind.MODULE)
        expected = 'def test(user_id: UserId) -> None: ...'
        assert stub.render() == expected

    def test_nonetype_annotation(self):
        """NoneType should always be rendered as None"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(sig, {'a': Dict[str, NoneType]}, has_self=False,
                                    existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE)
        stub = FunctionStub('test', sig, FunctionKind.MODULE)
        expected = 'def test(a: Dict[str, None], b) -> int: ...'
        assert stub.render() == expected

    def test_forward_ref_annotation(self):
        """Forward refs should be rendered as strings, not _ForwardRef(...)."""
        stub = FunctionStub('has_forward_ref', inspect.signature(has_forward_ref), FunctionKind.MODULE)
        expected = "def has_forward_ref() -> Optional['TestFunctionStub']: ..."
        assert stub.render() == expected

    @pytest.mark.xfail(reason='We get Generator[ForwardRef(), ...].')
    def test_forward_ref_annotation_within_generator(self):
        stub = FunctionStub('foo',
                            inspect.signature(has_forward_ref_within_generator),
                            FunctionKind.MODULE)
        expected = "def foo() -> Generator['TestFunctionStub', None, int]: ..."
        assert stub.render() == expected


def _func_stub_from_callable(func: Callable, strip_modules: List[str] = None):
    kind = FunctionKind.from_callable(func)
    sig = Signature.from_callable(func)
    return FunctionStub(func.__name__, sig, kind, strip_modules)


class TestClassStub:
    def test_render(self):
        cm_stub = _func_stub_from_callable(Dummy.a_class_method.__func__)
        im_stub = _func_stub_from_callable(Dummy.an_instance_method)
        class_stub = ClassStub('Test', function_stubs=(cm_stub, im_stub),
                               attribute_stubs=[
                                   AttributeStub('foo', int),
                                   AttributeStub('bar', str),
                                ])
        expected = '\n'.join([
            'class Test:',
            '    bar: str',
            '    foo: int',
            '    @classmethod',
            '    def a_class_method(cls, foo: Any) -> Optional[frame]: ...',
            '    def an_instance_method(self, foo: Any, bar: Any) -> Optional[frame]: ...',
        ])
        assert class_stub.render() == expected


class TestReplaceTypedDictsWithStubs:
    SIMPLE_TYPED_DICT_STUB: ClassStub = ClassStub(
        name='FooBarTypedDict__RENAME_ME__(TypedDict)',
        function_stubs=[],
        attribute_stubs=[
            AttributeStub(name='a', typ=int),
            AttributeStub(name='b', typ=str),
        ])
    SIMPLE_TYPED_DICT_STUB2: ClassStub = ClassStub(
        name='FooBar2TypedDict__RENAME_ME__(TypedDict)',
        function_stubs=[],
        attribute_stubs=[
            AttributeStub(name='a', typ=int),
            AttributeStub(name='b', typ=str),
        ])
    SIMPLE_NON_TOTAL_TYPED_DICT_STUB: ClassStub = ClassStub(
        name='FooBarTypedDict__RENAME_ME__(TypedDict, total=False)',
        function_stubs=[],
        attribute_stubs=[
            AttributeStub(name='a', typ=int),
            AttributeStub(name='b', typ=str),
        ])
    SIMPLE_BASE_AND_SUBCLASS: List[ClassStub] = [
        ClassStub(
            name='FooBarTypedDict__RENAME_ME__(TypedDict)',
            function_stubs=[],
            attribute_stubs=[
                AttributeStub(name='a', typ=int),
                AttributeStub(name='b', typ=str),
            ]),
        ClassStub(
            name='FooBarTypedDict__RENAME_ME__NonTotal(FooBarTypedDict__RENAME_ME__, total=False)',
            function_stubs=[],
            attribute_stubs=[
                AttributeStub(name='c', typ=int),
            ]),
    ]

    @pytest.mark.parametrize(
        'typ, expected',
        [
            (int, (int, [])),
            (List[int], (List[int], [])),
            (Set[int], (Set[int], [])),
            (Dict[str, int], (Dict[str, int], [])),
            (Tuple[str, int], (Tuple[str, int], [])),
            (List[List[Dict[str, int]]], (List[List[Dict[str, int]]], []),),
            (List[List[Dict[str, int]]], (List[List[Dict[str, int]]], []),),
            (
                List[List[make_typed_dict(required_fields={'a': int, 'b': str})]],
                (List[List[make_forward_ref('FooBarTypedDict__RENAME_ME__')]], [SIMPLE_TYPED_DICT_STUB]),
            ),
            (
                Dict[str, make_typed_dict(required_fields={'a': int, 'b': str})],
                (Dict[str, make_forward_ref('FooBar2TypedDict__RENAME_ME__')], [SIMPLE_TYPED_DICT_STUB2]),
            ),
            (
                Set[make_typed_dict(required_fields={'a': int, 'b': str})],
                (Set[make_forward_ref('FooBarTypedDict__RENAME_ME__')], [SIMPLE_TYPED_DICT_STUB]),
            ),
            (
                Tuple[int, make_typed_dict(required_fields={'a': int, 'b': str})],
                (Tuple[int, make_forward_ref('FooBar2TypedDict__RENAME_ME__')], [SIMPLE_TYPED_DICT_STUB2]),
            ),
            (
                make_typed_dict(required_fields={'a': int, 'b': str}),
                (make_forward_ref('FooBarTypedDict__RENAME_ME__'), [SIMPLE_TYPED_DICT_STUB]),
            ),
            (
                make_typed_dict(optional_fields={'a': int, 'b': str}),
                (make_forward_ref('FooBarTypedDict__RENAME_ME__'), [SIMPLE_NON_TOTAL_TYPED_DICT_STUB]),
            ),
            (
                make_typed_dict(required_fields={'a': int, 'b': str}, optional_fields={'c': int}),
                (make_forward_ref('FooBarTypedDict__RENAME_ME__NonTotal'), SIMPLE_BASE_AND_SUBCLASS),
            ),
            (
                TypedDict('GenuineTypedDict', {'a': int, 'b': str}),
                (TypedDict('GenuineTypedDict', {'a': int, 'b': str}), []),
            ),
            (
                make_typed_dict(required_fields={
                    'a': int,
                    'b': make_typed_dict(required_fields={
                        'a': int,
                        'b': str
                    })
                }),
                (make_forward_ref('FooBarTypedDict__RENAME_ME__'), [
                    ClassStub(
                        name='BTypedDict__RENAME_ME__(TypedDict)',
                        function_stubs=[],
                        attribute_stubs=[
                            AttributeStub(name='a', typ=int),
                            AttributeStub(name='b', typ=str),
                        ]),
                    ClassStub(
                        name='FooBarTypedDict__RENAME_ME__(TypedDict)',
                        function_stubs=[],
                        attribute_stubs=[
                            AttributeStub(name='a', typ=int),
                            AttributeStub(name='b', typ=make_forward_ref('BTypedDict__RENAME_ME__')),
                        ])
                ]),
            ),
            (
                Tuple[make_typed_dict(required_fields={'a': int}),
                      make_typed_dict(required_fields={'b': str})],
                (Tuple[make_forward_ref('FooBarTypedDict__RENAME_ME__'),
                       make_forward_ref('FooBar2TypedDict__RENAME_ME__')],
                 [ClassStub(
                     name='FooBarTypedDict__RENAME_ME__(TypedDict)',
                     function_stubs=[],
                     attribute_stubs=[
                         AttributeStub(name='a', typ=int),
                     ]),
                  ClassStub(
                      name='FooBar2TypedDict__RENAME_ME__(TypedDict)',
                      function_stubs=[],
                      attribute_stubs=[
                          AttributeStub(name='b', typ=str),
                      ])]),
            ),
        ],
    )
    def test_replace_typed_dict_with_stubs(self, typ, expected):
        rewritten_type, stubs = ReplaceTypedDictsWithStubs.rewrite_and_get_stubs(typ, class_name_hint='foo_bar')
        actual = rewritten_type, stubs
        assert actual == expected


typed_dict_import_map = ImportMap()
typed_dict_import_map['mypy_extensions'] = {'TypedDict'}
module_stub_for_method_with_typed_dict = {
    'tests.util': ModuleStub(
        function_stubs=(),
        class_stubs=[
            ClassStub(
                name='Dummy',
                function_stubs=[
                    FunctionStub(
                        name='an_instance_method',
                        signature=Signature(
                            parameters=[
                                Parameter(name='self',
                                          kind=Parameter.POSITIONAL_OR_KEYWORD,
                                          annotation=Parameter.empty),
                                Parameter(name='foo',
                                          kind=Parameter.POSITIONAL_OR_KEYWORD,
                                          annotation=make_forward_ref('FooTypedDict__RENAME_ME__')),
                                Parameter(name='bar',
                                          kind=Parameter.POSITIONAL_OR_KEYWORD,
                                          annotation=int),
                            ],
                            return_annotation=make_forward_ref('DummyAnInstanceMethodTypedDict__RENAME_ME__'),
                        ),
                        kind=FunctionKind.INSTANCE,
                        strip_modules=['mypy_extensions'],
                        is_async=False,
                    ),
                ],
            ),
        ],
        imports_stub=ImportBlockStub(typed_dict_import_map),
        typed_dict_class_stubs=[
            ClassStub(
                name='FooTypedDict__RENAME_ME__(TypedDict)',
                function_stubs=[],
                attribute_stubs=[
                    AttributeStub('a', int),
                    AttributeStub('b', str),
                ]
            ),
            ClassStub(
                # We use the name of the method, `Dummy.an_instance_method`,
                # to get `DummyAnInstanceMethodTypedDict__RENAME_ME__`.
                name='DummyAnInstanceMethodTypedDict__RENAME_ME__(TypedDict)',
                function_stubs=[],
                attribute_stubs=[
                    AttributeStub('c', int),
                ]
            ),
        ],
    )
}


class TestModuleStub:
    def test_render(self):
        cm_stub = _func_stub_from_callable(Dummy.a_class_method)
        im_stub = _func_stub_from_callable(Dummy.an_instance_method)
        sig_stub = _func_stub_from_callable(Dummy.has_complex_signature)
        func_stubs = (cm_stub, im_stub, sig_stub)
        test_stub = ClassStub('Test', function_stubs=func_stubs)
        test2_stub = ClassStub('Test2', function_stubs=func_stubs)
        other_class_stubs = module_stub_for_method_with_typed_dict['tests.util'].class_stubs.values()
        class_stubs = (*other_class_stubs, test_stub, test2_stub)
        typed_dict_class_stubs = module_stub_for_method_with_typed_dict['tests.util'].typed_dict_class_stubs
        mod_stub = ModuleStub(function_stubs=func_stubs,
                              class_stubs=class_stubs,
                              typed_dict_class_stubs=typed_dict_class_stubs)
        expected = '\n'.join([
            'class DummyAnInstanceMethodTypedDict__RENAME_ME__(TypedDict):',
            '    c: int',
            '',
            '',
            'class FooTypedDict__RENAME_ME__(TypedDict):',
            '    a: int',
            '    b: str',
            '',
            '',
            '@classmethod',
            'def a_class_method(foo: Any) -> Optional[frame]: ...',
            '',
            '',
            'def an_instance_method(self, foo: Any, bar: Any) -> Optional[frame]: ...',
            '',
            '',
            'def has_complex_signature(',
            '    self,',
            '    a: Any,',
            '    b: Any,',
            '    /,',
            '    c: Any,',
            '    d: Any = ...,',
            '    *e: Any,',
            '    f: Any,',
            '    g: Any = ...,',
            '    **h: Any',
            ') -> Optional[frame]: ...',
            '',
            '',
            'class Dummy:',
            '    def an_instance_method(',
            '        self,',
            '        foo: \'FooTypedDict__RENAME_ME__\',',
            '        bar: int',
            '    ) -> \'DummyAnInstanceMethodTypedDict__RENAME_ME__\': ...',
            '',
            '',
            'class Test:',
            '    @classmethod',
            '    def a_class_method(foo: Any) -> Optional[frame]: ...',
            '    def an_instance_method(self, foo: Any, bar: Any) -> Optional[frame]: ...',
            '    def has_complex_signature(',
            '        self,',
            '        a: Any,',
            '        b: Any,',
            '        /,',
            '        c: Any,',
            '        d: Any = ...,',
            '        *e: Any,',
            '        f: Any,',
            '        g: Any = ...,',
            '        **h: Any',
            '    ) -> Optional[frame]: ...',
            '',
            '',
            'class Test2:',
            '    @classmethod',
            '    def a_class_method(foo: Any) -> Optional[frame]: ...',
            '    def an_instance_method(self, foo: Any, bar: Any) -> Optional[frame]: ...',
            '    def has_complex_signature(',
            '        self,',
            '        a: Any,',
            '        b: Any,',
            '        /,',
            '        c: Any,',
            '        d: Any = ...,',
            '        *e: Any,',
            '        f: Any,',
            '        g: Any = ...,',
            '        **h: Any',
            '    ) -> Optional[frame]: ...',
        ])
        assert mod_stub.render() == expected

    def test_render_nested_typed_dict(self):
        function = FunctionDefinition.from_callable_and_traced_types(
            Dummy.an_instance_method,
            {
                'foo': make_typed_dict(required_fields={
                    # Naming the key 'z' to test a class name
                    # that comes last in alphabetical order.
                    'z': make_typed_dict(required_fields={'a': int, 'b': str}),
                    'b': str,
                }),
                'bar': int,
            },
            int,
            None,
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE
        )
        entries = [function]
        expected = '\n'.join([
            'from mypy_extensions import TypedDict',
            '',
            '',
            'class FooTypedDict__RENAME_ME__(TypedDict):',
            '    b: str',
            # We can forward-reference a class that is defined afterwards.
            '    z: \'ZTypedDict__RENAME_ME__\'',
            '',
            '',
            'class ZTypedDict__RENAME_ME__(TypedDict):',
            '    a: int',
            '    b: str',
            '',
            '',
            'class Dummy:',
            '    def an_instance_method(self, foo: \'FooTypedDict__RENAME_ME__\', bar: int) -> int: ...'])
        self.maxDiff = None
        assert build_module_stubs(entries)['tests.util'].render() == expected

    def test_render_return_typed_dict(self):
        function = FunctionDefinition.from_callable_and_traced_types(
            Dummy.an_instance_method,
            {
                'foo': int,
                'bar': int,
            },
            make_typed_dict(required_fields={'a': int, 'b': str}),
            yield_type=None,
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE
        )
        entries = [function]
        expected = '\n'.join([
            'from mypy_extensions import TypedDict',
            '',
            '',
            'class DummyAnInstanceMethodTypedDict__RENAME_ME__(TypedDict):',
            '    a: int',
            '    b: str',
            '',
            '',
            'class Dummy:',
            '    def an_instance_method(self, foo: int, bar: int)'
            ' -> \'DummyAnInstanceMethodTypedDict__RENAME_ME__\': ...',
        ])
        self.maxDiff = None
        assert build_module_stubs(entries)['tests.util'].render() == expected

    def test_render_yield_typed_dict(self):
        function = FunctionDefinition.from_callable_and_traced_types(
            Dummy.an_instance_method,
            {
                'foo': int,
                'bar': int,
            },
            int,
            yield_type=make_typed_dict(required_fields={'a': int, 'b': str}),
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE
        )
        entries = [function]
        expected = '\n'.join([
            'from mypy_extensions import TypedDict',
            'from typing import Generator',
            '',
            '',
            'class DummyAnInstanceMethodYieldTypedDict__RENAME_ME__(TypedDict):',
            '    a: int',
            '    b: str',
            '',
            '',
            'class Dummy:',
            '    def an_instance_method(',
            '        self,',
            '        foo: int,',
            '        bar: int',
            '    ) -> Generator[\'DummyAnInstanceMethodYieldTypedDict__RENAME_ME__\', None, int]: ...',
        ])
        self.maxDiff = None
        assert build_module_stubs(entries)['tests.util'].render() == expected

    def test_render_typed_dict_in_list(self):
        function = FunctionDefinition.from_callable_and_traced_types(
            Dummy.an_instance_method,
            {
                'foo': List[make_typed_dict(required_fields={'a': int})],
                'bar': int,
            },
            int,
            None,
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE,
        )
        entries = [function]
        expected = '\n'.join([
            'from mypy_extensions import TypedDict',
            'from typing import List',
            '',
            '',
            'class FooTypedDict__RENAME_ME__(TypedDict):',
            '    a: int',
            '',
            '',
            'class Dummy:',
            '    def an_instance_method(self, foo: List[\'FooTypedDict__RENAME_ME__\'], bar: int) -> int: ...'])
        self.maxDiff = None
        assert build_module_stubs(entries)['tests.util'].render() == expected

    def test_render_typed_dict_base_and_subclass(self):
        function = FunctionDefinition.from_callable_and_traced_types(
            Dummy.an_instance_method,
            {
                'foo': make_typed_dict(required_fields={'a': int}, optional_fields={'b': str}),
                'bar': int,
            },
            int,
            None,
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE,
        )
        entries = [function]
        expected = '\n'.join([
            'from mypy_extensions import TypedDict',
            '',
            '',
            'class FooTypedDict__RENAME_ME__(TypedDict):',
            '    a: int',
            '',
            '',
            'class FooTypedDict__RENAME_ME__NonTotal(FooTypedDict__RENAME_ME__, total=False):',
            '    b: str',
            '',
            '',
            'class Dummy:',
            '    def an_instance_method(self, foo: \'FooTypedDict__RENAME_ME__NonTotal\', bar: int) -> int: ...'])
        assert build_module_stubs(entries)['tests.util'].render() == expected

    def test_render_return_empty_tuple(self):
        """Regression test for #190."""
        function = FunctionDefinition.from_callable_and_traced_types(
            Dummy.an_instance_method,
            {
                'foo': int,
                'bar': int,
            },
            Tuple[()],
            yield_type=None,
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE
        )
        entries = [function]
        expected = '\n'.join([
            'from typing import Tuple',
            '',
            '',
            'class Dummy:',
            '    def an_instance_method(self, foo: int, bar: int)'
            ' -> Tuple[()]: ...',
        ])
        self.maxDiff = None
        assert build_module_stubs(entries)['tests.util'].render() == expected


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

    def test_build_module_stubs_typed_dict_parameter(self):
        function = FunctionDefinition.from_callable_and_traced_types(
            Dummy.an_instance_method,
            {
                'foo': make_typed_dict(required_fields={'a': int, 'b': str}),
                'bar': int,
            },
            make_typed_dict(required_fields={'c': int}),
            None,
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE
        )
        entries = [function]
        expected = module_stub_for_method_with_typed_dict
        self.maxDiff = None
        assert build_module_stubs(entries) == expected


def untyped_helper(x, y):
    pass


class TestStubIndexBuilder:
    def test_ignore_non_matching_functions(self):
        b = StubIndexBuilder('foo.bar', max_typed_dict_size=0)
        b.log(CallTrace(untyped_helper, {'x': int, 'y': str}))
        assert len(b.index) == 0

    def test_build_index(self):
        idxb = StubIndexBuilder('tests', max_typed_dict_size=0)
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
        sig = update_signature_args(
            sig, {'a': str, 'b': bool}, has_self=False, existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE)
        params = [
            Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
            Parameter('b', Parameter.POSITIONAL_OR_KEYWORD, annotation=bool),
        ]
        assert sig == Signature(parameters=params, return_annotation=int)

    def test_update_self_ignore_existing_anno(self):
        """Don't annotate first arg of instance methods if asked to ignore"""
        sig = Signature.from_callable(UpdateSignatureHelper.an_instance_method)
        sig = update_signature_args(sig, {'self': UpdateSignatureHelper}, has_self=True,
                                    existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE)
        expected = Signature(parameters=[Parameter('self', Parameter.POSITIONAL_OR_KEYWORD)])
        assert sig == expected

    def test_update_arg_ignore_existing_anno_None(self):
        """Update arg annotations from types"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(
            sig, {'a': None, 'b': int}, has_self=False, existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE)
        params = [
            Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=inspect.Parameter.empty),
            Parameter('b', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
        ]
        assert sig == Signature(parameters=params, return_annotation=int)

    def test_update_arg_avoid_incompatible_anno(self):
        """Can generate stub with no annotations where they already exist in the source."""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_args(
            sig, {'a': int, 'b': int}, has_self=False, existing_annotation_strategy=ExistingAnnotationStrategy.OMIT)
        params = [
            Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=inspect.Parameter.empty),
            Parameter('b', Parameter.POSITIONAL_OR_KEYWORD, annotation=int)
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

    def test_avoid_incompatible_return(self):
        """Generate stub for application with no annotation where source has one"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_return(
            sig, return_type=str, existing_annotation_strategy=ExistingAnnotationStrategy.OMIT)
        expected = Signature(
            parameters=[
                Parameter('a', Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                Parameter('b', Parameter.POSITIONAL_OR_KEYWORD)
            ],
        )
        assert sig == expected

    def test_update_return_with_anno_ignored(self):
        """Leave existing return annotations alone"""
        sig = Signature.from_callable(UpdateSignatureHelper.has_annos)
        sig = update_signature_return(
            sig, return_type=str, existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE)
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
    cases = [
        (Dummy.a_static_method, FunctionKind.STATIC),
        (Dummy.a_class_method.__func__, FunctionKind.CLASS),
        (Dummy.an_instance_method, FunctionKind.INSTANCE),
        (Dummy.a_property.fget, FunctionKind.PROPERTY),
        (a_module_func, FunctionKind.MODULE),
    ]
    if cached_property:
        cases.append((Dummy.a_cached_property.func, FunctionKind.DJANGO_CACHED_PROPERTY))

    @pytest.mark.parametrize(
        'func, expected',
        cases,
    )
    def test_from_callable(self, func, expected):
        assert FunctionKind.from_callable(func) == expected


class TestFunctionDefinition:
    cases = [
        (Dummy.a_static_method, False),
        (Dummy.a_class_method.__func__, True),
        (Dummy.an_instance_method, True),
        (Dummy.a_property.fget, True),
        (a_module_func, False),
    ]
    if cached_property:
        cases.append((Dummy.a_cached_property.func, True))

    @pytest.mark.parametrize(
        'func, expected',
        cases,
    )
    def test_has_self(self, func, expected):
        defn = FunctionDefinition.from_callable(func)
        assert defn.has_self == expected

    cases = [
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
        (a_module_func, FunctionDefinition(
            'tests.test_stubs', 'a_module_func', FunctionKind.MODULE,
            Signature.from_callable(a_module_func))),
        (an_async_func, FunctionDefinition(
            'tests.test_stubs', 'an_async_func', FunctionKind.MODULE,
            Signature.from_callable(a_module_func), is_async=True)),
    ]
    if cached_property:
        cases.append(
            (Dummy.a_cached_property.func, FunctionDefinition(
                'tests.util', 'Dummy.a_cached_property', FunctionKind.DJANGO_CACHED_PROPERTY,
                Signature.from_callable(Dummy.a_cached_property.func)))
        )

    @pytest.mark.parametrize(
        'func, expected',
        cases,
    )
    def test_from_callable(self, func, expected):
        defn = FunctionDefinition.from_callable(func)
        assert defn == expected

    @pytest.mark.parametrize(
        'func, arg_types, return_type, yield_type, expected',
        [
            # Non-TypedDict case.
            (
                Dummy.an_instance_method,
                {'foo': int, 'bar': List[str]},
                int,
                None,
                FunctionDefinition(
                    'tests.util',
                    'Dummy.an_instance_method',
                    FunctionKind.INSTANCE,
                    Signature(
                        parameters=[
                            Parameter(name='self', kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=Parameter.empty),
                            Parameter(name='foo', kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                            Parameter(name='bar', kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=List[str]),
                        ],
                        return_annotation=int,
                    ),
                    False,
                    [],
                )
            ),
            # TypedDict: Add class definitions and use the class names as types.
            (
                Dummy.an_instance_method,
                {
                    'foo': make_typed_dict(required_fields={'a': int, 'b': str}),
                    'bar': make_typed_dict(required_fields={'c': int}),
                },
                int,
                None,
                FunctionDefinition(
                    'tests.util',
                    'Dummy.an_instance_method',
                    FunctionKind.INSTANCE,
                    Signature(
                        parameters=[
                            Parameter(name='self', kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=Parameter.empty),
                            Parameter(name='foo', kind=Parameter.POSITIONAL_OR_KEYWORD,
                                      annotation=make_forward_ref('FooTypedDict__RENAME_ME__')),
                            Parameter(name='bar', kind=Parameter.POSITIONAL_OR_KEYWORD,
                                      annotation=make_forward_ref('BarTypedDict__RENAME_ME__')),
                        ],
                        return_annotation=int,
                    ),
                    False,
                    [
                        ClassStub(
                            name='FooTypedDict__RENAME_ME__(TypedDict)',
                            function_stubs=[],
                            attribute_stubs=[
                                AttributeStub('a', int),
                                AttributeStub('b', str),
                            ]
                        ),
                        ClassStub(
                            name='BarTypedDict__RENAME_ME__(TypedDict)',
                            function_stubs=[],
                            attribute_stubs=[
                                AttributeStub('c', int),
                            ]
                        ),
                    ],
                )
            ),
        ],
    )
    def test_from_callable_and_traced_types(self, func, arg_types,
                                            return_type, yield_type, expected):
        function = FunctionDefinition.from_callable_and_traced_types(
            func, arg_types,
            return_type, yield_type,
            existing_annotation_strategy=ExistingAnnotationStrategy.IGNORE
        )
        assert function == expected


def tie_helper(a, b):
    pass


class TestShrinkTracedTypes:
    def test_shrink_args(self):
        traces = [
            CallTrace(tie_helper, {'a': str, 'b': int}),
            CallTrace(tie_helper, {'a': str, 'b': NoneType}),
        ]
        assert shrink_traced_types(traces, max_typed_dict_size=0) == ({'a': str, 'b': Optional[int]}, None, None)

    def test_shrink_return(self):
        traces = [
            CallTrace(tie_helper, {}, NoneType),
            CallTrace(tie_helper, {}, str),
        ]
        assert shrink_traced_types(traces, max_typed_dict_size=0) == ({}, Optional[str], None)

    def test_shrink_yield(self):
        traces = [
            CallTrace(tie_helper, {}, yield_type=int),
            CallTrace(tie_helper, {}, yield_type=str),
        ]
        assert shrink_traced_types(traces, max_typed_dict_size=0) == ({}, None, Union[int, str])


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

    def test_callable(self):
        assert get_imports_for_annotation(Callable) == {'typing': {'Callable'}}

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


class TestGetImportsForSignature:
    def test_default_none_parameter_imports(self):
        stub = FunctionStub('test', inspect.signature(default_none_parameter), FunctionKind.MODULE)
        expected = {'typing': {'Optional'}}
        assert get_imports_for_signature(stub.signature) == expected
