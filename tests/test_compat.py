# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from typing import Union

from monkeytype.compat import is_generic, is_union, name_of_generic


def test_name_of_union():
    typ = Union[int, str]
    assert name_of_generic(typ) == "Union"


def test_is_union_and_is_generic():
    typ = Union[int, str]
    assert is_union(typ)
    assert is_generic(typ)
