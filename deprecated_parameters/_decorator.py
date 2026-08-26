import inspect
import warnings
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, List, Literal, Optional, Tuple, Type, TypeVar, Union

from ._sphinx import document_deprecations, documenting

__all__ = [
    "ParameterRemove",
    "ParameterRename",
    "ParameterPositional",
    "ParameterValueRemove",
    "DeprecatedParameters",
    "deprecated_parameters",
    "get_deprecated_parameters",
]

default_when = "the future"
#: The messages say what the call is going to run into, not what happened to the signature, which for a
#: deprecation declared with a transform has already changed.
default_remove_message = (
    'Argument "%(old_name)s" for "%(func)s" is deprecated%(since)s and will no longer be accepted in %(when)s'
)
#: Used instead of the above when the transform drops the argument, since then the caller also needs to
#: know that the value it gives no longer has any effect.
default_remove_ignored_message = (
    'Argument "%(old_name)s" for "%(func)s" is deprecated%(since)s, its value is ignored and it will no '
    "longer be accepted in %(when)s"
)
default_rename_message = (
    'Argument "%(old_name)s" for "%(func)s" is deprecated%(since)s, it has been renamed to "%(new_name)s" '
    'and "%(old_name)s" will no longer be accepted in %(when)s'
)
default_positional_message = (
    'Giving argument "%(name)s" for "%(func)s" positionally is deprecated%(since)s, it must be given as a '
    "keyword argument in %(when)s"
)
default_value_message = (
    'Value %(old_value)r for argument "%(name)s" of "%(func)s" is deprecated%(since)s and will not be '
    "supported in %(when)s%(instead)s"
)

#: Attribute in which the deprecations are stored, in the callable returned by the decorator.
deprecations_attribute = "__deprecated_parameters__"

F = TypeVar("F", bound=Callable)

positional_kinds = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)


class _Unset:
    """Sentinel for values that were not given, distinguishing them from None."""

    def __repr__(self) -> str:
        return "<unset>"


unset: Any = _Unset()


def _validate_version(version: Optional[str]) -> None:
    if version is None:
        return
    if not isinstance(version, str):
        raise TypeError("version must be a string.")
    from packaging.version import InvalidVersion, Version

    try:
        Version(version)
    except InvalidVersion:
        raise ValueError(f"version {version!r} is not a valid PEP 440 version.") from None


def _validate_old_index(old_index: Optional[int], required: bool = False) -> None:
    if old_index is None and not required:
        return
    if not isinstance(old_index, int) or isinstance(old_index, bool) or old_index < 0:
        raise ValueError("old_index must be a non-negative integer.")


def _validate_category(category: Type[Warning]) -> None:
    if not (isinstance(category, type) and issubclass(category, Warning)):
        raise TypeError("category must be a Warning subclass.")


class ParameterDeprecation:
    """Base class for the deprecation of a parameter."""

    #: Name of the parameter that the deprecation refers to.
    name: str

    #: Position the parameter had in the previous signature, when it can still be given positionally.
    old_index: Optional[int] = None

    def __init__(
        self,
        *,
        when: str,
        message: str,
        transform: Optional[str],
        version: Optional[str],
        category: Type[Warning],
    ) -> None:
        _validate_version(version)
        _validate_category(category)
        self.when = when
        self.message = message
        self.transform = transform
        self.version = version
        self.category = category

    @property
    def since(self) -> str:
        return f" since {self.version}" if self.version else ""

    def message_values(self, func_name: str) -> dict:
        return {
            "func": func_name,
            "when": self.when,
            "version": self.version,
            "since": self.since,
            "name": self.name,
        }

    def format(self, func_name: str) -> str:
        return self.message % self.message_values(func_name)


class ParameterRemove(ParameterDeprecation):
    """A parameter that is being removed.

    ``old_index`` is only needed for a parameter that callers could also give positionally. It is the
    position it had in the previous signature, zero based and counting every positional parameter, which
    includes ``self`` for methods. Without it only the keyword form is recognized, and a call still
    giving the parameter positionally fails as it would without the decorator.
    """

    def __init__(
        self,
        *,
        old_name: str,
        old_index: Optional[int] = None,
        when: str = default_when,
        message: Optional[str] = None,
        transform: Literal["remove", None] = "remove",
        version: Optional[str] = None,
        category: Type[Warning] = DeprecationWarning,
    ) -> None:
        if transform not in ["remove", None]:
            raise ValueError("transform must be 'remove' or None.")
        _validate_old_index(old_index)
        if message is None:
            message = default_remove_ignored_message if transform == "remove" else default_remove_message
        self.old_name = old_name
        self.name = old_name
        self.old_index = old_index
        super().__init__(when=when, message=message, transform=transform, version=version, category=category)

    def message_values(self, func_name: str) -> dict:
        return {**super().message_values(func_name), "old_name": self.old_name}


