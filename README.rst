MonkeyType
==========

MonkeyType collects runtime types of function arguments and return values, and
can automatically generate stub files or even add draft type annotations
directly to your Python code based on the types collected at runtime.

Example
-------

Say ``some/module.py`` originally contains::

  def add(a, b):
      return a + b

And ``myscript.py`` contains::

  from some.module import add

  add(1, 2)

Now we want to infer the type annotation of ``add`` in ``some/module.py`` by
running ``myscript.py`` with ``MonkeyType``. One way is to run::

  $ monkeytype run myscript.py

By default, this will dump call traces into a SQLite database in the file
``monkeytype.sqlite3`` in the current working directory. You can then use the
``monkeytype`` command to generate a stub file for a module, or apply the type
annotations directly to your code.

Running ``monkeytype stub some.module`` will output a stub::

  def add(a: int, b: int) -> int: ...

Running  ``monkeytype apply some.module`` will modify ``some/module.py`` to::

  def add(a: int, b: int) -> int:
      return a + b

This example demonstrates both the value and the limitations of
MonkeyType. With MonkeyType, it's very easy to add annotations that
reflect the concrete types you use at runtime, but those annotations may not
always match the full intended capability of the functions. For instance, ``add``
is capable of handling many more types than just integers. Similarly, MonkeyType
may generate a concrete ``List`` annotation where an abstract ``Sequence`` or
``Iterable`` would be more appropriate. MonkeyType's annotations are an
informative first draft, to be checked and corrected by a developer.

Motivation
----------

Readability and static analysis are the primary motivations for adding type
annotations to code. It's already common in many Python style guides to
document the argument and return types for a function in its docstring;
annotations are a standardized way to provide this documentation, which also
permits static analysis by a typechecker such as `mypy`_.

For more on the motivation and design of Python type annotations, see
:pep:`483` and :pep:`484`.

.. _mypy: http://mypy.readthedocs.io/en/latest/

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
