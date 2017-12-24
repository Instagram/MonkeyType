Storing call traces
-------------------

MonkeyType operates in two phases: :doc:`call tracing <tracing>` and :doc:`stub
generation <generation>`. You first run some code under MonkeyType tracing and
store the traced calls. You can do this repeatedly, maybe even sampled in
production continually so you always have up-to-date traces available. Then
whenever you need, you run ``monkeytype stub`` or ``monkeytype apply`` to
generate annotations based on types from the recorded traces.

In order to do this, MonkeyType needs a backing store for the recorded call
traces. By default it will use :class:`~monkeytype.db.sqlite.SQLiteStore`, which
stores traces in a local SQLite database file. But you can write your own
:class:`~monkeytype.db.base.CallTraceStore` subclass to store traces in whatever
data store works best for you, and return an instance of your custom store from
the :meth:`~monkeytype.config.Config.trace_store` method of your
:class:`~monkeytype.config.Config` class.

.. module:: monkeytype.db.base

CallTraceStore interface
~~~~~~~~~~~~~~~~~~~~~~~~

The ``CallTraceStore`` base class defines the interface that all call-trace
stores must implement. The :class:`~monkeytype.db.sqlite.SQLiteStore` subclass
provides a useful example implementation of the :class:`CallTraceStore`
interface.

.. class:: CallTraceStore

  .. classmethod:: make_store(connection_string: str) -> CallTraceStore

    Create and return an instance of the store, given a connection string.

    The format and interpretation of the connection string is entirely up to the
    store class. Typically it might be e.g. a URI like
    ``mysql://john:pass@localhost:3306/my_db``.

  .. method:: add(traces: Iterable[CallTrace]) -> None

    Store one or more :class:`~monkeytype.typing.CallTrace` instances.

    Implementations of this method will probably find the
    :func:`~monkeytype.encoding.serialize_traces` function useful.

  .. method:: filter(module: str, qualname_prefix: Optional[str] = None, limit: int = 2000) -> List[CallTraceThunk]

    Query call traces from the call trace store. The ``module`` argument should
    be provided as a dotted Python import path (e.g. ``some.module``).

    The store should return the most recent ``limit`` traces available for the
    given ``module`` and ``qualname``.

    The returned :class:`CallTraceThunk` instances can be any object that
    implements a :meth:`~CallTraceThunk.to_trace` zero-argument method returning
    a :class:`~monkeytype.typing.CallTrace` instance. This allows callers of
    ``filter`` to handle deserialization errors as desired per-trace.

    Most stores will choose to return instances of
    :class:`~monkeytype.encoding.CallTraceRow`, which implements a
    :meth:`~monkeytype.encoding.CallTraceRow.to_trace` that deserializes traces
    from the same JSON format that its
    :meth:`~monkeytype.encoding.CallTraceRow.from_trace` classmethod serializes
    to.

.. module:: monkeytype.db.sqlite

SQLiteStore
~~~~~~~~~~~

MonkeyType bundles one sample store implementation, which
:class:`~monkeytype.config.DefaultConfig` uses as the default store. It stores
call traces in a SQLite database in a local file.

.. class:: SQLiteStore

  .. classmethod:: make_store(connection_string: str) -> SQLiteStore

    The ``connection_string`` argument will be passed straight through to the
    Python standard library `sqlite module`_.

  .. method:: add(traces: Iterable[CallTrace]) -> None

    Store one or more :class:`~monkeytype.typing.CallTrace` instances in the
    SQLite database, encoded via :class:`~monkeytype.encoding.CallTraceRow`.

  .. method:: filter(module: str, qualname_prefix: Optional[str] = None, limit: int = 2000) -> List[CallTraceRow]

    Query up to ``limit`` call traces from the SQLite database for a given
    ``module`` and optional ``qualname_prefix``, returning each as a
    :class:`~monkeytype.encoding.CallTraceRow` instance.

.. _sqlite module: https://docs.python.org/3/library/sqlite3.html

.. module:: monkeytype.encoding

serialize_traces
~~~~~~~~~~~~~~~~

.. function:: serialize_traces(traces: Iterable[CallTrace]) -> Iterable[CallTraceRow]

  Serialize an iterable of :class:`~monkeytype.tracing.CallTrace` to an iterable
  of :class:`CallTraceRow` (via :meth:`CallTraceRow.from_trace`). If any trace
  fails to serialize, the exception is logged and serialization continues.

CallTraceRow
~~~~~~~~~~~~

The :class:`CallTraceRow` class implements serialization/deserialization of
:class:`~monkeytype.tracing.CallTrace` instances to/from JSON. See the
implementation of :class:`~monkeytype.db.sqlite.SQLiteStore` for example usage.

It is not required for a custom store to use :class:`CallTraceRow`; a store may
choose to implement its own alternative (de)serialization.

.. class:: CallTraceRow

  .. classmethod:: from_trace(trace: CallTrace) -> CallTraceRow

    Serialize a :class:`CallTraceRow` from the given
    :class:`~monkeytype.tracing.CallTrace`.

  .. method:: to_trace() -> CallTrace

    Deserialize and return the :class:`~monkeytype.tracing.CallTrace`
    represented by this :class:`CallTraceRow`.

  .. attribute:: module: str

    The module in which the traced function is defined, e.g. ``some.module``.

  .. attribute:: qualname: str

    The ``__qualname__`` of the traced function or method, e.g. ``some_func``
    for a top-level function or ``SomeClass.some_method`` for a method.

  .. attribute:: arg_types: str

    A JSON-serialized representation of the concrete argument types for a single
    traced call. See the implementation for details of the format.

  .. attribute:: return_type: Optional[str]

    A JSON-serialized representation of the actual return type of this traced
    call, or ``None`` if this call did not return (i.e. yielded instead).

  .. attribute:: yield_type: Optional[str]

    A JSON-serialized representation of the actual yield type for this traced
    call, or ``None`` if this call did not yield (i.e. returned instead).

.. currentmodule:: monkeytype.db.base

CallTraceThunk
~~~~~~~~~~~~~~

The minimal required interface of the objects returned from
:meth:`CallTraceStore.filter`. Most stores will use
:class:`~monkeytype.encoding.CallTraceRow` to satisfy this interface.

.. class:: CallTraceThunk

  .. method:: to_trace() -> CallTrace

    Produce a :class:`~monkeytype.tracing.CallTrace` instance based on the
    serialized trace data stored in this thunk.
