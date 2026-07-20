# Ammeter Testing Framework

A testing framework for current measurement systems using three ammeter emulators: Greenlee, ENTES, and CIRCUTOR. Each emulator runs as a TCP socket server on a separate thread and simulates a different physical measurement method.

## Project Structure

```
.
├── main.py                          # Entry point — starts emulators and runs all tests
├── config/
│   └── config.yaml                  # Sampling, ammeter, and analysis configuration
├── Ammeters/
│   ├── base_ammeter.py              # Abstract base class for all emulators
│   ├── Greenlee_Ammeter.py          # Ohm's Law emulator (I = V / R)
│   ├── Entes_Ammeter.py             # Hall Effect emulator (I = B * K)
│   ├── Circutor_Ammeter.py          # Rogowski Coil emulator (I = integral of V dt)
│   └── client.py                    # Socket client used by the framework
├── src/
│   └── testing/
│       ├── test_framework.py        # AmmeterTestFramework — core testing class
│       └── error_simulation.py      # ErrorSimulator — failure scenario test suite
└── results/                         # Auto-created — stores JSON results and PNG plots
```

## Setup

Install dependencies:
```sh
pip install -r requirements.txt
```

Libraries used: `matplotlib`, `numpy`, `pyyaml`. (`seaborn`, `scipy`, `pandas` are listed in requirements but not required by the framework itself — seaborn was removed in favour of a pure numpy/matplotlib KDE implementation to minimise dependencies.)

## Running

```sh
python main.py
```

This will:
1. Start the three ammeter emulators in background threads
2. Wait 5 seconds for the servers to be ready
3. Run a test for each ammeter using the settings in `config/config.yaml`
4. Print a per-run summary (mean, median, std dev, min, max) to the console
5. Save a JSON result and PNG plot (if visualization is enabled) to `results/`
6. Print a full list of all historical results
7. Print a side-by-side comparison of the three ammeters from this run
8. Run an accuracy assessment ranking ammeters by measurement precision
9. Run the error simulation suite to verify all failure modes are handled gracefully

## Configuration

All settings live in `config/config.yaml`:

```yaml
testing:
  sampling:
    measurements_count: 10        # Number of samples per test
    total_duration_seconds: 10    # Alternative to count — derives count from duration * frequency
    sampling_frequency_hz: 1.0    # How often to sample (samples per second)

ammeters:
  greenlee:
    port: 5001
    command: "MEASURE_GREENLEE -get_measurement"
  entes:
    port: 5002
    command: "MEASURE_ENTES -get_data"
  circutor:
    port: 5003
    command: "MEASURE_CIRCUTOR -get_measurement -current"

analysis:
  visualization:
    enabled: true   # Set to false to skip PNG plot generation
```

## Using the Framework Programmatically

```python
from src.testing.test_framework import AmmeterTestFramework

framework = AmmeterTestFramework()

# Run with config defaults
result = framework.run_test("greenlee")

# Override sampling parameters per call
result = framework.run_test("entes", measurements_count=20)
result = framework.run_test("circutor", total_duration_seconds=30, sampling_frequency_hz=2.0)

# List all saved results (optionally filter by ammeter type)
framework.list_results()
framework.list_results("greenlee")

# Load a specific result by its short ID (first 4 chars of the filename)
result = framework.load_result("6595")

# Compare multiple runs side by side
framework.compare_results(["6595", "0d9c", "6e67"])

# Rank ammeters by precision using the most recent result per type
framework.accuracy_assessment()

# Or pass specific run IDs to compare
framework.accuracy_assessment(["6595", "0d9c", "6e67"])
```

## Error Simulation

The `ErrorSimulator` runs 8 failure scenarios to verify every error path in the framework is handled gracefully and never crashes the program:

| # | Scenario | What it tests |
|---|----------|---------------|
| 1 | Connection refused | Server not running — `ConnectionRefusedError` caught per sample |
| 2 | Timeout | Server accepts but never replies — socket timeout caught per sample |
| 3 | Garbled data | Server sends non-numeric response — `ValueError` caught per sample |
| 4 | Empty response | Server closes connection without sending data — empty recv handled |
| 5 | Framework resilience | All samples fail — framework logs errors and exits cleanly without archiving |
| 6 | Disk write error | Results directory does not exist — `OSError` caught in `_archive_result` |
| 7 | Corrupted JSON file | Invalid JSON in results folder — file skipped with warning in `list_results` |
| 8 | Zero std dev visualization | All samples identical (std_dev=0) — KDE bandwidth fallback prevents division by zero |

