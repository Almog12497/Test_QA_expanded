import threading
import time

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.testing.test_framework import AmmeterTestFramework
from src.testing.error_simulation import ErrorSimulator


def run_greenlee_emulator():
    greenlee = GreenleeAmmeter(5001)
    greenlee.start_server()

def run_entes_emulator():
    entes = EntesAmmeter(5002)
    entes.start_server()

def run_circutor_emulator():
    circutor = CircutorAmmeter(5003)
    circutor.start_server()


if __name__ == "__main__":

    # ------------------------------------------------------------------ #
    # SECTION 1 — Start ammeter emulators                                 #
    # Each emulator runs in a background thread on its own port.          #
    # Greenlee: 5001 | ENTES: 5002 | CIRCUTOR: 5003                      #
    # ------------------------------------------------------------------ #
    threading.Thread(target=run_greenlee_emulator, daemon=True).start()
    threading.Thread(target=run_entes_emulator, daemon=True).start()
    threading.Thread(target=run_circutor_emulator, daemon=True).start()

    # Wait for the servers to start. Increase sleep time if servers aren't ready in time.
    time.sleep(5)

    # ------------------------------------------------------------------ #
    # SECTION 2 — Run measurement tests                                   #
    # Collects samples from each ammeter and saves results to results/.   #
    # Sampling parameters can be overridden here or set in config.yaml.   #
    # Example override: framework.run_test(ammeter, measurements_count=5) #
    # ------------------------------------------------------------------ #
    framework = AmmeterTestFramework()
    run_ids = []
    for ammeter in ["greenlee", "entes", "circutor"]:
        result = framework.run_test(ammeter)
        run_ids.append(result["run_id"][:4])

    # ------------------------------------------------------------------ #
    # SECTION 3 — List all historical results                             #
    # Shows every saved run across all sessions in a summary table.       #
    # ------------------------------------------------------------------ #
    print("\n\n=== All saved results ===")
    framework.list_results()

    # ------------------------------------------------------------------ #
    # SECTION 4 — Compare results from this run                           #
    # Side-by-side stats table for the three ammeters just tested.        #
    # ------------------------------------------------------------------ #
    print("\n\n=== Comparison of this run ===")
    framework.compare_results(run_ids)

    # ------------------------------------------------------------------ #
    # SECTION 5 — Accuracy assessment                                     #
    # Ranks ammeters by precision (coefficient of variation).             #
    # Identifies the most reliable measurement method.                    #
    # ------------------------------------------------------------------ #
    print("\n")
    framework.accuracy_assessment(run_ids)

    # ------------------------------------------------------------------ #
    # SECTION 6 — Error simulation                                        #
    # Runs failure scenarios to verify error handling works correctly.    #
    # Safe to comment out — does not affect real results.                 #
    # ------------------------------------------------------------------ #
    print("\n")
    ErrorSimulator().run_all()
