# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
from typing import ContextManager

from monkeytype.config import (
    Config,
    DEFAULT_CONFIG,
)
from monkeytype.tracing import trace_calls

__version__ = "17.10.0"


def trace(config: Config = DEFAULT_CONFIG) -> ContextManager:
    """Context manager to trace and log all calls.

    Simple wrapper around `monkeytype.tracing.trace_calls` that uses trace
    logger, code filter, and sample rate from given (or default) config.
    """
    return trace_calls(
        logger=config.trace_logger(),
        code_filter=config.code_filter(),
        sample_rate=config.sample_rate(),
    )
