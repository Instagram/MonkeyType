How to release MonkeyType
=========================

1. Update ``CHANGES.rst``: change "master" heading to a new version number. The
   version number should be in the form ``YY.M.X``, where ``YY`` is the last two
   digits of the current year, ``M`` is the current month (no leading zero, but
   might be two digits), and ``X`` just increments, starting at ``0`` for the first
   release in a month (can also be multiple digits if needed).
2. Update ``monkeytype/__init__.py``: change ``__version__`` to the same
   version as above.
3. Commit these changes with the commit message "Version YY.M.X" (replacing with
   the real version).
4. Tag this commit (signed tag): ``git tag -s vYY.M.X``. Tag message can also
   just be ``vYY.M.X``.
5. Build wheel and sdist packages: ``python setup.py sdist bdist_wheel``.
6. Upload the packages to PyPI:
   ``twine upload -s dist/MonkeyType-YY.M.X-py3-none-any.whl dist/MonkeyType-YY.M.X.tar.gz``
7. Add a new "master" heading to ``CHANGES.rst`` and bump the version number in
   ``monkeytype/__init__.py`` to the next micro version, with ``.dev1`` appended
   (e.g. after releasing ``18.5.1``, bump to ``18.5.2.dev1``). Commit this.
8. Push everything to GitHub: ``git push && git push --tags``.
