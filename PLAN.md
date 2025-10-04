# Work Plan

## Goals
- Expand automated coverage for the refactored audit runner and CLI enhancements.
- Update documentation to describe new CLI flags and profile layout changes.
- Validate and adjust profiles after the new directory reorganization.

## Steps
1. **Review Engine Changes**
   - Re-read `modules/audit_runner.py` to confirm expectations for extends, variable resolution, allowlist handling, fact caching, and new status values.
   - Identify critical code paths lacking tests (parallel execution, variable overrides, allowlist comparison, summary scoring, evidence snippets).

2. **Add Targeted Tests**
   - Extend `tests/test_audit_runner.py` with cases that exercise:
     - Variable substitution from CLI/environment levels.
     - Profile inheritance via `extends` including deep nesting and override precedence.
     - Allowlist comparison for SUID/ports rules.
     - Fact caching by asserting shell commands invoked once.
     - Parallel executor behaviour (bounded workers, timeout/UNDEF path where feasible).
   - Introduce CLI tests for `--level`, `--var`, and `--workers` parsing to ensure they feed the runner correctly.

3. **Profile Validation & Docs**
   - Run `secaudit validate` (or equivalent) against reorganized profiles; patch YAML if schema violations occur.
   - Update `README.md` and `docs/` to highlight new profiles layout, strictness levels, and CLI options.
   - Ensure `profiles/include/vars_*.env` contain the intended thresholds and mention them in `profiles/README.md` if needed.

4. **Reporting & Output**
   - Adjust report templates or add TODOs in docs if modifications are out of scope for this iteration.
   - Confirm JSON summary structure matches downstream expectations; document changes in README/CHANGELOG if necessary.

5. **Verification**
   - Execute `pytest` and representative `secaudit audit` commands to verify behaviour and capture sample outputs.
   - Prepare PR summary referencing new tests/docs.
