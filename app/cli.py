"""Entry point for the installed 'study buddy' command."""
import sys


def main():
    if sys.argv[1:] in ([], ["--help"], ["-h"]):
        print("Usage: study buddy [server options]\nStart your local Study Buddy app. Press Ctrl+C to stop.")
        return 0
    if sys.argv[1] != "buddy":
        print("Usage: study buddy", file=sys.stderr)
        return 2
    del sys.argv[1]
    from app.launch import main as launch
    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
