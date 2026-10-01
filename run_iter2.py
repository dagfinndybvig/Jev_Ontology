"""Run just iteration 2 against v4.0 to get feedback signals."""
import convergence_experiment as ce

TICKETS = ce.TICKETS
def main():
    if not ce.API_KEY:
        raise SystemExit("Missing TYPESAFE_API_KEY")
    ce.run_iteration("Iteration 2 (v4.0)", TICKETS, "ontology_v4.json")


if __name__ == "__main__":
    main()
