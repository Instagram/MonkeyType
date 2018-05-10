# Find bugs with type-checked Python and MonkeyType!

## Quickstart

1. Run the tests:
   ```
   $ pytest
   ```
2. Try type-checking the code (no output means it checked clean):
   ```
   $ mypy .
   ```
3. Use MonkeyType to complete the type annotations:
   ```
   $ monkeytype run `which pytest`
   $ monkeytype apply inbox
   ```
4. Type-check again; bugs are revealed!
   ```
   mypy .
   ```

## Narrative

The file `inbox.py` in this directory has some code implementing aggregation of
notifications in a hypothetical inbox system.

The code looks like it's in pretty good shape; it has thorough tests (in
`test_inbox.py`) that cover every possible code path. You can run the tests with
`pytest` and see them pass. But there are a few latent bugs hiding in there!

You might be able to find the bugs by reading the code; take a few minutes to
try! If you get tired of searching, come back and we'll take advantage of
MonkeyType to find them quickly.

The code is partially type annotated; you can type-check it with `mypy .`. It
won't show any type errors. But many of the functions in `inbox.py` aren't
type-annotated yet, so they aren't being type-checked.

You could annotate them all by hand. Feel free to try; you'll need to trace
through the code to understand what's being passed in at the call-sites for each
function. That's slow and tiresome. Instead, let's use
[MonkeyType](https://github.com/Instagram/MonkeyType) to annotate the entire
file quickly!

Run the test suite under MonkeyType tracing to collect a bunch of data about
types:

```
$ monkeytype run `which pytest`
```

This populates the SQLite database file `monkeytype.sqlite3` with traces of
function calls and their types. (If you change the code and want to start fresh
collecting traces, you can just delete that file.)

Now let's see the type information we collected:

```
$ monkeytype stub inbox
```

And let's go ahead and apply the type annotations directly to the code:

```
$ monkeytype apply inbox
```

We can run `pytest` again to verify we didn't break anything; the tests still
pass.

But run `mypy .` again; this time we see some type errors! The type-checker
found our bugs; can you fix them?

Feel free to play around with changing the code and re-running MonkeyType to see
how its generated annotations reflect the actual runtime types.