Run separately with:
```python
from src.testing.error_simulation import ErrorSimulator

ErrorSimulator().run_all()
```

## Result Files

Each test run produces a JSON file in `results/` named:
```
{ammeter_type}_{YYYYMMDD}_{HHMMSS}_{short_id}.json
```
Example: `greenlee_20260720_124916_6595.json`

The JSON contains the run ID, timestamps, sampling config, raw samples (rounded to 3 decimal places), and statistics (mean, median, standard deviation, min, max).

If visualization is enabled, a matching PNG file is saved alongside the JSON.

## Ammeter Emulators

| Ammeter  | Port | Measurement Method        | Formula            |
|----------|------|---------------------------|--------------------|
| Greenlee | 5001 | Ohm's Law                 | I = V / R          |
| ENTES    | 5002 | Hall Effect               | I = B * K          |
| CIRCUTOR | 5003 | Rogowski Coil Integration | I = integral(V dt) |

## Bugs Fixed

| Bug | File | Fix |
|-----|------|-----|
| Wrong ports in client calls | `main.py` | Client now connects to 5001/5002/5003, matching where servers bind |
| Wrong/truncated commands | `main.py` | Commands updated to match exact byte strings each emulator expects |
| `client.py` returned a string | `Ammeters/client.py` | Now parses and returns a `float` |
| `Ω` symbol crashed on Windows terminal | `Ammeters/Greenlee_Ammeter.py` | Replaced with `Ohm` |
| Unicode arrow crashed on Windows terminal | `src/testing/test_framework.py` | Replaced `→` with `->` |
| Emulator server crashed on measurement error | `Ammeters/base_ammeter.py` | Added try/except so the server keeps running after a single failure |
| No `__init__.py` files in `src/` | `src/`, `src/testing/`, `src/utils/` | Created empty `__init__.py` to enable relative imports |

## Design Decisions

### Architecture
The framework is built around a single class (`AmmeterTestFramework`) that owns the full lifecycle of a test run: configuration loading, sampling, statistics, archiving, and visualisation. This keeps all logic in one place and makes the framework easy to extend — adding a new ammeter type requires only a new entry in `config.yaml`, no code changes.

### Configuration-first with per-call overrides
Sampling parameters (`measurements_count`, `total_duration_seconds`, `sampling_frequency_hz`) are read from `config.yaml` by default but can be overridden on any individual `run_test()` call. This makes the framework suitable for both automated scripted runs (driven entirely by config) and interactive exploration (override per call without touching the file).

### Unique run identification
Each test run gets a full UUID4 stored in the JSON result. The first 4 characters are embedded in the filename for human readability. This ensures results are never overwritten and can be referenced by short ID in `load_result()` and `compare_results()`.

### Precision vs. display rounding
`run_test()` returns the full-precision float values in memory (useful if the caller does further computation), while the JSON archive rounds to 3 decimal places for readability. These are kept separate so the two concerns don't interfere.

### Precise sampling interval
Each sample records its start time before the network call. After the call, the elapsed time is subtracted from the target interval before sleeping, so the next sample starts at the correct wall-clock time regardless of how long the previous measurement took. This ensures the configured frequency is honoured even when network latency varies.

### Per-sample error handling, not per-test
Errors are caught at the individual sample level, not at the test level. If one sample fails (connection drop, timeout, bad data), the framework logs a warning and continues collecting the rest. Only if every sample fails does the test abort. This mirrors how real measurement systems behave — a single dropout should not invalidate an entire session.

### Socket timeout
The client sets a 5-second socket timeout so a hung or unresponsive server does not block the test indefinitely. Without this, a dead server would cause `recv()` to block forever.

### Accuracy assessment via coefficient of variation
Because the three ammeters operate on completely different current scales (Greenlee ~0.1 A, ENTES ~70 A, CIRCUTOR ~0.04 A), their raw standard deviations cannot be directly compared. The accuracy assessment normalises by dividing std_dev by mean (coefficient of variation), giving a scale-independent measure of precision. The ammeter with the lowest CV is ranked most reliable.

### Error simulation as a separate class
Error simulation is implemented as `ErrorSimulator`, separate from `AmmeterTestFramework`. Each scenario spins up a deliberately broken server on a reserved port range (5010–5019) and verifies the framework handles the failure gracefully. Keeping this separate means it can be run independently and does not affect the real test results.
