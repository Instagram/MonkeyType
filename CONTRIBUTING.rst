Contributing to MonkeyType
==========================

We want to make contributing to this project as easy and transparent as
possible.

Development
-----------

MonkeyType development happens via GitHub issues and pull requests.

Pull Requests
-------------

We welcome your pull requests.

1. Fork the repo and create your branch from `master`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation and ensure it builds
   (``cd doc && pipenv run make html``).
4. Ensure the test suite passes (``pipenv run pytest``).
5. Make sure your code lints (``pipenv run flake8``) and typechecks
   (``pipenv run mypy monkeytype``).
6. If your change is a user-visible feature or bugfix, add an entry to
   ``CHANGES.rst`` (see format of previous entries). Yes, you should add a
   thanks to yourself :)
7. If you haven't already, complete the Contributor License Agreement ("CLA").

Contributor License Agreement ("CLA")
-------------------------------------

In order to accept your pull request, we need you to submit a CLA. You only need
to do this once to work on any of Facebook's open source projects.

Complete your CLA at https://code.facebook.com/cla

Issues
------

We use GitHub issues to track public bugs. Please ensure your description is
clear and has sufficient instructions to be able to reproduce the issue.

Facebook has a `bounty program`_ for the safe disclosure of security bugs. In
those cases, please go through the process outlined on that page and do not file
a public issue.

.. _bounty program: https://www.facebook.com/whitehat/

Local Dev Environment
---------------------

To set up your local development environment, you will need `pipenv`_. You can
install it with ``pip install --user pipenv``. After this, you should be able to
run ``pipenv --help`` and get help output. If ``pipenv`` isn't found, you will
need to add ``$HOME/.local/bin`` to your shell ``PATH``.

Once you have ``pipenv``, run ``pipenv update -d`` to create a virtual
environment and install all packages needed for MonkeyType development into it.

Then you can run ``pipenv run pytest`` to run the tests, ``pipenv run flake8``
to lint, and ``pipenv run mypy monkeytype`` to typecheck. All three must pass
cleanly before your pull request can be merged.

You can also activate a pipenv shell with ``pipenv shell``, then just run
``pytest``, ``flake8``, and ``mypy monkeytype``.

.. _pipenv: https://docs.pipenv.org/

Coding Style
------------

* 4 spaces for indentation
* 80 character line length
* Flake8 default settings

License
-------

By contributing to MonkeyType, you agree that your contributions will be
licensed under the LICENSE file in the root directory of this source tree.
