MonkeyType
==========

MonkeyType collects runtime types of function arguments and return values, and
can automatically generate stub files or even add draft type annotations
directly to your Python code based on the types collected at runtime.

Examples
--------

In the example, we have two files: ``some/module.py`` and ``myscript.py``.

Say ``some/module.py`` originally contained::

  def add(a, b):
      return a + b

And ``myscript.py`` contains::

  from some.module import add

  add(1, 2)

Now we want to infer the type annotation of ``add`` in ``some/module.py`` by
running ``myscript.py`` with ``MonkeyType``. This is supported in two ways:

Run a script under call-trace logging of functions and methods in all imported
modules::

  $ monkeytype run myscript.py

Or enable call-trace logging for a block of code in ``myscript.py``::

  import monkeytype

  with monkeytype.trace():
      ...

By default this will dump call traces into a sqlite database in the file
``monkeytype.sqlite3`` in the current working directory. You can then use the
``monkeytype`` command to generate a stub file for a module, or apply the type
annotations directly to your code::

  $ monkeytype stub some.module
  $ monkeytype apply some.module

Then you'd get a stub like this from ``monkeytype stub some.module``::

  def add(a: int, b: int) -> int: ...

And if you run ``monkeytype apply some.module``, ``some/module.py`` will be
modified to::

  def add(a: int, b: int) -> int:
      return a + b

This example demonstrates both the value and the limitations of
MonkeyType. With MonkeyType, it's very easy to add type annotations that
reflect the concrete types you use at runtime, but those annotations may not
always match the full intended capability of the functions (e.g. this ``add``
function is capable of handling many more types than just integers, or
MonkeyType may generate a ``List`` annotation where ``Sequence`` or
``Iterable`` would be more appropriate). MonkeyType's annotations are intended
as a first draft, to be checked and corrected by a developer.

Requirements
------------

MonkeyType requires Python 3.6+ and the `retype`_ library (for applying type
stubs to code files). It generates only Python 3 type annotations (no type
comments).

Installing
----------

Install MonkeyType with `pip`_::

  pip install MonkeyType

How MonkeyType works
--------------------

MonkeyType uses the `sys.setprofile`_ hook provided by Python to interpose on
function calls, function returns, and generator yields, and record the types of
arguments / return values / yield values.

It generates `stub files`_ based on that data, and can use `retype`_ to apply those
stub files directly to your code.

.. _pip: https://pip.pypa.io/en/stable/
.. _retype: https://pypi.python.org/pypi/retype
.. _sys.setprofile: https://docs.python.org/3/library/sys.html#sys.setprofile
.. _stub files: http://mypy.readthedocs.io/en/latest/basics.html#library-stubs-and-the-typeshed-repo

.. end-here

See `the full documentation`_ for details.

.. _the full documentation: http://monkeytype.readthedocs.io/en/latest/

Troubleshooting
---------------

Check if your issue is mentioned in `the frequently asked questions`_ list.

.. _the frequently asked questions: http://monkeytype.readthedocs.io/en/stable/faq.html

LICENSE
-------

MonkeyType is BSD licensed.