class ParameterRename(ParameterDeprecation):
    """A parameter that is being renamed."""

    def __init__(
        self,
        *,
        new_name: str,
        old_name: str,
        when: str = default_when,
        message: str = default_rename_message,
        transform: Literal["reassign", None] = "reassign",
        version: Optional[str] = None,
        category: Type[Warning] = DeprecationWarning,
    ) -> None:
        if transform not in ["reassign", None]:
            raise ValueError("transform must be 'reassign' or None.")
        self.new_name = new_name
        self.old_name = old_name
        self.name = old_name
        super().__init__(when=when, message=message, transform=transform, version=version, category=category)

    def message_values(self, func_name: str) -> dict:
        return {**super().message_values(func_name), "old_name": self.old_name, "new_name": self.new_name}


class ParameterPositional(ParameterDeprecation):
    """A parameter that is becoming keyword-only.

    ``old_index`` is the position the parameter had in the previous signature, zero based and counting
    every positional parameter, which includes ``self`` for methods. It is given explicitly instead of
    being taken from the order of the deprecations, so that reordering them can not silently change
    which argument goes where. Applying the decorator fails when it does not match the signature, and
    the error states which indexes are expected.
    """

    old_index: int

    def __init__(
        self,
        *,
        name: str,
        old_index: int,
        when: str = default_when,
        message: str = default_positional_message,
        transform: Literal["keyword", None] = "keyword",
        version: Optional[str] = None,
        category: Type[Warning] = DeprecationWarning,
    ) -> None:
        if transform not in ["keyword", None]:
            raise ValueError("transform must be 'keyword' or None.")
        _validate_old_index(old_index, required=True)
        self.name = name
        self.old_index = old_index
        super().__init__(when=when, message=message, transform=transform, version=version, category=category)


class ParameterValueRemove(ParameterDeprecation):
    """A single value of a parameter that is being deprecated, rather than the parameter itself.

    The transform replaces the deprecated value with ``new_value``. When there is no replacement,
    ``new_value`` is simply not given and the transform has nothing to do, so the caller keeps
    receiving the deprecated value. ``transform=None`` is only needed to warn about a value that does
    have a replacement without applying it.
    """

    def __init__(
        self,
        *,
        name: str,
        old_value: Any,
        new_value: Any = unset,
        when: str = default_when,
        message: str = default_value_message,
        transform: Literal["replace", None] = "replace",
        version: Optional[str] = None,
        category: Type[Warning] = DeprecationWarning,
    ) -> None:
        if transform not in ["replace", None]:
            raise ValueError("transform must be 'replace' or None.")
        self.name = name
        self.old_value = old_value
        self.new_value = new_value
        super().__init__(when=when, message=message, transform=transform, version=version, category=category)

    def message_values(self, func_name: str) -> dict:
        instead = "" if self.new_value is unset else f", use {self.new_value!r} instead"
        return {
            **super().message_values(func_name),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "instead": instead,
        }


@dataclass
class DeprecatedParameters:
    removed: List[ParameterRemove] = field(default_factory=list)
    renamed: List[ParameterRename] = field(default_factory=list)
    positional: List[ParameterPositional] = field(default_factory=list)
    values: List[ParameterValueRemove] = field(default_factory=list)
    signature: Optional[inspect.Signature] = None

    @property
    def all(self) -> List[ParameterDeprecation]:
        return [*self.removed, *self.renamed, *self.positional, *self.values]


def get_deprecated_parameters(func: Callable, /) -> Optional[DeprecatedParameters]:
    """Return the parameter deprecations of a callable, or None if it has none."""
    return getattr(func, deprecations_attribute, None)


def _mark_coroutine_function(wrapper: Callable) -> None:
    """Mark a sync wrapper that returns a coroutine as being a coroutine function.

    From python 3.12 this makes both inspect.iscoroutinefunction and asyncio.iscoroutinefunction true.
    Before that only asyncio.iscoroutinefunction can be influenced, which is what async frameworks used.
    """
    mark = getattr(inspect, "markcoroutinefunction", None)
    if mark is not None:  # python>=3.12
        mark(wrapper)
        return
    import asyncio

    marker = getattr(asyncio.coroutines, "_is_coroutine", None)
    if marker is not None:  # python<3.12
        wrapper._is_coroutine = marker  # type: ignore[attr-defined]


def _positional_index(signature: inspect.Signature, name: str) -> Optional[int]:
    """Index at which a parameter can be given positionally, or None if it can not."""
    for index, (param_name, param) in enumerate(signature.parameters.items()):
        if param_name == name:
            return index if param.kind in positional_kinds else None
    return None


