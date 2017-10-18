import datetime
import logging
import json
import sqlite3

from typing import (
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from monkeytype.db.base import (
    CallTraceThunk,
    CallTraceStore,
)
from monkeytype.tracing import CallTrace
from monkeytype.util import (
    get_func_in_module,
    type_from_dict,
    type_to_dict,
)

logger = logging.getLogger(__name__)


CallTraceRowT = TypeVar('CallTraceRowT', bound='CallTraceRow')


def decode_type_field(typ_json: Optional[str]) -> Optional[type]:
    """Reify an encoded type"""
    typ: Optional[type] = None
    if (typ_json is not None) and (typ_json != 'null'):
        typ_dict = json.loads(typ_json)
        typ = type_from_dict(typ_dict)
    return typ


class CallTraceRow(CallTraceThunk):
    def __init__(
        self,
        module: str,
        qualname: str,
        arg_types: str,
        return_type: Optional[str] = None,
        yield_type: Optional[str] = None
    ) -> None:
        self.module = module
        self.qualname = qualname
        self.arg_types = arg_types
        self.return_type = return_type
        self.yield_type = yield_type

    @classmethod
    def from_trace(cls: Type[CallTraceRowT], trace: CallTrace) -> CallTraceRowT:
        arg_types = {name: type_to_dict(typ) for name, typ in trace.arg_types.items()}
        arg_types_json = json.dumps(arg_types, sort_keys=True)
        return_type = None
        if trace.return_type is not None:
            return_type = json.dumps(type_to_dict(trace.return_type), sort_keys=True)
        yield_type = None
        if trace.yield_type is not None:
            yield_type = json.dumps(type_to_dict(trace.yield_type), sort_keys=True)
        return cls(
            trace.func.__module__,
            trace.func.__qualname__,
            arg_types_json,
            return_type,
            yield_type
        )

    def to_trace(self) -> CallTrace:
        func = get_func_in_module(self.module, self.qualname)
        arg_types_dict = json.loads(self.arg_types)
        arg_types = {name: type_from_dict(d) for name, d in arg_types_dict.items()}
        return_type = decode_type_field(self.return_type)
        yield_type = decode_type_field(self.yield_type)
        return CallTrace(func, arg_types, return_type, yield_type)


DEFAULT_TABLE = 'monkeytype_call_traces'


def create_call_trace_table(conn: sqlite3.Connection, table: str = DEFAULT_TABLE) -> None:
    query = """
CREATE TABLE {table} (
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

    def add(self, traces: Iterable[CallTrace]) -> None:
        values = []
        for trace in traces:
            row = CallTraceRow.from_trace(trace)
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
