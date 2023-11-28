# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import logging
import sqlite3
from typing import Any, Iterable, List, Optional, cast

from monkeytype.db.base import CallTraceStore, CallTraceThunk
from monkeytype.encoding import CallTraceRow, serialize_traces
from monkeytype.tracing import CallTrace

logger = logging.getLogger(__name__)


def create_call_trace_tables(conn: sqlite3.Connection) -> None:
    queries = [
        """CREATE TABLE IF NOT EXISTS monkeytype_signatures (
            id INTEGER PRIMARY KEY,
            arg_types VARCHAR,
            return_type VARCHAR,
            yield_type VARCHAR
        )""",
        """CREATE TABLE IF NOT EXISTS monkeytype_modules (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            UNIQUE (name)
        )""",
        """CREATE TABLE IF NOT EXISTS monkeytype_functions (
            id INTEGER PRIMARY KEY,
            qualname VARCHAR NOT NULL,
            module_id INTEGER,
            FOREIGN KEY(module_id) REFERENCES monkeytype_modules (id),
            UNIQUE (qualname)
        )""",
        """CREATE TABLE IF NOT EXISTS monkeytype_functions_signatures (
            function_id INTEGER,
            signature_id INTEGER,
            PRIMARY KEY (function_id, signature_id),
            FOREIGN KEY(function_id) REFERENCES monkeytype_functions (id),
            FOREIGN KEY(signature_id) REFERENCES monkeytype_signatures (id)
        )""",
    ]

    with conn:
        for query in queries:
            conn.execute(query)


class SQLiteStore(CallTraceStore):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def make_store(cls, connection_string: str) -> "CallTraceStore":
        conn = sqlite3.connect(connection_string)
        create_call_trace_tables(conn)
        return cls(conn)

    def get_signature(
        self, arg_types: str, return_type: Optional[str], yield_type: Optional[str]
    ) -> Optional[int]:
        cur = self.conn.cursor()

        values = []
        cons = []

        def add_value(name: str, value: Optional[str]) -> None:
            if value is None:
                cons.append(f"({name} IS NULL)")
            else:
                cons.append(f"({name} == (?))")
                values.append(value)

        add_value("arg_types", arg_types)
        add_value("return_type", return_type)
        add_value("yield_type", yield_type)

        all_cons = " AND ".join(cons)

        query = f"""
        SELECT id FROM monkeytype_signatures
        WHERE {all_cons}
        """

        cur.execute(query, values)
        row = cur.fetchone()

        if row:
            return cast(int, row[0])

        return None

    def get_or_add_signature(
        self, arg_types: str, return_type: Optional[str], yield_type: Optional[str]
    ) -> int:
        signature = self.get_signature(arg_types, return_type, yield_type)

        if signature is not None:
            return signature

        print(f"Adding signature: {arg_types}, {return_type}, {yield_type}")

        cur = self.conn.cursor()

        query = "INSERT INTO monkeytype_signatures(arg_types, return_type, yield_type) VALUES(?, ?, ?) RETURNING id"

        values = [arg_types, return_type, yield_type]

        cur.execute(query, values)

        row = cur.fetchone()
        return cast(int, row[0])

    def get_module(self, qualname: str) -> Optional[int]:
        cur = self.conn.cursor()

        query = "SELECT id FROM monkeytype_modules WHERE name == ?"

        cur.execute(query, [qualname])

        row = cur.fetchone()

        if row:
            return cast(int, row[0])

        return None

    def get_or_add_module(self, name: str) -> int:
        module = self.get_module(name)

        if module is not None:
            return module

        cur = self.conn.cursor()
        query = "INSERT INTO monkeytype_modules(name) VALUES (?) RETURNING id"
        cur.execute(query, [name])

        row = cur.fetchone()
        return cast(int, row[0])

    def get_function(self, qualname: str) -> Optional[int]:
        cur = self.conn.cursor()

        query = "SELECT id FROM monkeytype_functions WHERE qualname == (?)"

        cur.execute(query, [qualname])

        row = cur.fetchone()

        if row:
            return cast(int, row[0])

        return None

    def get_or_add_function(self, trace: CallTraceRow) -> int:
        func = self.get_function(trace.qualname)

        if func is not None:
            return func

        module = self.get_or_add_module(trace.module)

        # assert module is not None

        cur = self.conn.cursor()

        query = "INSERT INTO monkeytype_functions(qualname, module_id) VALUES(?, ?) RETURNING id"

        values = [trace.qualname, module]

        cur.execute(query, values)

        row = cur.fetchone()
        func = cast(int, row[0])

        signature = self.get_or_add_signature(
            trace.arg_types, trace.return_type, trace.yield_type
        )

        self.add_signature_to_function(func, signature)

        return func

    def add_signature_to_function(self, function: int, signature: int) -> None:
        cur = self.conn.cursor()

        query = """
        INSERT INTO monkeytype_functions_signatures(function_id, signature_id) VALUES(?, ?)
        ON CONFLICT(function_id, signature_id) DO NOTHING
        """

        values = [function, signature]

        cur.execute(query, values)

    def add_trace(self, trace: CallTraceRow) -> None:
        func = self.get_or_add_function(trace)

        arg_types = trace.arg_types
        return_type = trace.return_type
        yield_type = trace.yield_type

        signature = self.get_or_add_signature(arg_types, return_type, yield_type)

        self.add_signature_to_function(func, signature)

    def add(self, traces: Iterable[CallTrace]) -> None:
        with self.conn:
            for trace in serialize_traces(traces):
                self.add_trace(trace)

    def filter(
        self, name: str, qualname_prefix: Optional[str] = None, limit: int = 2000
    ) -> List[CallTraceThunk]:
        cur = self.conn.cursor()

        values: List[Any] = [name]

        qualname_cond = ""

        if qualname_prefix is not None:
            qualname_cond = "AND func.qualname LIKE (?) || '%'"
            values.append(qualname_prefix)

        query = f"""
        SELECT func.qualname, module.name, sig.arg_types, sig.return_type, sig.yield_type
        FROM monkeytype_functions func
        JOIN monkeytype_functions_signatures func_sig ON func.id = func_sig.function_id
        JOIN monkeytype_signatures sig ON func_sig.signature_id = sig.id
        JOIN monkeytype_modules module ON func.module_id = module.id
        WHERE module.name == (?)
        {qualname_cond}
        LIMIT (?)
        """

        values.append(limit)

        cur.execute(query, values)

        rows: List[CallTraceThunk] = []

        for row in cur.fetchall():
            (qualname, module, arg_types, return_type, yield_type) = row
            trace_row = CallTraceRow(
                module, qualname, arg_types, return_type, yield_type
            )
            rows.append(trace_row)

        return rows

    def list_modules(self) -> List[str]:
        cur = self.conn.cursor()

        query = "SELECT name FROM monkeytype_modules"

        cur.execute(query)
        rows = cur.fetchall()

        return [row[0] for row in rows]
