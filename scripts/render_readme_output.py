"""Regenerate the README's generated blocks so they can never drift from behaviour.

Two blocks: the demo terminal output, and the test list — the latter is produced
by actually running the suite, so a failing test means no README update.
"""
import re
import subprocess
import sys
from pathlib import Path

README = Path(__file__).parent.parent / "README.md"
OUTPUT_MARKER = re.compile(
    r"(<!-- BEGIN OUTPUT -->\n```\n).*?(\n```\n<!-- END OUTPUT -->)", re.DOTALL
)
TESTS_MARKER = re.compile(
    r"(<!-- BEGIN TESTS -->\n```\n).*?(\n```\n<!-- END TESTS -->)", re.DOTALL
)


def demo_output() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "lane_drill.cli", "--demo"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def test_report() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--tb=no"],
        capture_output=True, text=True, check=True,
    )
    lines = []
    for line in result.stdout.splitlines():
        if "::" in line and " PASSED" in line:
            lines.append(line.split(" PASSED")[0] + " PASSED")
        elif re.match(r"=+ \d+ passed", line):
            # strip the wall-clock time so the block is byte-stable
            lines.append(re.sub(r" in [\d.]+s", "", line.strip("= ")).strip())
    *tests, summary = lines
    return "\n".join([summary, ""] + tests)


def main() -> int:
    text = README.read_text()
    text = OUTPUT_MARKER.sub(lambda m: m.group(1) + demo_output() + m.group(2), text)
    text = TESTS_MARKER.sub(lambda m: m.group(1) + test_report() + m.group(2), text)
    README.write_text(text)
    print("README generated blocks updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
