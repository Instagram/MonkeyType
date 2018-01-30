# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import datetime
import logging
import sqlite3

from typing import (
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)

from monkeytype.db.base import (
    CallTraceStore,
    CallTraceThunk,
)
from monkeytype.encoding import (
    CallTraceRow,
    serialize_traces,
)
from monkeytype.tracing import CallTrace

logger = logging.getLogger(__name__)


DEFAULT_TABLE = 'monkeytype_call_traces'


def create_call_trace_table(conn: sqlite3.Connection, table: str = DEFAULT_TABLE) -> None:
    query = """
CREATE TABLE IF NOT EXISTS {table} (
  created_at  TEXT,
  module      TEXT,
  qualname    TEXT,
  arg_types   TEXT,
  return_type TEXT,
  yield_type  TEXT);
""".format(table=table)
    with conn:
        conn.execute(query)


QueryValue = Union[str, int]
ParameterizedQuery = Tuple[str, List[QueryValue]]


def make_query(table: str, module: str, qualname: Optional[str], limit: int) -> ParameterizedQuery:
    raw_query = """
    SELECT
        module, qualname, arg_types, return_type, yield_type
    FROM {table}
    WHERE
        module == ?
    """.format(table=table)
    values: List[QueryValue] = [module]
    if qualname is not None:
        raw_query += " AND qualname LIKE ? || '%'"
        values.append(qualname)
    raw_query += """
    GROUP BY
        module, qualname, arg_types, return_type, yield_type
    ORDER BY date(created_at) DESC
    LIMIT ?
    """
    values.append(limit)
    return raw_query, values


class SQLiteStore(CallTraceStore):
    def __init__(self, conn: sqlite3.Connection, table: str = DEFAULT_TABLE) -> None:
        self.conn = conn
        self.table = table

    @classmethod
    def make_store(cls, connection_string: str) -> 'CallTraceStore':
        conn = sqlite3.connect(connection_string)
        create_call_trace_table(conn)
        return cls(conn)

    def add(self, traces: Iterable[CallTrace]) -> None:
        values = []
        for row in serialize_traces(traces):
            values.append((datetime.datetime.now(), row.module, row.qualname,
                           row.arg_types, row.return_type, row.yield_type))
        with self.conn:
            self.conn.executemany(
                'INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)'.format(table=self.table),
                values
            )

    def filter(
        self,
        module: str,
        qualname_prefix: Optional[str] = None,
        limit: int = 2000
    ) -> List[CallTraceThunk]:
        sql_query, values = make_query(self.table, module, qualname_prefix, limit)
        with self.conn:
            cur = self.conn.cursor()
            cur.execute(sql_query, values)
            return [CallTraceRow(*row) for row in cur.fetchall()]

    def list_modules(self) -> List[str]:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                        SELECT module FROM {table}
                        GROUP BY module
                        ORDER BY date(created_at) DESC
                        """.format(table=self.table))
            return [row[0] for row in cur.fetchall() if row[0]]
