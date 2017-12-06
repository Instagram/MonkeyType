.. program:: monkeytype

Generating type annotations
---------------------------

MonkeyType comes with a ``monkeytype`` command-line script for generating and
applying stub files based on recorded call traces.

monkeytype stub
~~~~~~~~~~~~~~~

Run ``monkeytype stub some.module`` to generate a stub file for the given module
based on call traces queried from the trace store. If the module already has
some type annotations, those annotations will be respected and will not be
replaced with annotations derived from traced calls.

The generated stub file will be printed to standard output. If you want to save
it to a file, redirect the output to a file (e.g. ``monkeytype stub some.module >
some/module.pyi``).

You can also run e.g. ``monkeytype stub some.module:SomeClass`` or ``monkeytype
stub some.module:somefunc`` to generate a stub for just one class or function.

monkeytype apply
~~~~~~~~~~~~~~~~

If you prefer inline type annotations, ``monkeytype apply some.module`` will
generate annotations for ``some.module`` internally (in exactly the same way as
``monkeytype stub`` would), but rather than printing the annotations in stub
syntax, it will apply them directly to the code file, modifying it in-place.

Obviously this is best used when the file is tracked in a version-control
system, so you can easily see the changes made by MonkeyType and accept or
reject them. MonkeyType annotations are rarely suitable exactly as generated;
they are a starting point and usually require some adjustment by someone who
understands the code.

Options
~~~~~~~

Both ``monkeytype stub`` and ``monkeytype apply`` accept the same set of
options:

.. option:: -c <config-path>, --config <config-path>

  The location of the :doc:`config object <configuration>` defining your
  call-trace store and other configuration. The config-path should take the form
  ``some.module:name``, where ``name`` is the variable in ``some.module``
  containing your config instance.

  Optionally, the value can also include a ``()`` suffix, and MonkeyType will
  call/instantiate the imported function/class with no arguments to get the
  actual config instance.

  The default value is ``monkeytype.config:get_default_config()``, which tries
  the config path ``monkeytype_config:CONFIG`` and falls back to
  ``monkeytype.config:DefaultConfig()`` if there is no ``monkeytype_config``
  module. This allows creating a custom config that will be used by default just
  by creating ``monkeytype_config.py`` with a ``CONFIG`` instance in it.

.. option:: -l <limit>, --limit <limit>

  The maximum number of call traces to query from your call trace store.
  Increasing this number may give more accurate results, at the cost of longer
  runtime.

  Default: 2000

.. option:: --disable-type-rewriting

  Don't apply your configured :ref:`rewriters` to the output types.

.. option:: --include-unparsable-defaults

  In order to introspect function arguments and existing annotations and apply
  new annotations, MonkeyType imports your code and inspects function signatures
  via the ``inspect`` standard library module, and then turns this introspected
  signature back into a code string when generating a stub.

  Some function arguments may have complex default values whose ``repr()`` is
  not a valid Python expression. These cannot round-trip successfully through
  the introspection process, since importing your code does not give MonkeyType
  access to the original expression for the default value, as a string of Python
  code.

  By default MonkeyType will simply exclude such functions from stub file
  output, in order to ensure a valid stub file. Provide this option to instead
  include these functions, invalid syntax and all; you'll have to manually fix
  them up before the stub file will be usable.

.. module:: monkeytype.typing

.. _rewriters:

Type rewriters
~~~~~~~~~~~~~~

MonkeyType's built-in type generation is quite simple: it just makes a ``Union``
of all the types seen in traces for a given argument or return value, and
shrinks that ``Union`` to remove redundancy. All additional type transformations
are performed through configured type rewriters.

.. class:: TypeRewriter()

  The :class:`TypeRewriter` class provides a type-visitor that can be subclassed
  to easily implement custom type transformations.

  Subclasses can implement arbitrary ``rewrite_Foo`` methods for rewriting a
  type named ``Foo``. :class:`TypeRewriter` itself implements only
  ``rewrite_Dict``, ``rewrite_List``, ``rewrite_Set``, ``rewrite_Tuple``,
  ``rewrite_Union`` (in addition to the methods listed below). These methods
  just recursively rewrite all type arguments of the container types.

  For example type rewriter implementations, see the source code of the
  subclasses listed below.

  .. method:: rewrite(typ: type) -> type

    Public entry point to rewrite given type; return rewritten type.

  .. method:: generic_rewrite(typ: type) -> type

    Fallback method when no specific ``rewrite_Foo`` method is available for a
    visited type.

.. class:: RemoveEmptyContainers()

  Rewrites e.g. ``Union[List[Any], List[int]]`` to ``List[int]``. The former
  type frequently occurs when a method that takes ``List[int]`` also sometimes
  receives the empty list, which will be typed as ``List[Any]``.

.. class:: RewriteConfigDict()

  Takes a generated type like ``Union[Dict[K, V1], Dict[K, V2]]`` and rewrites
  it to ``Dict[K, Union[V1, V2]]``.

.. class:: RewriteLargeUnion(max_union_len: int = 5)

  Rewrites large unions (by default, more than 5 elements) to simply `Any`, for
  better readability of functions that aren't well suited to static typing.

.. class:: ChainedRewriter(rewriters: Iterable[TypeRewriter])

  Accepts a list of rewriter instances and applies each in order. Useful for
  composing rewriters, since the
  :class:`~monkeytype.config.Config.type_rewriter` config method only allows
  returning a single rewriter.

.. class:: NoOpRewriter()

  Does nothing. The default type rewriter in the base
  :class:`~monkeytype.config.Config`.
