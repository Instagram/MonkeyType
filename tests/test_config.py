# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
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
        assert config.default_code_filter(
            config.default_code_filter.__wrapped__.__code__
        )

    def test_excludes_frozen_importlib(self):
        assert not config.default_code_filter(
            _frozen_importlib.spec_from_loader.__code__
        )

    def test_includes_stdlib_in_MONKEYTYPE_TRACE_MODULES(self, monkeypatch):
        monkeypatch.setenv("MONKEYTYPE_TRACE_MODULES", "sysconfig")
        assert config.default_code_filter(sysconfig.get_config_vars.__code__)
        monkeypatch.delenv("MONKEYTYPE_TRACE_MODULES")
