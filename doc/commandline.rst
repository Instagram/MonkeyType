.. program:: monkeytype

Using MonkeyType from the command-line
--------------------------------------

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
syntax, it will apply them directly to the code file as Python 3.6+ style type
annotations, modifying the file in-place.

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

  Default: ``monkeytype.config:DEFAULT_CONFIG``

.. option:: -l <limit>, --limit <limit>

  The maximum number of call traces to query from your call trace store.
  Increasing this number may give more accurate results, at the cost of longer
  runtime.

  Default: 2000

.. option:: --disable-type-rewriting

  Don't apply your configured :doc:`rewriters` to the output types.

.. option:: --include-unparsable-defaults

  In order to introspect function arguments and existing annotations and apply
  new annotations, MonkeyType imports your code and inspects function signatures
  via the ``inspect`` standard library module, and then turns this introspected
  signature back into a code string when generating a stub.

  Some function arguments may have complex default values whose ```repr()`` is
  not a valid Python expression. These cannot round-trip successfully through
  the introspection process, since importing your code does not give MonkeyType
  access to the original expression for the default value, as a string of Python
  code.

  By default MonkeyType will simply exclude such functions from stub file
  output, in order to ensure a valid stub file. Provide this option to instead
  include these functions, invalid syntax and all; you'll have to manually fix
  them up before the stub file will be usable.
