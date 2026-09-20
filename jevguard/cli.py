"""CLI: python -m jevguard "<prompt>" """

import json
import sys

from dotenv import load_dotenv

from .guard import check


def main() -> None:
    load_dotenv()
    if len(sys.argv) < 2:
        print('Usage: python -m jevguard "<prompt text>"', file=sys.stderr)
        raise SystemExit(1)

    prompt = " ".join(sys.argv[1:])
    result = check(prompt)
    print(json.dumps(result.to_dict(), indent=2))
    raise SystemExit(0 if result.verdict.value == "allow" else 1)


if __name__ == "__main__":
    main()
