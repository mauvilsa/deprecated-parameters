"""Small example library, in which every kind of parameter deprecation is used once.

Run it to see the warnings that the calls at the bottom get::

    python mylibrary.py

Check the same calls statically, without running them::

    mypy --config-file mypy.ini mylibrary.py

Build the documentation, in which each deprecation shows up as a ``deprecated`` directive::

    sphinx-build -b html docs build
"""

import sys
import warnings
from typing import Any, Dict, List, Literal

from deprecated_parameters import (
    ParameterPositional,
    ParameterRemove,
    ParameterRename,
    ParameterValueRemove,
    deprecated_parameters,
)

__all__ = [
    "read_table",
    "compute",
    "train",
    "solve",
    "configure",
    "Session",
]


@deprecated_parameters(
    ParameterRemove(old_name="verbose", old_index=2, version="1.5.0", when="v2.0.0"),
)
def read_table(path: str, encoding: str = "utf-8") -> List[str]:
    """Read a table from a file.

    The previous signature was ``read_table(path, encoding, verbose)``. ``verbose`` is gone from it,
    and ``old_index=2`` is the position it had, so that callers giving it positionally are warned
    instead of getting a ``TypeError``. Its value is dropped, which is what the warning says.

    Args:
        path: File to read.
        encoding: Encoding of the file.
    """
    return [f"{path} read as {encoding}"]


@deprecated_parameters(
    ParameterRename(old_name="n_jobs", new_name="workers", version="1.5.0", when="v2.0.0"),
)
def compute(data: List[int], *, workers: int = 1) -> int:
    """Compute something over the data.

    ``n_jobs`` is only the old name of ``workers``, so the value given for it is forwarded to
    ``workers`` and the function never sees the old name.

    Args:
        data: The data to compute over.
        workers: Number of workers to use.
    """
    return sum(data) * workers


@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1, version="1.6.0", when="v2.0.0"),
)
def train(data: List[int], *, workers: int = 1) -> int:
    """Train something on the data.

    ``workers`` is already keyword-only in the signature. ``old_index=1`` is the position it used to
    have, so a caller still giving it there is warned and the value is moved to the keyword argument.

    Args:
        data: The data to train on.
        workers: Number of workers to use.
    """
    return len(data) * workers


@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="linear", new_value="lstsq", version="1.6.0", when="v2.0.0"),
)
def solve(data: List[int], *, method: Literal["lstsq", "qr"] = "qr") -> str:
    """Solve a system.

    Here it is not the parameter that is deprecated but one of the values it used to accept.
    ``"linear"`` is gone from the annotation, and a caller still passing it gets ``"lstsq"`` instead.

    Args:
        data: The data to solve for.
        method: Method to use.
    """
    return method


@deprecated_parameters(
    ParameterRemove(
        old_name="log_level",
        transform=None,
        version="1.6.0",
        when="v2.0.0",
        category=FutureWarning,
        message='Setting "%(old_name)s" through %(func)s is deprecated%(since)s, '
        "use logging.getLogger() instead, it will be ignored from %(when)s",
    ),
)
def configure(**settings: Any) -> Dict[str, Any]:
    """Configure the library.

    ``transform=None`` announces the deprecation without changing the call, so ``log_level`` still
    arrives in ``**settings`` and is still honored. The category is ``FutureWarning``, which unlike
    ``DeprecationWarning`` is shown to end users by default, and the message is a custom one.

    Args:
        settings: Settings to apply.
    """
    return settings


class Session:
    """A session against a service.

    The decorator cannot be applied to a class, it is applied to ``__init__``, and mypy reports the
    deprecations on calls to the class.
    """

    @deprecated_parameters(
        ParameterRename(old_name="max_retries", new_name="retries", version="1.7.0", when="v2.0.0"),
    )
    def __init__(self, endpoint: str, *, retries: int = 3) -> None:
        """Open the session.

        Args:
            endpoint: Where to connect to.
            retries: How often to retry a request.
        """
        self.endpoint = endpoint
        self.retries = retries


def main() -> None:
    """Call everything above the way a caller that has not migrated yet would."""
    # DeprecationWarning is hidden outside of __main__ and only shown once per location, so that
    # users of a library are not bothered by warnings they cannot act on. Here every one is wanted.
    warnings.simplefilter("always")

    def section(title: str) -> None:
        print(f"\n--- {title}", file=sys.stderr, flush=True)

    section("ParameterRemove, given positionally")
    read_table("data.csv", "utf-8", True)

    section("ParameterRemove, given by keyword")
    read_table("data.csv", verbose=True)

    section("ParameterRename")
    compute([1, 2, 3], n_jobs=4)

    section("ParameterPositional")
    train([1, 2, 3], 4)

    section("ParameterValueRemove")
    solve([1, 2, 3], method="linear")

    section("ParameterRemove with transform=None, a custom message and FutureWarning")
    configure(log_level="debug")

    section("ParameterRename in a constructor")
    Session("https://example.com", max_retries=5)


if __name__ == "__main__":
    main()
