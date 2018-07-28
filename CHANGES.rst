Changelog
=========

master
------

* Enable ``python -m monkeytype {run,stub,apply} ...``. Merge of #100, fixes
  #99. Thanks retornam.


18.5.1
------

* Add ``MONKEYTYPE_TRACE_MODULES`` env var for easier tracing of code in
  site-packages. Merge of #83, fixes #82. Thanks Bo Peng.

* Fix passing additional arguments to scripts run via ``monkeytype run``. Merge
  of #85. Thanks Danny Qiu.

* Fix handling of spaces in filenames passed to retype. Merge of #79, fixes
  #77.

* Never render NoneType in stubs, substitute None.  Merge of #75, fixes #5.
  Thanks John Arnold.


18.2.0
------

* Move filtering of `__main__` module into CallTraceStoreLogger instead of core
  tracing code, so it can be overridden by special use cases like IPython
  tracing. Merge of #72, fixes #68. Thanks Tony Fast.

* Generate stubs for modules where the module file is like module/__init__.py.
  Print retype stdout/stderr. Merge of #69, Fixes #66.
  Thanks John Arnold.


18.1.13
-------

* Improve error messages in case of "no traces found" and/or file path given
  instead of module name. Merge of #37, partial fix for #65. Thanks Aarni
  Koskela.

* Add ``monkeytype list_modules`` sub-command to list all modules present in
  trace db. Merge of #61, fixes #60. Thanks Alex Miasoiedov.

* Add ``--diff`` option to ``monkeytype stub``. Merge of #59, fixes #58.
  Thanks Tai-Lin!

* Add ``--ignore-existing-annotations`` option to ``monkeytype stub``. Merge of
  #55, fixes #15. Thanks Tai-Lin!


18.1.11
-------

* Fix crash in RewriteEmptyContainers rewriter if a parameter has only empty
  container types in traces (and more than one). Fixes #53.


18.1.10
-------

* Display retype errors when stub application fails. Merge of #52, fixes #49.

* Add ``--sample-count`` option to show the number of traces a given stub is
  based on. Merge of #50, fixes #7. Thanks Tai-Lin.

* Add ``monkeytype run -m`` for running a module as a script. Merge of
  #41. Thanks Simon Gomizelj.

* Add support for Django's ``cached_property`` decorator. Merge of #46, fixes
  #9. Thanks Christopher J Wang.

* Catch and log serialization exceptions instead of crashing. Fixes #38, merge
  of #39.

* Fix bug in default code filter when Python lib paths are symlinked. Merge of
  #40. Thanks Simon Gomizelj.

17.12.3
-------

* Rewrite imports from _io module to io. (#1, merge of #32). Thanks Radhans
  Jadhao.

* Add Config.cli_context() as a hook for custom CLI initialization and cleanup
  logic (#28; merge of #29). Thanks Rodney Folz.

17.12.2
-------

* Exclude "frozen importlib" functions in default code filter.

* Fix passing args to script run with ``monkeytype run`` (#18; merge of
  #21). Thanks Rodney Folz.

* Fix generated annotations for NewType types (#22; merge of #23). Thanks
  Rodney Folz.

17.12.1
-------

* Fix using MonkeyType outside a virtualenv (#16). Thanks Guido van Rossum for
  the report.

17.12.0
-------

* Initial public version.
