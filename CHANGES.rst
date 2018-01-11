Changelog
=========

master
------

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
