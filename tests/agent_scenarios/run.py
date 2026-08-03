from __future__ import annotations

import asyncio
import sys

from .runner import ScenarioRunner, ALL_SCENARIOS

DEFAULT_AGENT_URL = "http://localhost:8002"


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AGENT_URL
    print(f"Running test agent scenarios against: {url}")
    print("=" * 60)

    async def _run() -> None:
        async with ScenarioRunner(agent_url=url) as runner:
            results = await runner.run_all(ALL_SCENARIOS)

        total = len(results)
        passed = sum(1 for r in results if r.overall_passed)
        failed = total - passed

        print(f"\n{'=' * 60}")
        print(f"Results: {passed}/{total} scenarios passed")

        for r in results:
            status = "PASS" if r.overall_passed else "FAIL"
            print(f"\n[{status}] {r.scenario_name} — {r.description}")
            print(f"  Persona: {r.persona} | Turns: {len(r.turns)} | Time: {r.total_time_ms:.0f}ms")

            for t in r.turns:
                turn_status = "OK" if t.passed else "FAIL"
                print(f"  Turn {t.turn_index}: {turn_status} ({t.elapsed_ms:.0f}ms)")
                if t.errors:
                    for err in t.errors:
                        print(f"    ERROR: {err}")
                if t.expect_pending and not t.pending_received:
                    print(f"    WARNING: Expected pending_confirmation but got '{t.status}'")

            if r.failed_turns:
                for ft in r.failed_turns:
                    print(f"  Failed turn response: {ft.response[:200]}")

        if failed > 0:
            print(f"\n{failed} scenario(s) FAILED")
            sys.exit(1)
        else:
            print(f"\nAll {total} scenarios PASSED")

    asyncio.run(_run())


if __name__ == "__main__":
    main()