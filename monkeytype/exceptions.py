# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.


class MonkeyTypeError(Exception):
    pass


class NameLookupError(MonkeyTypeError):
    pass


class InvalidTypeError(MonkeyTypeError):
    pass