def _num_positional(signature: inspect.Signature) -> int:
    return sum(1 for param in signature.parameters.values() if param.kind in positional_kinds)


def _has_var_keyword(signature: inspect.Signature) -> bool:
    return any(param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())


def _rescued_positional(deprecations: List[Any]) -> List[Any]:
    """Deprecations of arguments that callers may still give beyond the positional parameters.

    These are the parameters that left the positional part of the signature, either because they were
    removed or because they became keyword-only. Together they occupy one contiguous range of old
    positions, right after the positional parameters that remain, which is what makes an argument given
    for them distinguishable from one given for a parameter that is still there. They are therefore
    validated and applied as a single block, sorted by the position each one had.
    """
    extra = [x for x in deprecations if x.old_index is not None and x.transform is not None]
    return sorted(extra, key=lambda x: x.old_index)


def _given_value(signature: inspect.Signature, name: str, args: list, kwargs: dict) -> Any:
    """Value given for a parameter, either positionally or as a keyword, or unset if not given."""
    if name in kwargs:
        return kwargs[name]
    index = _positional_index(signature, name)
    if index is not None and index < len(args):
        return args[index]
    return unset


def _values_equal(given: Any, deprecated: Any) -> bool:
    """Whether a given value is the deprecated one, tolerating types with an unusual __eq__."""
    try:
        return bool(given == deprecated)
    except Exception:
        return False


def _validate_current_index(func: Callable, signature: inspect.Signature, name: str, old_index: int) -> None:
    """Check where a parameter that is only warned about, not transformed, sits in the signature."""
    index = _positional_index(signature, name)
    if index is None:
        raise ValueError(
            f"Parameter '{name}' must be positional in the signature of {func.__name__} "
            f"for transform=None, otherwise it can not be given positionally at all."
        )
    if old_index != index:
        raise ValueError(
            f"old_index for '{name}' must be {index}, the position it has in the "
            f"signature of {func.__name__}, got {old_index}."
        )


def _validate(func: Callable, deprecation: DeprecatedParameters) -> None:
    signature = deprecation.signature
    assert signature is not None
    params = signature.parameters

    for rename in deprecation.renamed:
        if rename.new_name not in params:
            raise ValueError(f"Parameter '{rename.new_name}' not found in signature of {func.__name__}.")

    changes: List[Union[ParameterRemove, ParameterRename]] = [*deprecation.removed, *deprecation.renamed]
    for change in changes:
        if change.transform and change.old_name in params:
            raise ValueError(
                f"Parameter '{change.old_name}' is still in the signature of {func.__name__}, so the "
                f"'{change.transform}' transform would silently discard the value given by the caller. "
                f"Remove it from the signature, or use transform=None to keep receiving it."
            )
        if change.transform is None and change.old_name not in params and not _has_var_keyword(signature):
            raise ValueError(
                f"Parameter '{change.old_name}' is not in the signature of {func.__name__} and there is no "
                f"**kwargs to receive it, so with transform=None every call giving it would fail. Put it "
                f"back in the signature, or drop transform=None so that the call is adapted to it."
            )

    for removal in deprecation.removed:
        if removal.transform is None and removal.old_index is not None:
            _validate_current_index(func, signature, removal.old_name, removal.old_index)

    for positional in deprecation.positional:
        if positional.name not in params:
            raise ValueError(f"Parameter '{positional.name}' not found in signature of {func.__name__}.")
        kind = params[positional.name].kind
        if positional.transform == "keyword" and kind != inspect.Parameter.KEYWORD_ONLY:
            raise ValueError(
                f"Parameter '{positional.name}' must be keyword-only in the signature of {func.__name__} for "
                f"the 'keyword' transform, since the transform exists to rescue callers that can no longer "
                f"give it positionally. Use transform=None to only warn about it."
            )
        if positional.transform is None:
            _validate_current_index(func, signature, positional.name, positional.old_index)

    extra = _rescued_positional(deprecation.all)
    if extra:
        first = _num_positional(signature)
        expected = list(range(first, first + len(extra)))
        given = sorted(x.old_index for x in extra)
        if given != expected:
            raise ValueError(
                f"The old_index values of the parameters of {func.__name__} that are no longer positional "
                f"must be {expected}, got {given}. They are the positions the parameters had in the "
                f"previous signature, counting every positional parameter, self included for methods."
            )

    for value in deprecation.values:
        if value.name not in params:
            raise ValueError(f"Parameter '{value.name}' not found in signature of {func.__name__}.")


def _warn(deprecation: ParameterDeprecation, func_name: str) -> None:
    warnings.warn(deprecation.format(func_name), category=deprecation.category, stacklevel=4)


