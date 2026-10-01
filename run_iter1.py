"""Run just iteration 1 against v3.0 to get feedback signals for ontology revision."""
import convergence_experiment as ce

TICKETS = ce.TICKETS
def main():
    ce.run_iteration("Iteration 1 (baseline)", TICKETS, "ontology_v3.json")


if __name__ == "__main__":
    main()
