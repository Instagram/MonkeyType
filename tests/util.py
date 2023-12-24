# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import inspect
import os
from types import FrameType
from typing import (
    Any,
    List,
    Optional,
)

from monkeytype.compat import cached_property


class Dummy:
    @staticmethod
    def a_static_method(foo: Any) -> Optional[FrameType]:
        return inspect.currentframe()

    @classmethod
    def a_class_method(cls, foo: Any) -> Optional[FrameType]:
        return inspect.currentframe()

    def an_instance_method(self, foo: Any, bar: Any) -> Optional[FrameType]:
        return inspect.currentframe()

    def has_complex_signature(
        self,
        a: Any,
        b: Any,
        /,
        c: Any,
        d: Any = 0,
        *e: Any,
        f: Any,
        g: Any = 0,
        **h: Any,
    ) -> Optional[FrameType]:
        return inspect.currentframe()

    @property
    def a_property(self) -> Optional[FrameType]:
        return inspect.currentframe()

    @property
    def a_settable_property(self) -> Optional[FrameType]:
        return inspect.currentframe()

    @a_settable_property.setter
    def a_settable_property(self, unused) -> Optional[FrameType]:
        return inspect.currentframe()

    if cached_property:
        @cached_property
        def a_cached_property(self) -> Optional[FrameType]:
            return inspect.currentframe()


class Outer:
    class Inner:
        def f(self) -> None:
            pass


def transform_path(path: str) -> str:
    """Transform tests/test_foo.py to monkeytype.foo"""
    path = 'monkeytype/' + path[len('tests/'):]
    *basepath, file_name = path.split('/')
    basename, _ext = os.path.splitext(file_name[len('test_'):])
    return '.'.join(basepath + [basename])


def smartcov_paths_hook(paths: List[str]) -> List[str]:
    """Given list of test files to run, return modules to measure coverage of."""
    if not paths:
        return ['monkeytype']
    return [
        transform_path(path)
        for path
        in paths
    ]
