# E-filing metadata regression checks (issue #305)

Run the isolated tests from the repository root:

```sh
python -m pytest tests/test_efiling_metadata.py -q
```

These execute the actual YAML code blocks, including both generic label paths,
classification, prediction, payment validation, submission gating, and refresh.
One test reproduces the original `NoneType.get` error with the original expression.

After installing this branch on **apps-dev.suffolklitlab.org**, run:

```sh
python tests/staging/run_probe.py
```

The staging probe requires requests, PyYAML, BeautifulSoup, and the apps-dev entry
in `~/.docassemblecli`. It uploads dedicated `issue305_*` Playground fixtures and
uses synthetic case metadata. It never submits a filing or changes server
configuration. It deletes its API sessions when finished; the Playground files
and anonymous browser smoke-test session remain for inspection.

The probe extracts the current production YAML blocks. It checks null responses,
retry recovery, court changes, stale successful labels, multiple search results,
selection, and browser submission of the manual-completion option. Browser form
submission is necessary because docassemble's variables API does not execute
question validation code.

## Verification on September 28, 2026

- 70 local pytest checks passed.
- All staging probe scenarios above passed.
- The companion EFSPIntegration branch's three court-info tests passed on the
  server under Python 3.12.3 (including parameterized subtests for null/malformed
  successful responses, failed responses, and valid court metadata).
- The complete petition interview opened successfully on apps-dev.
- The apps-dev configuration has a populated Massachusetts waiver ID. Live test
  court code lookups succeeded; no original production session was replayed.

The companion checkout is `/tmp/docassemble-EFSPIntegration-305`, branch
`fix/305-case-type-metadata`. It hardens `get_full_court_info()` and the non-indexed
case consumer. Both packages were deployed only to apps-dev.

The case-type endpoint is correct: its successful response contains both links
and metadata. There is no endpoint change. This fix does not address
MotionToStayEviction #129, which involves blank party names before fee calculation.

Labels are refreshed once per request and resolved lazily, using the found case's
court. A resolution makes one case-type request and one category request. This
avoids keeping failed or stale labels across navigation and saved-session resume,
but adds metadata requests compared with the previous indefinitely cached labels.
