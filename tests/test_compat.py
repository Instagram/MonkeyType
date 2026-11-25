# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import sys
from typing import Union

from monkeytype.compat import is_generic, is_union, name_of_generic


def test_name_of_union():
    typ = Union[int, str]
    assert name_of_generic(typ) == "Union"


def test_union_type_compat():
    assert is_union(Union[int, str])
    assert is_generic(Union[int, str])
    if sys.version_info >= (3, 10):
        assert is_union(int | str)
        assert is_generic(int | str)
        assert name_of_generic(int | str) == "Union"
