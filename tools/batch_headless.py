"""Run multiple headless playthroughs and summarize outcomes."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_one(url: str, rounds: int, ticker_speed: float, fps: float, class_id: str = "fighter") -> dict:
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "headless_playthrough.py"),
        "--url", url,
        "--rounds", str(rounds),
        "--ticker-speed", str(ticker_speed),
        "--fps", str(fps),
        "--class", class_id,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    outcome = "unknown"
    final_hp = 0
    web_seconds = 0.0
    for line in result.stdout.splitlines() + result.stderr.splitlines():
        if line.startswith("Outcome:"):
            outcome = line.split("Outcome:", 1)[1].strip().lower()
        elif line.startswith("Final HP:"):
            try:
                final_hp = int(line.split("Final HP:", 1)[1].strip())
            except ValueError:
                pass
        elif "Web-equivalent" in line:
            try:
                web_seconds = float(line.split(":", 1)[1].strip().split("s")[0])
            except ValueError:
                pass
    return {
        "outcome": outcome,
        "final_hp": final_hp,
        "web_seconds": web_seconds,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch headless Sanctuary benchmark")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--url", default="http://127.0.0.1:8700")
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--ticker-speed", type=float, default=40.0)
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--class", dest="class_id", default="fighter", help="Character class to benchmark")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    wins = 0
    defeats = 0
    unknown = 0
    times = []
    for i in range(1, args.runs + 1):
        print(f"\n=== Run {i}/{args.runs} ===", flush=True)
        res = run_one(args.url, args.rounds, args.ticker_speed, args.fps, args.class_id)
        if args.verbose:
            print(res["stdout"], file=sys.stdout)
            print(res["stderr"], file=sys.stderr)
        outcome = res["outcome"].lower()
        is_win = "win" in outcome or "cleared" in outcome or "exit open" in outcome or "victory" in outcome
        is_defeat = "defeat" in outcome or "fallen" in outcome or "died" in outcome or "unconscious" in outcome
        if is_win:
            wins += 1
            print(f"Run {i}: WIN (HP {res['final_hp']}, {res['web_seconds']:.1f}s)")
        elif is_defeat:
            defeats += 1
            print(f"Run {i}: DEFEAT (HP {res['final_hp']}, {res['web_seconds']:.1f}s)")
            if not args.verbose:
                print(res["stdout"])
        else:
            unknown += 1
            print(f"Run {i}: UNKNOWN ({res['outcome']}, HP {res['final_hp']}, {res['web_seconds']:.1f}s)")
            if not args.verbose:
                print(res["stdout"])
                if res["stderr"]:
                    print("--- stderr ---")
                    print(res["stderr"])
        times.append(res["web_seconds"])

    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)
    print(f"Class:    {args.class_id}")
    print(f"Runs:     {args.runs}")
    print(f"Wins:     {wins} ({100*wins/args.runs:.0f}%)")
    print(f"Defeats:  {defeats} ({100*defeats/args.runs:.0f}%)")
    print(f"Unknown:  {unknown}")
    if times:
        print(f"Time min: {min(times):.1f}s")
        print(f"Time max: {max(times):.1f}s")
        print(f"Time avg: {sum(times)/len(times):.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
