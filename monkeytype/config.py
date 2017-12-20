# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from contextlib import contextmanager
import os
import sys
import sysconfig

from abc import (
    ABCMeta,
    abstractmethod,
)
from types import CodeType
from typing import Optional, Iterator

from monkeytype.db.base import (
    CallTraceStore,
    CallTraceStoreLogger,
)
from monkeytype.db.sqlite import SQLiteStore
from monkeytype.tracing import (
    CallTraceLogger,
    CodeFilter,
)
from monkeytype.typing import (
    DEFAULT_REWRITER,
    NoOpRewriter,
    TypeRewriter,
)


class Config(metaclass=ABCMeta):
    """A Config ties together concrete implementations of the different abstractions
    that make up a typical deployment of MonkeyType.
    """
    @abstractmethod
    def trace_store(self) -> CallTraceStore:
        """Return the CallTraceStore for storage/retrieval of call traces."""
        pass

    @contextmanager
    def cli_context(self, command: str) -> Iterator[None]:
        """Lifecycle hook that is called once right after the CLI
        starts.

        `command` is the name of the command passed to monkeytype
        ('run', 'apply', etc).
        """
        yield

    def trace_logger(self) -> CallTraceLogger:
        """Return the CallTraceLogger for logging call traces.

        By default, returns a CallTraceStoreLogger that logs to the configured
        trace store.
        """
        return CallTraceStoreLogger(self.trace_store())

    def code_filter(self) -> Optional[CodeFilter]:
        """Return the (optional) CodeFilter predicate for triaging calls.

        A CodeFilter is a callable that takes a code object and returns a
        boolean determining whether the call should be traced or not. If None is
        returned, all calls will be traced and logged.
        """
        return None

    def sample_rate(self) -> Optional[int]:
        """Return the sample rate for call tracing.

        By default, all calls will be traced. If an integer sample rate of N is
        set, 1/N calls will be traced.
        """
        return None

    def type_rewriter(self) -> TypeRewriter:
        """Return the type rewriter for use when generating stubs."""
        return NoOpRewriter()

    def query_limit(self) -> int:
        """Maximum number of traces to query from the call trace store."""
        return 2000

    def include_unparsable_defaults(self) -> bool:
        """Output stubs for functions with defaults with invalid reprs?"""
        return False


lib_paths = {sysconfig.get_path(n) for n in ['stdlib', 'purelib', 'platlib']}
# if in a virtualenv, also exclude the real stdlib location
venv_real_prefix = getattr(sys, 'real_prefix', None)
if venv_real_prefix:
    lib_paths.add(
        sysconfig.get_path('stdlib', vars={'installed_base': venv_real_prefix})
    )
# exclude code objects from frozen importlib, which have a bogus co_filename
lib_paths.add('<frozen importlib.')
LIB_PATHS = tuple(p for p in lib_paths if p is not None)


def default_code_filter(code: CodeType) -> bool:
    """A CodeFilter to exclude stdlib and site-packages."""
    return bool(code.co_filename and not code.co_filename.startswith(LIB_PATHS))


class DefaultConfig(Config):
    DB_PATH_VAR = 'MT_DB_PATH'

    def type_rewriter(self) -> TypeRewriter:
        return DEFAULT_REWRITER

    def trace_store(self) -> CallTraceStore:
        """By default we store traces in a local SQLite database.

        The path to this database file can be customized via the `MT_DB_PATH`
        environment variable.
        """
        db_path = os.environ.get(self.DB_PATH_VAR, "monkeytype.sqlite3")
        return SQLiteStore.make_store(db_path)

    def code_filter(self) -> CodeFilter:
        """Default code filter excludes standard library & site-packages."""
        return default_code_filter


def get_default_config() -> Config:
    """Use monkeytype_config.CONFIG if it exists, otherwise DefaultConfig().

    monkeytype_config is not a module that is part of the monkeytype
    distribution, it must be created by the user.
    """
    try:
        import monkeytype_config  # type: ignore
    except ImportError:
        return DefaultConfig()
    return monkeytype_config.CONFIG
