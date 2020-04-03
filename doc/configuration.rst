.. module:: monkeytype.config

Configuration
-------------

Most of the useful ways to configure MonkeyType require writing Python code to
implement your preferred behavior, so MonkeyType's configuration is done in
Python code. To customize MonkeyType, you:

1. subclass :class:`monkeytype.config.Config` or :class:`monkeytype.config.DefaultConfig`,
2. override one or more methods in your subclass,
3. instantiate your subclass, and
4. point MonkeyType to your custom :class:`Config` instance.

Let's look at those steps in more detail.

Subclassing ``Config`` or ``DefaultConfig``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. class:: Config()

  ``Config`` is the "empty" config; it's not usable out of the box, and requires
  your subclass to fill in some blanks in order to get useful behavior. It has
  the following methods:

  .. method:: trace_store() -> CallTraceStore

    Return the :class:`~monkeytype.db.base.CallTraceStore` subclass you want to
    use to store your call traces.

    This is the one method you must override if you subclass the empty
    ``Config``.

  .. method:: trace_logger() -> CallTraceLogger

    Return the :class:`~monkeytype.tracing.CallTraceLogger` subclass you want
    to use to log your call traces.

    If you don't override, this returns an instance of
    :class:`~monkeytype.db.base.CallTraceStoreLogger` initialized with your
    :meth:`trace_store`.

  .. method:: code_filter() -> CodeFilter

    Return the :ref:`code filter <codefilters>` that categorizes traced
    functions into ones you are interested in (so their traces should be
    stored) and ones you aren't (their traces will be ignored).

    If you don't override, returns ``None``, meaning all traces will be stored.
    This will probably include a lot of standard-library and third-party
    functions!

  .. method:: sample_rate() -> int

    Return the integer sampling rate for your logged call traces. If you return
    an integer N from this method, 1/N function calls will be traced and
    logged.

    If you don't override, returns ``None``, which disables sampling; all
    function calls will be traced and logged.

  .. method:: type_rewriter() -> TypeRewriter

    Return the :class:`~monkeytype.typing.TypeRewriter` which will be applied
    to all your types when stubs are generated.

    If you don't override, returns :class:`~monkeytype.typing.NoOpRewriter`,
    which doesn't rewrite any types.

  .. method:: query_limit() -> int

    The maximum number of call traces to query from the trace store when
    generating stubs. If you have recorded a lot of traces, increasing this
    limit may improve stub accuracy, at the cost of slower stub generation.

    On the other hand, if some of your recorded traces are out of date because
    the code has changed, and you haven't purged your trace store, increasing
    this limit could make stubs worse by including more outdated traces.

    Defaults to 2000.

  .. method:: cli_context(command: str) -> Iterator[None]

    A context manager which wraps the execution of the CLI command.

    MonkeyType has to import your code in order to generate stubs for it. In
    some cases, like if you're using Django, setup is required before your code
    can be imported. Use this method to define the necessary setup or teardown
    for your codebase.

    This method must return a `context manager`_ instance. In most cases, the
    simplest way to do this will be with the `contextlib.contextmanager`_
    decorator. For example, if you run MonkeyType against a Django codebase,
    you can setup Django before the command runs::

      @contextmanager
      def cli_context(self, command: str) -> Iterator[None]:
          import django
          django.setup()
          yield

    ``command`` is the name of the command passed to the monkeytype cli:
    ``'run'``, ``'apply'``, etc.

    The default implementation of this method returns a no-op context manager.

    .. _context manager: https://docs.python.org/3/reference/datamodel.html#with-statement-context-managers
    .. _contextlib.contextmanager: https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager

 .. method:: max_typed_dict_size() -> int

   The maximum size of string-keyed dictionary for which per-key value types
   will be stored, and (if the traced keys and value types are consistent), a
   `TypedDict` will be emitted instead of `Dict`. Return `0` to disable per-key
   type tracking and TypedDict generation.

   Defaults to 0.

.. class:: DefaultConfig()

  ``DefaultConfig`` is the config MonkeyType uses if you don't provide your own;
  it's usable as-is, and you can inherit it if you just want to make some tweaks
  to the default setup. ``DefaultConfig`` overrides the following methods from
  :class:`Config`:

  .. method:: trace_store() -> SQLiteStore

    Returns an instance of :class:`~monkeytype.db.sqlite.SQLiteStore`, which
    stores call traces in a local SQLite database, by default in the file
    ``monkeytype.sqlite3`` in the current directory. You can override the path
    to the SQLite database by setting the ``MT_DB_PATH`` environment variable.

  .. method:: code_filter() -> CodeFilter

    Returns the default code filter predicate function. If an environment
    variable ``MONKEYTYPE_TRACE_MODULES`` is defined with one or more comma
    separated package and/or module names, the default code filter traces only
    functions within the listed modules. Otherwise the default filter excludes
    code in the Python standard library and installed site-packages, and traces
    all other functions.

  .. method:: type_rewriter() -> ChainedRewriter

    Returns an instance of :class:`~monkeytype.typing.ChainedRewriter`
    initialized with the :class:`~monkeytype.typing.RemoveEmptyContainers`,
    :class:`~monkeytype.typing.RewriteConfigDict`, and
    :class:`~monkeytype.typing.RewriteLargeUnion` type rewriters.

Using your custom config subclass
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you've written a :class:`Config` or :class:`DefaultConfig` subclass, you
need to instantiate it and point MonkeyType to that instance. The easiest way to
do this is to create a file named ``monkeytype_config.py`` and create a
:class:`~Config` instance in it named ``CONFIG``; MonkeyType will find and use
this config automatically.

For example, let's say you mostly like the default config, but you want to add a
sampling rate, so you put this code in the file ``monkeytype_config.py``::

  from monkeytype.config import DefaultConfig

  class MyConfig(DefaultConfig):
      def sample_rate(self):
          return 1000

  CONFIG = MyConfig()

MonkeyType will automatically find and use this config (as long as
``monkeytype_config.py`` is on the Python path).

Specifying a config
'''''''''''''''''''

You can also explicitly specify the config instance to use. For instance, when
tracing calls using the :func:`monkeytype.trace` context manager, you can just
pass your config object to it::

  from monkeytype import trace
  from some.module import my_config

  with trace(my_config):
      # ... run some code you want to trace here ...

When running :doc:`the command line utility <generation>`, use the ``--config``
or ``-c`` option to point MonkeyType to your config, e.g.::

  $ monkeytype -c some.module:my_config stub some.module
