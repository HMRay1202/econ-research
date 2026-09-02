# Runtime Guide

Start with the [README](../README.md) for first use. This page owns daily operation,
configuration and troubleshooting; see [data storage](data-storage.md) for files/backups and
[architecture](../ARCHITECTURE.md) for implementation boundaries.

## Requirements

- Run from the current repository root using Conda environment `econ-research` and Python 3.11.
- Install Conda first; launchers can create a missing application environment after confirmation.
- Keep the default loopback address `127.0.0.1:8000`. The app has no multi-user authentication.
- Use one application instance per database. Maintenance CLI commands also construct the service
  and run startup recovery, so avoid them against an active backend's database.

## Configuration and network costs

Create `.env` as described in the README without overwriting existing configuration.
Process environment variables take precedence over `.env`. Restart after changes.

| Setting | Default or purpose |
| --- | --- |
| `OPENAI_API_KEY` | Local credential needed for card generation and deep reads |
| `OPENAI_CARD_MODEL` | `gpt-5.6-luna` |
| `OPENAI_CARD_REASONING_EFFORT` | `low` |
| `OPENAI_DEEP_READ_MODEL` | `gpt-5.6-terra` |
| `OPENAI_DEEP_READ_REASONING_EFFORT` | `medium` |
| `OPENAI_DEFAULT_MODEL` | `gpt-5.6-terra` when an operation model is blank; legacy `OPENAI_MODEL` is accepted |
| `ECON_RESEARCH_PADDLE_FORMULA_OCR` | `true`; set `false` to disable Paddle formula recognition |
| `ECON_RESEARCH_FORMULA_ENRICHMENT` | `false`; experimental CodeFormula path, not the default |
| `ECON_RESEARCH_DATA_DIR` / `ECON_RESEARCH_DB_PATH` | `./data` / `./data/research.db`; independent settings, see data storage |

Model names are application defaults, not guarantees of availability or pricing for every account.

| Action | Network and cost boundary |
| --- | --- |
| Install libraries or prepare missing models | Downloads may be required; no LLM call merely for installation |
| Parse/reparse, formula OCR, search, read saved content | Local computation; missing models may still download |
| Initial import | Attempts card generation after local parsing and may call the LLM |
| Regenerate cards or request a deep read | Calls the configured OpenAI API and may incur charges |
| GET saved history, usage or files | Does not start another LLM call |

Requests include paper titles, source chunks, provenance and instructions; a deep read adds the
user's focus. Exclusion from GitHub does not mean source text never leaves the machine. The API
key stays in the backend, not browser code.

Use the UI usage panel. With the backend stopped, the CLI equivalent is:

~~~text
conda run -n econ-research research usage --details
~~~

Costs use recorded price snapshots and are estimates, not invoices; unknown pricing stays unpriced.
Reparse does not update existing card prose; explicitly regenerate only after reviewing the new source.

## Start, stop and update

Use `start-research.cmd` on Windows or `start-research.command` on macOS. Launchers locate the
environment, verify the editable package points to this checkout, and check runtime libraries.
Installing missing dependencies requires confirmation.

| Action | Windows | macOS |
| --- | --- | --- |
| Prepare/check without starting a new server | `start-research.cmd --setup-only` | `./start-research.command --setup-only` |
| Do not open a browser | `--no-open` | `--no-open` |
| Skip formula library installation | `--without-formula` | `--without-formula` |
| Stop the foreground service | Ctrl+C in its terminal | Ctrl+C in its terminal |

`--without-formula` neither uninstalls existing libraries nor disables existing OCR configuration.
`--with-formula` is a compatibility alias: formula libraries are already the default.
The macOS launcher returns early when a compatible server is running; stop it first for a fresh setup check.

When Windows finds an existing server:

- R confirms termination of the old server and starts it in the current window.
- S stops the existing server.
- L opens read-only logs; Ctrl+C closes only that viewer.
- Q exits the launcher and leaves the server running.

The fallback `stop-research.cmd`, or `start-research.cmd --stop`, checks environment/port ownership
and active uploads, then requires STOP confirmation. It terminates rather than gracefully shuts
down the process and cannot guarantee worker cleanup. Finish reparse/card/deep-read requests too;
prefer Ctrl+C in the original server window. Old redirected log files may not show current output.

Before updating code or launchers, finish tasks and stop the service. Do not edit an executing CMD
file or change its line endings. Preserve data/configuration, update the checkout, then run launcher
checks. The UI version marker is not a Git SHA; restart to load changed code.

## GPU and library installation

Prefer the launcher, or run this with the service stopped:

~~~text
conda run --no-capture-output -n econ-research python scripts/setup_runtime.py --install
~~~

Omit `--install` for a model-free library/device check. It does not download model weights.
Hardware policy inspects the default NVIDIA device, driver and compute capability, not merely
whether a CUDA toolkit is installed.

| Host | Current selection policy |
| --- | --- |
| Windows x64, driver ≥ 580.0, capability ≥ 7.5 and < 13 | Torch CUDA 13 in the main environment; isolated Paddle GPU CUDA 13 |
| Windows x64 not selected above, driver ≥ 560.76, capability ≥ 7.5 and < 10 | Torch/Paddle CUDA 12.6, with Paddle isolated |
| Windows without supported/detected GPU and driver | CPU path with a fallback reason |
| macOS | Native Torch, MPS when available; CPU Paddle, no CUDA worker |

This is a selection policy, not a guarantee that every target was tested. See [verification status](current-status.md).

Windows GPU Paddle lives in `<econ-research>/paddle-worker` without Torch. Separate processes load
their own CUDA/cuDNN libraries, avoiding the encountered Windows DLL conflict without patching DLLs.
A worker reuses its model within one document, has a 300-second request timeout, and closes after
parsing. `ECON_RESEARCH_PADDLE_PYTHON` can explicitly select its interpreter for advanced maintenance.

Do not install the legacy `.[formula-gpu]` extra in the main Windows environment or combine CPU/GPU
Paddle. The managed installer refuses a legacy main-environment GPU Paddle installation; stop the
service and inspect the environment before repairing it. Successful downloads alone do not prove
CUDA works. Normal setup does not require editing third-party DLLs.

## Troubleshooting

| Symptom | Check and interpretation |
| --- | --- |
| First run is slow | Follow the actual server output and task stage; library installation and model downloads are separate |
| GPU usage is near zero | Check whether parsing/OCR is active; queuing, network generation or a completed task can legitimately show low load |
| `formula_status=partial` | Some formulas fell back; review the PDF before deciding to reparse |
| Card generation failed | Inspect the credential, error and usage; retained parsed content can support a separate retry |
| Purge returns 409 | Record remains, but some files may already be removed; release file locks and allow synchronization, then retry |
| Restart shows interrupted work | Old jobs are not automatically replayed; review the prior outcome before re-uploading |
| Updated app still looks old | Stop the old process, restart from this checkout and refresh the browser |
| Logs do not advance | Read the foreground console; old `server-windows.*.log` files may be inactive |

Detailed states are in [workflows](workflows.md). Distinguish ordinary warnings, partial OCR
fallbacks and process failures rather than treating every diagnostic as a server crash.
