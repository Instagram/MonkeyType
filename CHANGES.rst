Changelog
=========

main
----

22.2.0
------

* Drop Python 3.6 support.

* Fix `AttributeError: __args__` when generating stubs on Python 3.9. Thanks
  GameDungeon and ntjess for the report. Fixes #231.

* Fix `AttributeError: '_SpecialForm' object has no attribute '__name__'` in
  collecting traces with Union types. Thanks Federico Caselli for the report.
  Fixes #243.


21.5.0
------

* Fix compatibility with Python 3.9. Thanks Felix Yan. Merge of #217, fixes
  #205.

* Render empty tuple type correctly. Thanks Pradeep Kumar Srinivasan. Merge of
  #191, fixes #190.


20.5.0
------

* Require ``libcst>=0.3.5``.

* Add ``--ignore-existing-annotations`` flag to ``apply`` command.


20.4.2
------

* Add missing ``libcst`` dependency in ``setup.py``.


20.4.1
------

* Generate stubs for TypedDicts nested within generic types. Disable
  TypedDicts completely when the max size is zero. Thanks Pradeep Kumar
  Srinivasan. Merge of #162, fixes #159.

* Remove ``stringcase`` dependency, just hand-roll ``pascal_case`` function.

* Shrink dictionary traces with required and optional keys to get non-total
  TypedDict class declarations. Thanks Pradeep Kumar Srinivasan.

* Implement ``monkeytype apply`` using libcst's ``ApplyTypeAnnotationsVisitor``.
  This correctly applies generated TypedDict classes. Thanks Pradeep Kumar
  Srinivasan.

* Render generic types recursively to handle nested special cases like
  ``List['Movie']``. Thanks Pradeep Kumar Srinivasan. Fixes #76.


19.11.2
-------

* Disable TypedDict generation by default for now, since it breaks `--apply`.


19.11.1
-------

* Add setup.py dependences for mypy-extensions and stringcase. Thanks Nicholas
  Bollweg for the report.


19.11.0
-------

* Trace per-key value types for dictionaries (up to a configured max size) and
  if the traced types are consistent, output a TypedDict in the stub instead of
  a homogenous dict. Thanks Pradeep Kumar Srinivasan. Merge of #143, fixes
  #105.

* Fix crash with empty tuples. Thanks akayunov for the report, Christophe
  Simonis for the simplest-case repro. Fixes #136.

* Don't add stringified annotations to type stubs. Thanks Łukasz Langa. Merge
  of #148.

* Don't crash in type rewriter on user-defined types that name-collide with
  container types from the `typing` module. Thanks Łukasz Langa. Merge of #146.

* Load config after argument parsing instead of during it, to avoid argparse
  catching TypeError/ValueError at import time of a custom config and replacing
  with a generic "invalid value" message. See
  https://bugs.python.org/issue30220. Thanks Daniel G Holmes for the report.
  Merge of #142, fixes #141.

* Typing support for collections.defaultdict. Thanks Dinesh Kesavan. Merge of #152.


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