def _apply_deprecations(
    func: Callable, deprecation: DeprecatedParameters, args: tuple, kwargs: dict
) -> Tuple[tuple, dict]:
    """Warn about deprecated arguments and transform the call, returning the new args and kwargs."""
    signature = deprecation.signature
    assert signature is not None
    func_name = func.__name__
    arguments = list(args)
    num_positional = _num_positional(signature)

    # Arguments given at positions the signature no longer has, that is for parameters which were
    # removed or became keyword-only. Worked out before anything is changed, so that the checks below
    # see the call as the caller wrote it.
    extra = _rescued_positional(deprecation.all)
    rescued = [x for x in extra if len(arguments) > num_positional and x.old_index < len(arguments)]
    rescued_names = {x.name for x in rescued}

    for removal in deprecation.removed:
        given_keyword = removal.old_name in kwargs
        index = _positional_index(signature, removal.old_name)
        given_positional = removal.old_name in rescued_names or (index is not None and index < len(arguments))
        if given_keyword or given_positional:
            _warn(removal, func_name)
            if removal.transform == "remove" and given_keyword:
                del kwargs[removal.old_name]

    for rename in deprecation.renamed:
        if rename.old_name in kwargs:
            _warn(rename, func_name)
            if rename.transform == "reassign":
                positionals = list(signature.parameters)[: len(arguments)]
                if rename.new_name in kwargs or rename.new_name in positionals:
                    raise ValueError(f"Unable to reassign '{rename.old_name}' because '{rename.new_name}' is also set.")
                kwargs[rename.new_name] = kwargs.pop(rename.old_name)

    if rescued:
        for deprecated_positional in rescued:
            # Removals are already warned about above, and their value is simply not carried over.
            if isinstance(deprecated_positional, ParameterPositional):
                _warn(deprecated_positional, func_name)
                kwargs[deprecated_positional.name] = arguments[deprecated_positional.old_index]
        # Anything beyond the declared deprecations is left alone, to fail as it normally would.
        last = max(x.old_index for x in extra)
        arguments = arguments[:num_positional] + arguments[last + 1 :]

    for positional in deprecation.positional:
        if positional.transform is None and positional.old_index < len(arguments):
            _warn(positional, func_name)

    for value in deprecation.values:
        given = _given_value(signature, value.name, arguments, kwargs)
        if given is not unset and _values_equal(given, value.old_value):
            _warn(value, func_name)
            # Without a new_value there is nothing to replace with, so the transform has nothing to do.
            if value.transform == "replace" and value.new_value is not unset:
                if value.name in kwargs:
                    kwargs[value.name] = value.new_value
                else:
                    index = _positional_index(signature, value.name)
                    assert index is not None
                    arguments[index] = value.new_value

    return tuple(arguments), kwargs


Deprecation = Union[ParameterRemove, ParameterRename, ParameterPositional, ParameterValueRemove]


def deprecated_parameters(*deprecations: Deprecation) -> Callable[[F], F]:
    """
    A decorator to mark parameters of a function or method as deprecated.

    While sphinx is building, and only then, the deprecations are also appended to the docstring of the
    decorated callable as ``.. deprecated::`` directives, one per version.

    Args:
        deprecations: parameter deprecation instances.

    Returns:
        The decorated function with registered parameter deprecations.
    """
    if len(deprecations) == 0:
        raise ValueError("At least one deprecation must be provided.")

    def decorator(func):
        if inspect.isclass(func):
            raise TypeError(
                "The @deprecated_parameters decorator can not be applied to classes. Apply it to the "
                "__init__ method instead."
            )
        if get_deprecated_parameters(func) is not None:
            raise ValueError("The @deprecated_parameters decorator can only be applied once per callable.")

        deprecation = DeprecatedParameters(
            removed=[x for x in deprecations if isinstance(x, ParameterRemove)],
            renamed=[x for x in deprecations if isinstance(x, ParameterRename)],
            positional=[x for x in deprecations if isinstance(x, ParameterPositional)],
            values=[x for x in deprecations if isinstance(x, ParameterValueRemove)],
            signature=inspect.signature(func),
        )

        _validate(func, deprecation)

        # For coroutine functions the wrapper is intentionally sync, such that the warning is issued when
        # the coroutine is created, i.e. at the call site, instead of when it is awaited, i.e. deep inside
        # the event loop where the stack no longer relates to the caller.
        @wraps(func)
        def wrapper(*args, **kwargs):
            args, kwargs = _apply_deprecations(func, deprecation, args, kwargs)
            return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            _mark_coroutine_function(wrapper)

        setattr(wrapper, deprecations_attribute, deprecation)

        if documenting():
            wrapper.__doc__ = document_deprecations(func.__doc__, func.__name__, deprecation)

        return wrapper

    return decorator
