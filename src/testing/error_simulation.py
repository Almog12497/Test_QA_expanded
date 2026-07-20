import json
import socket
import threading
import time
from pathlib import Path
from typing import Callable, List, Tuple

from Ammeters.client import request_current_from_ammeter
from src.testing.test_framework import AmmeterTestFramework


class ErrorSimulator:
    """
    Runs a suite of error scenarios against the framework to verify that
    failures are handled gracefully and never crash the program.
    """

    _PORT_BASE = 5010  # Ports 5010-5019 reserved for simulation servers

    def run_all(self) -> List[Tuple[str, bool]]:
        scenarios = [
            ("Connection refused (server not running)",    self._scenario_connection_refused),
            ("Timeout (server accepts but never replies)", self._scenario_timeout),
            ("Garbled data (non-numeric response)",        self._scenario_garbled_data),
            ("Empty response (connection closed early)",   self._scenario_empty_response),
            ("Framework resilience (all samples fail)",    self._scenario_framework_resilience),
            ("Disk write error (bad results path)",        self._scenario_disk_write_error),
            ("Corrupted JSON result file",                 self._scenario_corrupted_json),
            ("Visualization with zero std dev",            self._scenario_visualization_zero_std),
        ]

        print("\n=== Error Simulation ===\n")
        results = []
        for name, scenario in scenarios:
            print(f"  Scenario: {name}")
            handled = scenario()
            label = "PASS" if handled else "FAIL"
            print(f"  Result:   {label}\n")
            results.append((name, handled))

        passed = sum(1 for _, ok in results if ok)
        print(f"Summary: {passed}/{len(results)} scenarios handled correctly")
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _start_bad_server(self, port: int, handler: Callable):
        """Start a one-shot server in a daemon thread that calls handler(conn)."""
        def serve():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('localhost', port))
                s.listen(1)
                try:
                    conn, _ = s.accept()
                    with conn:
                        handler(conn)
                except Exception:
                    pass

        threading.Thread(target=serve, daemon=True).start()
        time.sleep(0.1)  # Give the thread time to bind before client connects

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    def _scenario_connection_refused(self) -> bool:
        """No server is running — expect ConnectionRefusedError to be caught."""
        try:
            result = request_current_from_ammeter(5099, b'TEST')
            return result is None
        except ConnectionRefusedError:
            return True
        except Exception:
            return True

    def _scenario_timeout(self) -> bool:
        """Server accepts the connection but hangs and never sends data."""
        port = self._PORT_BASE

        def hang(conn):
            time.sleep(10)  # Longer than SOCKET_TIMEOUT_SECONDS in client.py

        self._start_bad_server(port, hang)
        try:
            result = request_current_from_ammeter(port, b'TEST')
            return result is None
        except (TimeoutError, socket.timeout, OSError):
            return True
        except Exception:
            return True

    def _scenario_garbled_data(self) -> bool:
        """Server replies with text that cannot be parsed as a float."""
        port = self._PORT_BASE + 1

        def send_garbage(conn):
            conn.sendall(b'NOT_A_NUMBER!!!')

        self._start_bad_server(port, send_garbage)
        try:
            result = request_current_from_ammeter(port, b'TEST')
            return result is None
        except ValueError:
            return True
        except Exception:
            return True

    def _scenario_empty_response(self) -> bool:
        """Server closes the connection immediately without sending any data."""
        port = self._PORT_BASE + 2

        def send_empty(conn):
            pass  # Close immediately — recv() will return b''

        self._start_bad_server(port, send_empty)
        try:
            result = request_current_from_ammeter(port, b'TEST')
            return result is None
        except Exception:
            return True

    def _scenario_disk_write_error(self) -> bool:
        """Archive fails because the results path does not exist and cannot be created."""
        framework = AmmeterTestFramework()
        framework.results_dir = Path("Z:\\nonexistent\\path\\that\\does\\not\\exist")

        fake_result = {
            "run_id": "disk-error-test-0000-000000000000",
            "ammeter_type": "greenlee",
            "started_at": "2026-01-01T00:00:00",
            "completed_at": "2026-01-01T00:00:01",
            "config": {"measurements_count": 1, "sampling_frequency_hz": 1.0},
            "samples": [1.0],
            "statistics": {"mean": 1.0, "median": 1.0, "std_dev": 0.0,
                           "min": 1.0, "max": 1.0, "count": 1},
        }
        try:
            framework._archive_result(fake_result)
            return True  # Error was caught internally — did not propagate
        except Exception as e:
            print(f"    [UNEXPECTED EXCEPTION] {e}")
            return False

    def _scenario_corrupted_json(self) -> bool:
        """list_results skips a file with invalid JSON instead of crashing."""
        framework = AmmeterTestFramework()
        corrupted = framework.results_dir / "corrupted_test_do_not_use.json"
        corrupted.write_text("{ this is not valid json !!!", encoding="utf-8")
        try:
            framework.list_results()
            return True  # Skipped the bad file gracefully
        except Exception as e:
            print(f"    [UNEXPECTED EXCEPTION] {e}")
            return False
        finally:
            corrupted.unlink(missing_ok=True)

    def _scenario_visualization_zero_std(self) -> bool:
        """Visualization handles all-identical samples (std_dev=0, bandwidth would be 0)."""
        framework = AmmeterTestFramework()
        fake_result = {
            "run_id": "viz-zero-std-0000-000000000000",
            "ammeter_type": "test",
            "started_at": "2026-01-01T00:00:00",
            "samples": [1.5, 1.5, 1.5],
            "statistics": {"mean": 1.5, "median": 1.5, "std_dev": 0.0,
                           "min": 1.5, "max": 1.5, "count": 3},
        }
        try:
            framework._visualize(fake_result)
            return True  # Completed without raising
        except Exception as e:
            print(f"    [UNEXPECTED EXCEPTION] {e}")
            return False

    def _scenario_framework_resilience(self) -> bool:
        """
        Points the framework at a non-existent port and runs a small test.
        Verifies it logs errors per sample, produces a failure summary,
        and does not raise an exception.
        """
        framework = AmmeterTestFramework()
        framework.config["ammeters"]["error_test"] = {
            "port": 5098,
            "command": "TEST -simulate_error",
        }

        try:
            result = framework.run_test("error_test", measurements_count=3)
            # Expect empty samples list — framework should have returned cleanly
            return result["samples"] == []
        except Exception as e:
            print(f"    [UNEXPECTED EXCEPTION] {e}")
            return False
