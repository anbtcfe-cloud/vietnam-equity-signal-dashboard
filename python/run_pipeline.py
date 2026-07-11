import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PYTHON_DIR = BASE_DIR / "python"

scripts = [
    "03_build_quarterly_data.py",
    "04_calculate_technical_indicators.py",
    "05_signal_scoring.py",
    "07_add_benchmark_relative_strength.py",
    "06_peer_comparison.py",
]


def main():
    print("Starting Vietnam Equity Signal data pipeline...\n")
    print("Using Python interpreter:")
    print(sys.executable)
    print()

    for script in scripts:
        script_path = PYTHON_DIR / script

        print("=" * 80)
        print(f"Running: {script}")
        print("=" * 80)

        subprocess.run(
            [sys.executable, str(script_path)],
            check=True
        )

        print(f"Completed: {script}\n")

    print("Pipeline completed successfully.")


if __name__ == "__main__":
    main()