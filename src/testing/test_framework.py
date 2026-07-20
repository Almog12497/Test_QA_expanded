import json
import statistics
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import matplotlib.pyplot as plt

from ..utils.config import load_config
from Ammeters.client import request_current_from_ammeter


class AmmeterTestFramework:
    def __init__(self, config_path: str = "config/config.yaml"):
        try:
            self.config = load_config(config_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Config file not found: '{config_path}'. "
                "Make sure config/config.yaml exists."
            )
        except Exception as e:
            raise ValueError(f"Failed to load config from '{config_path}': {e}")

        output_dir = self.config.get("result_management", {}).get("output_dir", "results")
        self.results_dir = Path(output_dir)
        self.results_dir.mkdir(exist_ok=True)

    def _ammeter_cfg(self, ammeter_type: str) -> Dict:
        ammeters = self.config.get("ammeters", {})
        cfg = ammeters.get(ammeter_type.lower())
        if cfg is None:
            raise ValueError(
                f"Unknown ammeter type: '{ammeter_type}'. "
                f"Available: {list(ammeters.keys())}"
            )
        return cfg

    def _collect_samples(self, ammeter_type: str, num_measurements: int,
                         frequency_hz: float) -> List[float]:
        cfg = self._ammeter_cfg(ammeter_type)
        port = cfg["port"]
        command = cfg["command"].encode("utf-8")
        interval = 1.0 / frequency_hz
        samples: List[float] = []
        failures = 0

        for i in range(num_measurements):
            sample_start = time.time()

            try:
                value = request_current_from_ammeter(port, command)
                if value is not None:
                    samples.append(value)
                else:
                    failures += 1
                    print(f"  [WARNING] Sample {i + 1}: no data received from {ammeter_type}")
            except ConnectionRefusedError:
                failures += 1
                print(f"  [ERROR] Sample {i + 1}: could not connect to {ammeter_type} "
                      f"on port {port} - is the server running?")
            except ValueError as e:
                failures += 1
                print(f"  [ERROR] Sample {i + 1}: invalid data from {ammeter_type}: {e}")
            except Exception as e:
                failures += 1
                print(f"  [ERROR] Sample {i + 1}: unexpected error from {ammeter_type}: {e}")

            if i < num_measurements - 1:
                elapsed = time.time() - sample_start
                sleep_time = max(0.0, interval - elapsed)
                time.sleep(sleep_time)

        if failures:
            print(f"  [SUMMARY] {len(samples)} of {num_measurements} samples collected "
                  f"({failures} failed) for {ammeter_type}")
        return samples

    def _compute_stats(self, samples: List[float]) -> Dict:
        if not samples:
            return {}
        mean = statistics.mean(samples)
        std_dev = statistics.stdev(samples) if len(samples) > 1 else 0.0

        return {
            "mean": mean,
            "median": statistics.median(samples),
            "std_dev": std_dev,
            "min": min(samples),
            "max": max(samples),
            "count": len(samples),
        }

    def run_test(self, ammeter_type: str,
                 measurements_count: int = None,
                 total_duration_seconds: float = None,
                 sampling_frequency_hz: float = None) -> Dict:
        sampling_cfg = self.config.get("testing", {}).get("sampling", {})
        frequency_hz = sampling_frequency_hz or sampling_cfg.get("sampling_frequency_hz", 1.0)

        if total_duration_seconds is not None:
            num_measurements = int(total_duration_seconds * frequency_hz)
        elif measurements_count is not None:
            num_measurements = measurements_count
        elif sampling_cfg.get("total_duration_seconds"):
            num_measurements = int(sampling_cfg["total_duration_seconds"] * frequency_hz)
        else:
            num_measurements = sampling_cfg.get("measurements_count", 10)

        run_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        print(f"\n[{ammeter_type}] Starting test - {num_measurements} samples "
              f"at {frequency_hz} Hz (run {run_id})")

        samples = self._collect_samples(ammeter_type, num_measurements, frequency_hz)
        stats = self._compute_stats(samples)

        result = {
            "run_id": run_id,
            "ammeter_type": ammeter_type,
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
            "config": {
                "measurements_count": num_measurements,
                "sampling_frequency_hz": frequency_hz,
            },
            "samples": samples,
            "statistics": stats,
        }

        if not samples:
            print(f"  [ERROR] No samples collected for {ammeter_type} - skipping archive and analysis.")
            return result

        self._archive_result(result)
        self._print_summary(result)

        if self.config.get("analysis", {}).get("visualization", {}).get("enabled", False):
            self._visualize(result)

        return result

    def _archive_result(self, result: Dict):
        started = datetime.fromisoformat(result["started_at"])
        filename = (
            f"{result['ammeter_type']}_"
            f"{started.strftime('%Y%m%d')}_{started.strftime('%H%M%S')}_"
            f"{result['run_id'][:4]}.json"
        )

        archived = result.copy()
        archived["samples"] = [round(v, 3) for v in result["samples"]]
        archived["statistics"] = {
            k: round(v, 3) if isinstance(v, float) else v
            for k, v in result["statistics"].items()
        }

        path = self.results_dir / filename
        try:
            with open(path, "w") as f:
                json.dump(archived, f, indent=2)
            print(f"  Result saved -> {path}")
        except OSError as e:
            print(f"  [ERROR] Could not save result to {path}: {e}")

    def _visualize(self, result: Dict):
        samples = result["samples"]
        stats = result["statistics"]
        ammeter_type = result["ammeter_type"]
        mean = stats["mean"]
        std_dev = stats["std_dev"]

        if len(samples) < 2:
            print(f"  [WARNING] Not enough samples to visualize "
                  f"({len(samples)} collected, need at least 2) - skipping plot.")
            return

        try:
            fig, (ax_line, ax_hist) = plt.subplots(1, 2, figsize=(12, 4))
            fig.suptitle(f"{ammeter_type.capitalize()} Ammeter")

            # Line plot: measurements over time
            ax_line.plot(range(1, len(samples) + 1), samples, marker="o", linewidth=1.5)
            ax_line.axhline(mean, color="red", linestyle="--", label=f"Mean ({mean:.3f} A)")
            ax_line.axhspan(mean - std_dev, mean + std_dev, alpha=0.15, color="red", label="+/-1 std")
            ax_line.set_xlabel("Sample #")
            ax_line.set_ylabel("Current (A)")
            ax_line.set_title("Measurements over time")
            ax_line.legend()

            # Histogram with KDE using numpy (no seaborn dependency)
            ax_hist.hist(samples, bins="auto", color="steelblue", edgecolor="white",
                         alpha=0.7, density=True)
            # Fallback bandwidth when std_dev=0 (all samples identical) to avoid division by zero
            if std_dev > 0:
                bandwidth = 1.06 * std_dev * len(samples) ** -0.2
            else:
                bandwidth = abs(mean) * 0.1 if mean != 0 else 0.1
            x_range = np.linspace(min(samples) - 3 * bandwidth, max(samples) + 3 * bandwidth, 300)
            kde_values = np.mean(
                np.exp(-0.5 * ((x_range[:, None] - np.array(samples)[None, :]) / bandwidth) ** 2),
                axis=1
            ) / (bandwidth * np.sqrt(2 * np.pi))
            ax_hist.plot(x_range, kde_values, color="navy", linewidth=2)
            ax_hist.axvline(mean, color="red", linestyle="--", label=f"Mean ({mean:.3f} A)")
            ax_hist.set_xlabel("Current (A)")
            ax_hist.set_title("Value distribution")
            ax_hist.legend()

            plt.tight_layout()

            started = datetime.fromisoformat(result["started_at"])
            plot_filename = (
                f"{ammeter_type}_"
                f"{started.strftime('%Y%m%d')}_{started.strftime('%H%M%S')}_"
                f"{result['run_id'][:4]}.png"
            )
            path = self.results_dir / plot_filename
            plt.savefig(path, dpi=150)
            plt.close()
            print(f"  Plot saved    -> {path}")
        except Exception as e:
            print(f"  [ERROR] Visualization failed: {e}")
            plt.close()

    def list_results(self, ammeter_type: str = None) -> List[Dict]:
        """Return metadata for all saved runs, optionally filtered by ammeter type."""
        results = []
        for path in sorted(self.results_dir.glob("*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  [WARNING] Skipping corrupted result file {path.name}: {e}")
                continue
            if ammeter_type is None or data.get("ammeter_type") == ammeter_type.lower():
                results.append({
                    "file": path.name,
                    "run_id": data["run_id"],
                    "ammeter_type": data["ammeter_type"],
                    "started_at": data["started_at"],
                    "count": data["statistics"].get("count"),
                    "mean": data["statistics"].get("mean"),
                })

        if not results:
            print("No results found.")
            return results

        print(f"\n{'File':<45} {'Type':<10} {'Started':<20} {'N':>4} {'Mean':>8}")
        print("-" * 90)
        for r in results:
            print(f"{r['file']:<45} {r['ammeter_type']:<10} {r['started_at'][:19]:<20} "
                  f"{r['count']:>4} {r['mean']:>8.3f}")
        return results

    def load_result(self, run_id_prefix: str) -> Dict:
        """Load a result by its short ID prefix (first 4 chars) or full run_id."""
        matches = [p for p in self.results_dir.glob("*.json")
                   if run_id_prefix in p.name]
        if not matches:
            raise FileNotFoundError(f"No result found matching '{run_id_prefix}'")
        if len(matches) > 1:
            raise ValueError(
                f"Multiple results match '{run_id_prefix}': "
                f"{[p.name for p in matches]}"
            )
        try:
            with open(matches[0]) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Could not read result file '{matches[0].name}': {e}")

    def compare_results(self, run_id_prefixes: List[str]):
        """Print a side-by-side stats comparison for the given run IDs."""
        results = [self.load_result(rid) for rid in run_id_prefixes]
        stats_keys = ["mean", "median", "std_dev", "min", "max"]

        col_width = 18
        header = f"{'Metric':<28}" + "".join(
            f"{r['ammeter_type']} ({r['run_id'][:4]})"[:col_width].ljust(col_width)
            for r in results
        )
        print(f"\n{header}")
        print("-" * (28 + col_width * len(results)))

        for key in stats_keys:
            label = key.replace("_", " ").capitalize()
            row = f"{label:<28}"
            for r in results:
                val = r["statistics"].get(key, "N/A")
                cell = f"{val:.3f}" if isinstance(val, float) else str(val)
                row += cell.ljust(col_width)
            print(row)

    def accuracy_assessment(self, run_id_prefixes: List[str] = None):
        """
        Compare precision across ammeter types and identify the most reliable one.
        If no run IDs are given, uses the most recent result for each ammeter type.
        Precision is measured by the coefficient of variation (std_dev / mean):
        a lower value means the ammeter produces more consistent readings.
        """
        if run_id_prefixes:
            results = [self.load_result(rid) for rid in run_id_prefixes]
        else:
            results = self._latest_per_ammeter()

        if not results:
            print("No results available for accuracy assessment.")
            return

        assessments = []
        for r in results:
            stats = r["statistics"]
            mean = stats.get("mean", 0)
            std_dev = stats.get("std_dev", 0)
            spread = stats.get("max", 0) - stats.get("min", 0)
            cv = (std_dev / mean) if mean != 0 else float("inf")
            assessments.append({
                "ammeter_type": r["ammeter_type"],
                "run_id": r["run_id"][:4],
                "mean": mean,
                "std_dev": std_dev,
                "spread": spread,
                "cv": cv,
            })

        assessments.sort(key=lambda x: x["cv"])

        print("\n=== Accuracy Assessment ===")
        print("Precision metric: coefficient of variation (std_dev / mean) - lower is better\n")

        col = 16
        header = (f"{'Rank':<6}{'Ammeter':<12}{'Run':<6}"
                  f"{'Mean':>{col}}{'Std Dev':>{col}}{'Spread':>{col}}{'CV (precision)':>{col}}")
        print(header)
        print("-" * (6 + 12 + 6 + col * 4))

        medals = {0: "1st", 1: "2nd", 2: "3rd"}
        for i, a in enumerate(assessments):
            rank = medals.get(i, f"{i + 1}th")
            print(f"{rank:<6}{a['ammeter_type']:<12}{a['run_id']:<6}"
                  f"{a['mean']:>{col}.3f}{a['std_dev']:>{col}.3f}"
                  f"{a['spread']:>{col}.3f}{a['cv']:>{col}.4f}")

        winner = assessments[0]
        print(f"\nMost reliable: {winner['ammeter_type'].upper()} "
              f"(CV={winner['cv']:.4f}, run {winner['run_id']})")

        return assessments

    def _latest_per_ammeter(self) -> List[Dict]:
        """Load the most recent saved result for each known ammeter type."""
        latest: Dict[str, dict] = {}
        for path in sorted(self.results_dir.glob("*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  [WARNING] Skipping corrupted result file {path.name}: {e}")
                continue
            ammeter_type = data.get("ammeter_type")
            if ammeter_type:
                latest[ammeter_type] = data
        return list(latest.values())

    def _print_summary(self, result: Dict):
        stats = result["statistics"]
        if not stats:
            print("  No samples collected.")
            return
        print(f"  mean={stats['mean']:.3f} A  median={stats['median']:.3f} A  "
              f"std={stats['std_dev']:.3f}  min={stats['min']:.3f}  max={stats['max']:.3f}")
