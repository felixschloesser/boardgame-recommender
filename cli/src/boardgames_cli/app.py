import sys

from boardgames_cli.cli import run


def main() -> None:
    MIN_VERSION = (3, 11)
    MAX_VERSION = (3, 14)

    if not (MIN_VERSION <= sys.version_info[:2] <= MAX_VERSION):
        version_str = ".".join(map(str, sys.version_info[:3]))
        raise RuntimeError(
            f"Unsupported Python version: {version_str}. "
            f"boardgames-cli requires Python {MIN_VERSION[0]}.{MIN_VERSION[1]} "
            f"to {MAX_VERSION[0]}.{MAX_VERSION[1]} due to scikit-learn/scipy "
            f"compatibility constraints."
        )

    run(sys.argv[1:])
