# Open work

Standing backlog. Edit line by line, never rewrite wholesale. When an item is finished, delete
its line; the reason it closed belongs in the commit message, CHANGELOG or git history.

- [ ] (2026-10-05) [20] FOUND: the e2e tests (`tests/test_e2e_analysis.py`, `_run_and_save_analysis`) run under `make test` (marked `e2e`/`network`, not `integration`) and rewrite 48 TRACKED snapshots under `tests/e2e_outputs/` from live PyPI/GitHub data on every run, so each gate leaves a dirty tree and `make push` would commit ~30k lines of API drift | size: decide whether the outputs are fixtures (write to tmp_path, compare) or artifacts (gitignore them), plus whether e2e belongs in the integration lane | open: found while releasing the python -m fix 2026-10-05; worked around by restoring the snapshots from HEAD before the push | next: read what consumes tests/e2e_outputs, then pick fixture vs artifact
