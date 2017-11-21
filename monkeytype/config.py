# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
import os

from abc import (
    ABCMeta,
    abstractmethod,
)

from monkeytype.db.base import CallTraceStore
from monkeytype.db.sqlite import SQLiteStore
from monkeytype.typing import (
    DEFAULT_REWRITER,
    TypeRewriter,
)


class Config(metaclass=ABCMeta):
    """A Config ties together concrete implementations of the diffrent abstractions
    that make up a typical deployment of MonkeyType.
    """
    @abstractmethod
    def type_rewriter(self) -> TypeRewriter:
        """Returns the type rewriter that should be used by the CLI when generating
        stubs.
        """
        pass

    @abstractmethod
    def trace_store(self) -> CallTraceStore:
        pass


class DefaultConfig(Config):
    DB_PATH_VAR = 'MT_DB_PATH'

    def type_rewriter(self) -> TypeRewriter:
        return DEFAULT_REWRITER

    def trace_store(self) -> CallTraceStore:
        db_path = os.environ.get(self.DB_PATH_VAR, "monkeytype.sqlite3")
        return SQLiteStore.make_store(db_path)


DEFAULT_CONFIG = DefaultConfig()
