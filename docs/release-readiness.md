# Publication Audit Archive: Windows GPU and Paper Workflows

This is historical evidence for a completed commit/push, not a pending release checklist.
See [current status](current-status.md) for the baseline and [DEVELOPMENT](../DEVELOPMENT.md)
for future change discipline.

## Final outcome

On 2026-09-02, commit `c331715b049ec5f6a8546eff448d105b563e66ea` was pushed to
`https://github.com/HMRay1202/econ-research.git` on `main` and the remote SHA matched the local
commit. The worktree was clean then. Package version remained `0.1.0`; no tag or GitHub Release
was created.

## Preparation and publication sequence

1. Preparation began with local and remote baseline `58f8f1d5df0c99b2acde1e31d89063547441c33d`.
2. Scope was 26 tracked modifications and 15 new files, 41 files in total.
3. After authorization, the server was stopped. Its dedicated CMD window started another project
   server after the first stop; the verified launcher and server were then stopped and port
   release confirmed before committing.
4. The staged content was checked and committed. A separate user request authorized an ordinary
   push; no force push was used.

These are past observations, not current process state. Changing an executing CMD file can affect
subsequent execution, so stop before updating code/launchers. The observation above is not proof
of a general automatic-restart mechanism.

## Checks recorded at the time

| Check | Result and boundary |
| --- | --- |
| Ruff / offline tests | Passed; 107 tests and one dependency deprecation warning |
| Staged scope | 41 files including setup/stop scripts, worker modules, tests and docs |
| Patch formatting | `git diff --cached --check` passed |
| Sensitive content | Heuristic scan found no credentials, runtime data, models or files above 10 MiB; not an absolute guarantee |
| Ignore rules | Config, PDFs, databases, models, logs and Python caches were not committed |
| macOS launcher | Executable mode `100755` retained; Git attributes specify .command LF and .cmd CRLF |
| Data | No database deletion, model replacement or data-directory migration was used to complete the update |
| Remote | Full remote main SHA verified after push |

Added implementation files included four runtime scripts, two isolated Paddle modules,
`stop-research.cmd` and five test modules, alongside docs and line-ending attributes.
Use `git show --stat c331715` for the complete file list instead of copying it into several guides.

Test and GPU/import observations belong in [verification status](current-status.md).
Future publication must rerun checks; this audit does not certify later changes or remote state.
