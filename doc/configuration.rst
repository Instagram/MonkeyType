.. module:: monkeytype.config

Configuration
-------------

Most of the useful ways to configure MonkeyType require writing Python code to
implement your preferred behavior, so MonkeyType's configuration is done in
Python code. To customize MonkeyType, you:

1. subclass :class:`monkeytype.config.Config` or :class:`monkeytype.config.DefaultConfig`,
2. override one or more methods in your subclass,
3. instantiate your subclass, and
4. point MonkeyType to your custom ``Config`` instance.

Let's look at those steps in more detail.

Subclassing ``Config`` or ``DefaultConfig``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. class:: Config()

  ``Config`` is the "empty" config; it's not usable out of the box, and requires
  your subclass to fill in some blanks in order to get useful behavior. It has
  the following methods:

  .. method:: trace_store() -> CallTraceStore

    Should return the :class:`~monkeytype.db.base.CallTraceStore` subclass you
    want to use to store your call traces.

    This is the one method you must override if you subclass the empty
    ``Config``.

  .. method:: trace_logger() -> CallTraceLogger

    Should return the :class:`~monkeytype.tracing.CallTraceLogger` subclass you
    want to use to log your call traces.

    If you don't override, this returns an instance of
    :class:`~monkeytype.db.base.CallTraceStoreLogger` initialized with your
    :meth:`trace_store`.

  .. method:: code_filter() -> CodeFilter

    Should return the :doc:`code filter <filters>` that categorizes traced
    functions into ones you are interested in (so their traces should be stored)
    and ones you aren't (their traces will be ignored).

    If you don't override, returns ``None``, meaning all traces will be stored.
    This will probably include a lot of standard-library and third-party
    functions!

  .. method:: sample_rate() -> int

    Should return the integer sampling rate for your logged call traces. If you
    return an integer N from this method, 1/N function calls will be traced and
    logged.

    If you don't override, returns ``None``, which disables sampling; all
    function calls will be traced and logged.

  .. method:: type_rewriter() -> TypeRewriter

    Should return the :class:`~monkeytype.typing.TypeRewriter` which will be
    applied to all your types when stubs are generated.

    If you don't override, returns :class:`~monkeytype.typing.NoOpRewriter`,
    which doesn't rewrite any types.

.. class:: DefaultConfig()

  ``DefaultConfig`` is the config MonkeyType uses if you don't provide your own;
  it's usable as-is, and you can inherit it if you just want to make some tweaks
  to the default setup. ``DefaultConfig`` overrides the following methods from
  :class:`Config`:

  .. method:: trace_store() -> SQLiteStore

    Returns an instance of :class:`~monkeytype.db.sqlite.SQLiteStore`, which
    stores call traces in a local SQLite database, in the file
    ``monkeytype.sqlite`` in the current directory.

  .. method:: code_filter() -> CodeFilter

    Returns a predicate function that excludes code in the Python standard
    library and installed third-party packages from call trace logging.

  .. method:: type_rewriter() -> ChainedRewriter

    Returns an instance of :class:`~monkeytype.typing.ChainedRewriter`
    initialized with the :class:`~monkeytype.typing.RemoveEmptyContainers`,
    :class:`~monkeytype.typing.RewriteConfigDict`, and
    :class:`~monkeytype.typing.RewriteLargeUnion` type rewriters.

Using your custom config subclass
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you've written a :class:`Config` or :class:`DefaultConfig` subclass, you
need to tell MonkeyType to use it. To do this, you instantiate it, and then
point MonkeyType to that instance. For example, let's say you mostly like the
default config, but you want to add a sampling rate, so you put this
configuration code in a file ``mtconfig.py``::

  from monkeytype.config import DefaultConfig

  class MyConfig(DefaultConfig):
      def sample_rate(self):
          return 1000

  my_config = MyConfig()

When tracing calls using the :func:`monkeytype.trace` context manager, you can
just pass your config object to it::

  from monkeytype import trace
  from mtconfig import my_config

  with trace(my_config):
      # ... run some code you want to trace here ...

When running :doc:`the command line utility <commandline>`, use the ``--config``
or ``-c`` option to point MonkeyType to your config, e.g.::

  $ monkeytype -c mtconfig:my_config stub some.module
