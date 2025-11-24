import sys

from .main import main

if __name__ == "__main__":
    MIN_VERSION = (3, 11)
    MAX_VERSION = (3, 14)

    if not (MIN_VERSION <= sys.version_info[:2] <= MAX_VERSION):
        version_str = ".".join(map(str, sys.version_info[:3]))
        raise RuntimeError(
            f"Unsupported Python version: {version_str}. "
            f"boardgame-recommender requires Python {MIN_VERSION[0]}.{MIN_VERSION[1]} "
            f"to {MAX_VERSION[0]}.{MAX_VERSION[1]} due to scikit-learn/scipy "
            f"compatibility constraints."
        )

    main(sys.argv[1:])
