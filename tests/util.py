# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
import inspect
from types import FrameType
from typing import (
    Any,
    Optional,
)


class Dummy:
    @staticmethod
    def a_static_method(foo: Any) -> Optional[FrameType]:
        return inspect.currentframe()

    @classmethod
    def a_class_method(cls, foo: Any) -> Optional[FrameType]:
        return inspect.currentframe()

    def an_instance_method(self, foo: Any, bar: Any) -> Optional[FrameType]:
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
