from __future__ import annotations

from typing import cast

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def normalize_rows(matrix: Array) -> Array:
    """
    L2-normalize each row while guarding against zero vectors.
    """
    if matrix.ndim != 2:
        raise ValueError("normalize_rows expects a 2D matrix.")

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = matrix / norms
    return cast(Array, normalized)
