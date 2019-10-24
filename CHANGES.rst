Changelog
=========

master
------

* Load config after argument parsing instead of during it, to avoid argparse
  catching TypeError/ValueError at import time of a custom config and replacing
  with a generic "invalid value" message. See
  https://bugs.python.org/issue30220. Thanks Daniel G Holmes for the report.
  Merge of #142, fixes #141.


19.5.0
------

* Mark ``monkeytype`` package as typed per PEP 561. Thanks Vasily Zakharov for 
  the report.
* Add ``-v`` option; don't display individual traces that fail to decode unless
  it is given.

19.1.1
------

* Pass ``--incremental`` to retype when applying stubs, so it doesn't choke on
  partial stubs (which can result from e.g. failures to decode some traces).

19.1.0
------

* Add ``--omit-existing-annotations`` option, implied by ``apply``. Merge of
  #129. Fixes #11 and #81.

* Render ``...`` for all parameter defaults in stubs. Remove the
  ``--include-unparsable-defaults`` and ``--exclude-unparsable-defaults`` CLI
  options, as well as the ``include_unparsable_defaults()`` config method.
  Merge of #128, fixes #123.

* Render forward references (from existing annotations) correctly. Merge of #127.

* Rewrite `Generator[..., None, None]` to `Iterator[None]` by default. Merge of
  #110, fixes #4. Thanks iyanuashiri.


18.8.0
------

* Support Python 3.7. Merge of #107, fixes #78.

* Print useful error message when filename is passed to stub/apply. Merge of
  #88, fixes #65. Thanks rajathagasthya.

* Fix crash in ``list_modules`` when there are no traces. Merge of #106, fixes
  #90.  Thanks tyrinwu.

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
