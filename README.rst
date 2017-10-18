MonkeyType
==========

MonkeyType collects runtime types of function arguments and return values, and
can automatically generate stub files or even add draft type annotations
directly to your Python code based on the types collected at runtime.

Examples
--------

Enable call-trace logging for a block of code::

  import monkeytype

  with monkeytype.trace_calls():
      ...

By default this will dump call traces into a sqlite database in the file
``monkeytype.sqlite`` in the current working directory. You can then use the
``monkeytype`` command to generate a stub file or apply the type annotations
directly to your code::

  $ monkeytype stub some.module
  $ monkeytype apply some.module

See the documentation for details and more options.

Requirements
------------

MonkeyType requires Python 3.6+ and the `retype`_ library (for applying
type stubs to code files).

Installing
----------

Install MonkeyType with `pip`_::

  pip install MonkeyType

How MonkeyType works
--------------------

MonkeyType uses the `sys.setprofile`_ hook provided by Python to interpose on
function calls, function returns, and generator yields, and record the types of
arguments / return values / yield values.

It generates stub files based on that data, and can use retype to apply those
stub files directly to your code.

Caveats
-------

MonkeyType uses the same `sys.setprofile`_ hook that `coverage.py`_ uses to
measure Python code coverage, so you can't use MonkeyType and coverage
measurement together. If you want to run your tests under MonkeyType tracing,
disable coverage measurement, and vice versa.

.. _coverage.py: https://coverage.readthedocs.io/
.. _pip: https://pip.pypa.io/en/stable/
.. _retype: https://pypi.python.org/pypi/retype
.. _sys.setprofile: https://docs.python.org/3/library/sys.html#sys.setprofile
