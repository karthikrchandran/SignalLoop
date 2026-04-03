from worker_app.policies.enforcement_gate import EnforcementGate


def main() -> None:
    gate = EnforcementGate()
    print(f"EngageHub worker initialized (paused={gate.is_paused()})")


if __name__ == "__main__":
    main()
