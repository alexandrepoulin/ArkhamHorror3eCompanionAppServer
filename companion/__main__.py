"""The main file."""

import sys

from companion.extension import sum_as_string


def main():
    answer = sum_as_string(1, 2)
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
