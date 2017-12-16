# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
import _frozen_importlib
import sysconfig

import pytest

from monkeytype import config


class TestDefaultCodeFilter:
    def test_excludes_stdlib(self):
        assert not config.default_code_filter(sysconfig.get_path.__code__)

    def test_excludes_site_packages(self):
        assert not config.default_code_filter(pytest.skip.__code__)

    def test_includes_otherwise(self):
        assert config.default_code_filter(config.default_code_filter.__code__)

    def test_excludes_frozen_importlib(self):
        assert not config.default_code_filter(_frozen_importlib.spec_from_loader.__code__)
