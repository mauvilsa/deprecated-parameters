import inspect
import warnings
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Dict, List, Literal, Optional, TypeVar, Union

__all__ = [
    "ParameterRemove",
    "ParameterRename",
    "DeprecatedParameters",
    "deprecated_parameters",
    "get_deprecated_parameters",
]

default_when = "the future"
default_remove_message = 'Argument "%(old_name)s" to "%(func)s" is deprecated and will be removed in %(when)s'
default_rename_message = (
    'Argument "%(old_name)s" to "%(func)s" is deprecated, it has been renamed to "%(new_name)s" '
    'and "%(old_name)s" will be removed in %(when)s'
)

F = TypeVar("F", bound=Callable)


class ParameterDeprecation:
    def __init__(
        self,
        *args,
        when,
        message,
        transform,
    ) -> None:
        if args:
            raise TypeError(f"{self.__class__.__name__} does not accept positional arguments.")
        self.when = when
        self.message = message
        self.transform = transform


class ParameterRemove(ParameterDeprecation):
    def __init__(
        self,
        *args,
        old_name: str,
        when: str = default_when,
        message: str = default_remove_message,
        transform: Literal["remove", None] = "remove",
    ) -> None:
        if transform not in ["remove", None]:
            raise ValueError("transform must be 'remove' or None.")
        self.old_name = old_name
        super().__init__(*args, when=when, message=message, transform=transform)


class ParameterRename(ParameterDeprecation):
    def __init__(
        self,
        *args,
        new_name: str,
        old_name: str,
        when: str = default_when,
        message: str = default_rename_message,
        transform: Literal["reassign", None] = "reassign",
    ) -> None:
        if transform not in ["reassign", None]:
            raise ValueError("transform must be 'reassign' or None.")
        self.new_name = new_name
        self.old_name = old_name
        super().__init__(*args, when=when, message=message, transform=transform)


@dataclass
class DeprecatedParameters:
    removed: List[ParameterRemove]
    renamed: List[ParameterRename]


_deprecations_register: Dict[str, DeprecatedParameters] = {}


def get_deprecated_parameters(func: Callable, /) -> Optional[DeprecatedParameters]:
    return _deprecations_register.get(f"{func.__module__}.{func.__qualname__}")


def deprecated_parameters(*deprecations: Union[ParameterRemove, ParameterRename]) -> Callable[[F], F]:
    """
    A decorator to mark parameters of a function or method as deprecated.

    Args:
        deprecations: parameter deprecation instances.

    Returns:
        The decorated function with registered parameter deprecations.
    """
    if len(deprecations) == 0:
        raise ValueError("At least one deprecation must be provided.")

    def decorator(func):
        fullname = f"{func.__module__}.{func.__qualname__}"
        if fullname in _deprecations_register:
            raise ValueError("The @deprecated_parameters decorator can only be applied once per callable.")

        deprecation = DeprecatedParameters(
            removed=[x for x in deprecations if isinstance(x, ParameterRemove)],
            renamed=[x for x in deprecations if isinstance(x, ParameterRename)],
        )

        if deprecation.renamed:
            params = list(inspect.signature(func).parameters.keys())
            for rename in deprecation.renamed:
                if rename.new_name not in params:
                    raise ValueError(f"Parameter '{rename.new_name}' not found in signature of {func}.")

        _deprecations_register[fullname] = deprecation

        @wraps(func)
        def wrapper(*args, **kwargs):
            for removal in deprecation.removed:
                if removal.old_name in kwargs:
                    warnings.warn(
                        removal.message % {"func": func.__name__, "old_name": removal.old_name, "when": removal.when},
                        category=DeprecationWarning,
                    )
                    if removal.transform == "remove":
                        del kwargs[removal.old_name]

            for rename in deprecation.renamed:
                if rename.old_name in kwargs:
                    warnings.warn(
                        rename.message
                        % {
                            "func": func.__name__,
                            "old_name": rename.old_name,
                            "new_name": rename.new_name,
                            "when": rename.when,
                        },
                        category=DeprecationWarning,
                    )
                    if rename.transform == "reassign":
                        positionals = list(inspect.signature(func).parameters.keys())[: len(args)]
                        if rename.new_name in kwargs or rename.new_name in positionals:
                            raise ValueError(
                                f"Unable to reassign '{rename.old_name}' because '{rename.new_name}' is also set."
                            )
                        kwargs[rename.new_name] = kwargs.pop(rename.old_name)

            return func(*args, **kwargs)

        return wrapper

    return decorator
