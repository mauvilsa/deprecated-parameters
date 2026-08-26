import asyncio
import inspect
import sys
import warnings

import pytest

from deprecated_parameters import (
    ParameterPositional,
    ParameterRemove,
    ParameterRename,
    ParameterValueRemove,
    deprecated_parameters,
    get_deprecated_parameters,
)


def test_parameter_remove_missing_required():
    with pytest.raises(TypeError, match="missing 1 required keyword-only argument: 'old_name'"):
        ParameterRemove()


def test_parameter_rename_missing_required():
    with pytest.raises(TypeError, match="missing 1 required keyword-only argument: 'new_name'"):
        ParameterRename(old_name="old_name")


def test_parameter_remove_invalid_transform():
    with pytest.raises(ValueError, match="transform must be 'remove' or None"):
        ParameterRemove(old_name="old_name", transform="invalid")


def test_parameter_rename_invalid_transform():
    with pytest.raises(ValueError, match="transform must be 'reassign' or None"):
        ParameterRename(old_name="old_name", new_name="new_name", transform="invalid")


def test_deprecated_parameters_decorator_positional_only():
    with pytest.raises(TypeError, match="deprecated_parameters.. got an unexpected keyword argument"):

        @deprecated_parameters(deprecations=[])
        def func_positional_only():
            pass


def test_deprecated_parameters_decorator_empty():
    with pytest.raises(ValueError, match="At least one deprecation must be provided"):

        @deprecated_parameters()
        def func_decorator_empty():
            pass


def test_deprecated_parameters_decorator_multiple():
    with pytest.raises(ValueError, match="@deprecated_parameters decorator can only be applied once per callable"):

        @deprecated_parameters(
            ParameterRemove(old_name="old_name"),
        )
        @deprecated_parameters(
            ParameterRename(old_name="old_name", new_name="new_name"),
        )
        def func_decorator_multiple(new_name: str):
            pass


def test_deprecated_parameters_rename_missing_new():
    with pytest.raises(ValueError, match="Parameter 'new_name' not found in signature of"):

        @deprecated_parameters(
            ParameterRename(old_name="old_name", new_name="new_name"),
        )
        def func_decorator_rename_missing_new():
            pass


@deprecated_parameters(
    ParameterRemove(old_name="removed"),
)
def func_keyword_parameter_remove():
    pass


def test_func_keyword_parameter_remove():
    with warnings.catch_warnings(record=True) as w:
        func_keyword_parameter_remove(removed=1)
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "removed" for "func_keyword_parameter_remove" is deprecated,' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        func_keyword_parameter_remove()
    assert len(w) == 0


@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
def func_keyword_parameter_rename(*, now: int):
    return now


def test_func_keyword_parameter_rename():
    with warnings.catch_warnings(record=True) as w:
        assert func_keyword_parameter_rename(before=7) == 7
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "before" for "func_keyword_parameter_rename" is deprecated' in str(w[-1].message)
    assert 'it has been renamed to "now" and "before" will no longer be accepted in the future' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        assert func_keyword_parameter_rename(now=6) == 6
    assert len(w) == 0


def test_func_keyword_parameter_rename_old_and_new_given():
    with pytest.raises(ValueError, match="Unable to reassign 'before' because 'now' is also set"):
        with warnings.catch_warnings(record=True) as w:
            func_keyword_parameter_rename(before=5, now=6)
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "before" for "func_keyword_parameter_rename" is deprecated' in str(w[-1].message)


class KeywordParameterRemove:
    @deprecated_parameters(
        ParameterRemove(old_name="removed"),
    )
    def method_keyword_parameter_remove(self):
        pass


def test_method_keyword_parameter_remove():
    instance = KeywordParameterRemove()

    with warnings.catch_warnings(record=True) as w:
        instance.method_keyword_parameter_remove(removed=1)
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "removed" for "method_keyword_parameter_remove" is deprecated' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        instance.method_keyword_parameter_remove()
    assert len(w) == 0


class KeywordParameterRename:
    @deprecated_parameters(
        ParameterRename(old_name="before", new_name="now"),
    )
    def method_keyword_parameter_rename(self, *, now: int):
        return now


def test_method_keyword_parameter_rename():
    instance = KeywordParameterRename()

    with warnings.catch_warnings(record=True) as w:
        assert instance.method_keyword_parameter_rename(before=9) == 9
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "before" for "method_keyword_parameter_rename" is deprecated' in str(w[-1].message)
    assert 'it has been renamed to "now" and "before" will no longer be accepted in the future' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        assert instance.method_keyword_parameter_rename(now=8) == 8
    assert len(w) == 0


# Warnings must be attributed to the caller, not to the decorator's wrapper.


@deprecated_parameters(
    ParameterRemove(old_name="removed"),
)
def func_stacklevel():
    pass


def test_warning_points_at_the_caller():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        func_stacklevel(removed=1)
    assert len(w) == 1
    assert w[0].filename == __file__
    assert w[0].lineno == test_warning_points_at_the_caller.__code__.co_firstlineno + 3


@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
def func_stacklevel_rename(*, now: int = 0):
    return now


def test_rename_warning_points_at_the_caller():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        func_stacklevel_rename(before=1)
    assert len(w) == 1
    assert w[0].filename == __file__


# The decorator must be usable on functions created more than once, e.g. defined inside a factory.


def factory():
    @deprecated_parameters(
        ParameterRemove(old_name="removed"),
    )
    def func_from_factory(**kwargs):
        return "called"

    return func_from_factory


def test_decorator_inside_factory():
    first = factory()
    second = factory()
    assert first is not second
    for func in (first, second):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            assert func(removed=1) == "called"
        assert len(w) == 1


def test_get_deprecated_parameters_distinguishes_instances():
    func = factory()
    deprecations = get_deprecated_parameters(func)
    assert deprecations is not None
    assert [x.old_name for x in deprecations.removed] == ["removed"]


def test_get_deprecated_parameters_undecorated():
    def plain():
        pass

    assert get_deprecated_parameters(plain) is None


# Classes are not supported and must be rejected instead of silently returning a function.


def test_decorator_on_class_not_supported():
    with pytest.raises(TypeError, match="can not be applied to classes"):

        @deprecated_parameters(
            ParameterRemove(old_name="removed"),
        )
        class ClassDecorated:
            def __init__(self, **kwargs):
                pass


# Async functions must remain async functions.


@deprecated_parameters(
    ParameterRemove(old_name="removed"),
)
async def func_async_remove(**kwargs):
    return "async result"


def test_async_function_identity_preserved():
    if sys.version_info >= (3, 12):
        assert inspect.iscoroutinefunction(func_async_remove)
    else:
        # Before python 3.12 a sync wrapper can not be marked for inspect.iscoroutinefunction. Only the
        # asyncio marker can be set, which is what async frameworks relied on in those versions.
        assert asyncio.iscoroutinefunction(func_async_remove)


def test_async_function_remove():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert asyncio.run(func_async_remove(removed=1)) == "async result"
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert 'Argument "removed" for "func_async_remove" is deprecated' in str(w[0].message)
    assert w[0].filename == __file__


@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
async def func_async_rename(*, now: int = 0):
    return now


def test_async_function_rename():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert asyncio.run(func_async_rename(before=3)) == 3
    assert len(w) == 1
    assert 'it has been renamed to "now"' in str(w[0].message)


def test_async_function_no_deprecated_argument():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert asyncio.run(func_async_rename(now=4)) == 4
    assert len(w) == 0


# A transform can only be applied when the old name is gone from the signature, otherwise the value
# given by the caller would be silently discarded.


def test_remove_transform_old_name_still_in_signature():
    with pytest.raises(ValueError, match="'removed' is still in the signature"):

        @deprecated_parameters(
            ParameterRemove(old_name="removed"),
        )
        def func_remove_still_present(removed=None):
            return removed


def test_remove_no_transform_old_name_still_in_signature():
    @deprecated_parameters(
        ParameterRemove(old_name="removed", transform=None),
    )
    def func_remove_kept(removed=None):
        return removed

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert func_remove_kept(removed=7) == 7
    assert len(w) == 1


def test_rename_transform_old_name_still_in_signature():
    with pytest.raises(ValueError, match="'before' is still in the signature"):

        @deprecated_parameters(
            ParameterRename(old_name="before", new_name="now"),
        )
        def func_rename_still_present(before=None, now=None):
            return before, now


def caught(func, *args, **kwargs):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = func(*args, **kwargs)
    return result, w


# ---------------------------------------------------------------- ParameterPositional


@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1, when="v2.0.0"),
)
def func_positional_keyword(data, *, workers: int = 1):
    return data, workers


def test_positional_transform_rescues_old_callers():
    result, w = caught(func_positional_keyword, [1], 4)
    assert result == ([1], 4)
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert 'Giving argument "workers" for "func_positional_keyword" positionally is deprecated' in str(w[0].message)
    assert "must be given as a keyword argument in v2.0.0" in str(w[0].message)
    assert w[0].filename == __file__


def test_positional_keyword_call_does_not_warn():
    result, w = caught(func_positional_keyword, [1], workers=4)
    assert result == ([1], 4)
    assert len(w) == 0


@deprecated_parameters(
    ParameterPositional(name="b", old_index=2, when="v2.0.0"),
    ParameterPositional(name="a", old_index=1, when="v2.0.0"),
)
def func_positional_multiple(data, *, a=None, b=None):
    return data, a, b


def test_positional_multiple_in_declaration_order():
    result, w = caught(func_positional_multiple, [1], "A", "B")
    assert result == ([1], "A", "B")
    assert len(w) == 2


@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1, transform=None, when="v2.0.0"),
)
def func_positional_no_transform(data, workers: int = 1):
    return data, workers


def test_positional_no_transform_warns_but_still_positional():
    result, w = caught(func_positional_no_transform, [1], 4)
    assert result == ([1], 4)
    assert len(w) == 1
    result, w = caught(func_positional_no_transform, [1], workers=4)
    assert len(w) == 0


def test_positional_transform_requires_keyword_only():
    with pytest.raises(ValueError, match="must be keyword-only"):

        @deprecated_parameters(ParameterPositional(name="workers", old_index=1))
        def func(data, workers=1):
            return workers


def test_positional_no_transform_requires_positional():
    with pytest.raises(ValueError, match="must be positional"):

        @deprecated_parameters(ParameterPositional(name="workers", old_index=1, transform=None))
        def func(data, *, workers=1):
            return workers


def test_positional_unknown_parameter():
    with pytest.raises(ValueError, match="'nope' not found in signature"):

        @deprecated_parameters(ParameterPositional(name="nope", old_index=1))
        def func(data):
            return data


# ---------------------------------------------------------------- ParameterValueRemove


@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo", when="v2.0.0"),
)
def func_value(data, *, method="new_algo"):
    return method


def test_value_replaced():
    result, w = caught(func_value, [1], method="old_algo")
    assert result == "new_algo"
    assert len(w) == 1
    assert 'Value \'old_algo\' for argument "method" of "func_value" is deprecated' in str(w[0].message)
    assert "use 'new_algo' instead" in str(w[0].message)
    assert "will not be supported in v2.0.0" in str(w[0].message)
    assert w[0].filename == __file__


def test_value_not_deprecated_does_not_warn():
    result, w = caught(func_value, [1], method="new_algo")
    assert result == "new_algo"
    assert len(w) == 0


def test_value_omitted_does_not_warn():
    result, w = caught(func_value, [1])
    assert result == "new_algo"
    assert len(w) == 0


@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="legacy", transform=None, when="v2.0.0"),
)
def func_value_no_replacement(data, method="legacy"):
    return method


def test_value_no_transform_keeps_value():
    result, w = caught(func_value_no_replacement, [1], method="legacy")
    assert result == "legacy"
    assert len(w) == 1
    assert "use" not in str(w[0].message)


def test_value_given_positionally_is_detected():
    result, w = caught(func_value_no_replacement, [1], "legacy")
    assert result == "legacy"
    assert len(w) == 1


@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old", new_value="new"),
)
def func_value_positional_replace(data, method="new"):
    return method


def test_value_replaced_when_given_positionally():
    result, w = caught(func_value_positional_replace, [1], "old")
    assert result == "new"
    assert len(w) == 1


def test_value_without_new_value_only_warns():
    # Nothing to replace with, so the transform has nothing to do and does not need to be disabled.
    @deprecated_parameters(ParameterValueRemove(name="method", old_value="old"))
    def func(data, *, method="new"):
        return method

    result, w = caught(func, [1], method="old")
    assert result == "old"
    assert len(w) == 1
    assert "use" not in str(w[0].message)


def test_value_without_new_value_and_no_transform_is_the_same():
    @deprecated_parameters(ParameterValueRemove(name="method", old_value="old", transform=None))
    def func(data, *, method="new"):
        return method

    result, w = caught(func, [1], method="old")
    assert result == "old"
    assert len(w) == 1


def test_value_with_new_value_but_no_transform_keeps_the_value():
    @deprecated_parameters(
        ParameterValueRemove(name="method", old_value="old", new_value="new", transform=None),
    )
    def func(data, *, method="new"):
        return method

    result, w = caught(func, [1], method="old")
    assert result == "old"
    assert len(w) == 1
    assert "use 'new' instead" in str(w[0].message)


def test_value_unknown_parameter():
    with pytest.raises(ValueError, match="'nope' not found in signature"):

        @deprecated_parameters(ParameterValueRemove(name="nope", old_value=1, new_value=2))
        def func(data):
            return data


def test_value_comparison_does_not_explode_on_odd_eq():
    class Odd:
        def __eq__(self, other):
            raise RuntimeError("nope")

    @deprecated_parameters(ParameterValueRemove(name="method", old_value="old", new_value="new"))
    def func(data, *, method="new"):
        return method

    result, w = caught(func, [1], method=Odd())
    assert len(w) == 0


# ---------------------------------------------------------------- version


@deprecated_parameters(
    ParameterRemove(old_name="verbose", version="1.5.0", when="v2.0.0"),
)
def func_with_version(data, **kwargs):
    return data


def test_version_included_in_message():
    _, w = caught(func_with_version, [1], verbose=True)
    assert len(w) == 1
    assert 'Argument "verbose" for "func_with_version" is deprecated since 1.5.0' in str(w[0].message)


def test_version_available_in_custom_message():
    @deprecated_parameters(
        ParameterRemove(old_name="verbose", version="1.5.0", message="%(old_name)s gone in %(version)s"),
    )
    def func(data, **kwargs):
        return data

    _, w = caught(func, [1], verbose=True)
    assert str(w[0].message) == "verbose gone in 1.5.0"


def test_invalid_version_rejected():
    with pytest.raises(ValueError, match="not a valid PEP 440 version"):
        ParameterRemove(old_name="verbose", version="not a version")


def test_version_with_leading_v_accepted():
    ParameterRemove(old_name="verbose", version="v1.5.0")


def test_no_version_keeps_message_unchanged():
    @deprecated_parameters(ParameterRemove(old_name="verbose"))
    def func(data, **kwargs):
        return data

    _, w = caught(func, [1], verbose=True)
    assert "is deprecated, its value is ignored and it will no longer be accepted in the future" in str(w[0].message)


# ---------------------------------------------------------------- category


def test_custom_category():
    @deprecated_parameters(
        ParameterRemove(old_name="verbose", category=FutureWarning),
    )
    def func(data, **kwargs):
        return data

    _, w = caught(func, [1], verbose=True)
    assert len(w) == 1
    assert issubclass(w[0].category, FutureWarning)


def test_category_must_be_warning_subclass():
    with pytest.raises(TypeError, match="category must be a Warning subclass"):
        ParameterRemove(old_name="verbose", category=int)


def test_category_per_deprecation():
    @deprecated_parameters(
        ParameterRemove(old_name="a", category=FutureWarning),
        ParameterRemove(old_name="b"),
    )
    def func(data, **kwargs):
        return data

    _, w = caught(func, [1], a=1, b=2)
    assert [x.category for x in w] == [FutureWarning, DeprecationWarning]


# ---------------------------------------------------------------- positional detection for removals


@deprecated_parameters(
    ParameterRemove(old_name="verbose", transform=None),
)
def func_remove_positional(data, verbose=False):
    return verbose


def test_removal_detected_when_given_positionally():
    result, w = caught(func_remove_positional, [1], True)
    assert result is True
    assert len(w) == 1


# ---------------------------------------------------------------- introspection


def test_get_deprecated_parameters_exposes_all_kinds():
    @deprecated_parameters(
        ParameterRemove(old_name="r"),
        ParameterRename(old_name="o", new_name="n"),
        ParameterPositional(name="p", old_index=1),
        ParameterValueRemove(name="v", old_value=1, new_value=2),
    )
    def func(data, *, n=None, p=None, v=2, **kwargs):
        return data

    deprecations = get_deprecated_parameters(func)
    assert [x.old_name for x in deprecations.removed] == ["r"]
    assert [x.old_name for x in deprecations.renamed] == ["o"]
    assert [x.name for x in deprecations.positional] == ["p"]
    assert [x.name for x in deprecations.values] == ["v"]


# The position a parameter used to have is given explicitly, rather than inferred from the order in
# which the deprecations happen to be declared.


def test_positional_multiple_uses_old_index_not_declaration_order():
    # Declared b before a, but the indices decide which argument goes where.
    result, w = caught(func_positional_multiple, [1], "A", "B")
    assert result == ([1], "A", "B")
    assert len(w) == 2


def test_positional_old_index_is_required():
    with pytest.raises(TypeError, match="missing 1 required keyword-only argument: 'old_index'"):
        ParameterPositional(name="workers")


def test_positional_old_index_must_be_a_non_negative_int():
    with pytest.raises(ValueError, match="old_index must be a non-negative integer"):
        ParameterPositional(name="workers", old_index=-1)


def test_positional_old_index_must_follow_the_remaining_positionals():
    with pytest.raises(ValueError, match=r"must be \[1\], got \[2\]"):

        @deprecated_parameters(ParameterPositional(name="workers", old_index=2))
        def func(data, *, workers=1):
            return workers


def test_positional_old_index_must_be_contiguous():
    with pytest.raises(ValueError, match=r"must be \[1, 2\], got \[1, 3\]"):

        @deprecated_parameters(
            ParameterPositional(name="a", old_index=1),
            ParameterPositional(name="b", old_index=3),
        )
        def func(data, *, a=None, b=None):
            return a, b


def test_positional_old_index_counts_self_for_methods():
    class Cls:
        @deprecated_parameters(ParameterPositional(name="workers", old_index=2))
        def method(self, data, *, workers=1):
            return workers

    instance = Cls()
    result, w = caught(instance.method, [1], 4)
    assert result == 4
    assert len(w) == 1


def test_positional_old_index_error_names_what_is_expected_for_methods():
    with pytest.raises(ValueError, match=r"must be \[2\], got \[1\]"):

        class Cls:
            @deprecated_parameters(ParameterPositional(name="workers", old_index=1))
            def method(self, data, *, workers=1):
                return workers


def test_positional_no_transform_old_index_must_match_the_signature():
    with pytest.raises(ValueError, match="old_index for 'workers' must be 1"):

        @deprecated_parameters(ParameterPositional(name="workers", old_index=2, transform=None))
        def func(data, workers=1):
            return workers


def test_positional_extra_arguments_still_fail():
    with pytest.raises(TypeError):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            func_positional_keyword([1], 4, "unexpected")


# ---------------------------------------------------------------- messages


def test_remove_message_says_the_value_is_ignored():
    @deprecated_parameters(ParameterRemove(old_name="verbose", when="v2.0.0"))
    def func(data):
        return data

    _, w = caught(func, [1], verbose=True)
    assert str(w[0].message) == (
        'Argument "verbose" for "func" is deprecated, its value is ignored and it will no longer be accepted in v2.0.0'
    )


def test_remove_message_without_transform_does_not_say_ignored():
    @deprecated_parameters(ParameterRemove(old_name="verbose", transform=None, when="v2.0.0"))
    def func(data, verbose=False):
        return verbose

    _, w = caught(func, [1], verbose=True)
    assert str(w[0].message) == 'Argument "verbose" for "func" is deprecated and will no longer be accepted in v2.0.0'


def test_rename_message_says_no_longer_accepted():
    @deprecated_parameters(ParameterRename(old_name="n_jobs", new_name="workers", when="v2.0.0"))
    def func(data, *, workers=1):
        return workers

    _, w = caught(func, [1], n_jobs=4)
    assert str(w[0].message) == (
        'Argument "n_jobs" for "func" is deprecated, it has been renamed to "workers" and "n_jobs" will '
        "no longer be accepted in v2.0.0"
    )


def test_remove_message_includes_the_version():
    @deprecated_parameters(ParameterRemove(old_name="verbose", version="1.5.0", when="v2.0.0"))
    def func(data):
        return data

    _, w = caught(func, [1], verbose=True)
    assert str(w[0].message) == (
        'Argument "verbose" for "func" is deprecated since 1.5.0, its value is ignored and it will no '
        "longer be accepted in v2.0.0"
    )


def test_remove_custom_message_is_used_as_given():
    @deprecated_parameters(ParameterRemove(old_name="verbose", message="%(old_name)s is gone from %(func)s"))
    def func(data):
        return data

    _, w = caught(func, [1], verbose=True)
    assert str(w[0].message) == "verbose is gone from func"


# ---------------------------------------------------------------- transform=None needs a landing place


def test_remove_no_transform_without_landing_place_fails():
    with pytest.raises(ValueError, match="'verbose' is not in the signature of func and there is no"):

        @deprecated_parameters(ParameterRemove(old_name="verbose", transform=None))
        def func(data):
            return data


def test_remove_no_transform_accepts_var_keyword_as_landing_place():
    @deprecated_parameters(ParameterRemove(old_name="verbose", transform=None))
    def func(data, **kwargs):
        return kwargs

    result, w = caught(func, [1], verbose=True)
    assert result == {"verbose": True}
    assert len(w) == 1


def test_rename_no_transform_without_landing_place_fails():
    with pytest.raises(ValueError, match="'n_jobs' is not in the signature of func and there is no"):

        @deprecated_parameters(ParameterRename(old_name="n_jobs", new_name="workers", transform=None))
        def func(data, *, workers=1):
            return workers


def test_remove_with_transform_drops_it_even_when_there_is_var_keyword():
    @deprecated_parameters(ParameterRemove(old_name="verbose"))
    def func(data, **kwargs):
        return kwargs

    result, w = caught(func, [1], verbose=True)
    assert result == {}
    assert len(w) == 1


# ---------------------------------------------------------------- removals given positionally


# The old signature was compute(data, workers, verbose), so verbose was at index 2.
@deprecated_parameters(
    ParameterRemove(old_name="verbose", old_index=2, when="v2.0.0"),
)
def func_remove_old_index(data, workers=1):
    return data, workers


def test_remove_old_index_drops_the_positional_argument():
    result, w = caught(func_remove_old_index, [1], 4, True)
    assert result == ([1], 4)
    assert len(w) == 1
    assert "its value is ignored" in str(w[0].message)


def test_remove_old_index_leaves_a_current_call_alone():
    result, w = caught(func_remove_old_index, [1], 4)
    assert result == ([1], 4)
    assert len(w) == 0


def test_remove_old_index_still_detects_the_keyword_form():
    result, w = caught(func_remove_old_index, [1], verbose=True)
    assert result == ([1], 1)
    assert len(w) == 1


def test_remove_old_index_must_be_the_last_positional_of_the_old_signature():
    # verbose was in the middle of the old signature, compute(data, verbose, workers), so an argument
    # given for it can not be told apart from one given for workers.
    with pytest.raises(ValueError, match=r"must be \[2\], got \[1\]"):

        @deprecated_parameters(ParameterRemove(old_name="verbose", old_index=1))
        def func(data, workers=1):
            return data, workers


def test_remove_old_index_must_follow_the_remaining_positionals():
    with pytest.raises(ValueError, match=r"must be \[1\], got \[2\]"):

        @deprecated_parameters(ParameterRemove(old_name="verbose", old_index=2))
        def func(data):
            return data


def test_remove_old_index_must_be_a_non_negative_int():
    with pytest.raises(ValueError, match="old_index must be a non-negative integer"):
        ParameterRemove(old_name="verbose", old_index=-1)


def test_remove_old_index_shares_the_block_with_positional_deprecations():
    @deprecated_parameters(
        ParameterRemove(old_name="verbose", old_index=2),
        ParameterPositional(name="workers", old_index=1),
    )
    def func(data, *, workers=1):
        return data, workers

    result, w = caught(func, [1], 4, True)
    assert result == ([1], 4)
    assert len(w) == 2


def test_remove_old_index_block_must_be_contiguous():
    with pytest.raises(ValueError, match=r"must be \[1, 2\], got \[1, 3\]"):

        @deprecated_parameters(
            ParameterRemove(old_name="verbose", old_index=3),
            ParameterPositional(name="workers", old_index=1),
        )
        def func(data, *, workers=1):
            return data, workers


def test_remove_old_index_counts_self_for_methods():
    class Cls:
        @deprecated_parameters(ParameterRemove(old_name="verbose", old_index=2))
        def method(self, data):
            return data

    result, w = caught(Cls().method, [1], True)
    assert result == [1]
    assert len(w) == 1


def test_remove_no_transform_old_index_must_match_the_signature():
    with pytest.raises(ValueError, match="old_index for 'verbose' must be 1"):

        @deprecated_parameters(ParameterRemove(old_name="verbose", old_index=2, transform=None))
        def func(data, verbose=False):
            return verbose


def test_remove_no_transform_old_index_requires_a_positional_parameter():
    with pytest.raises(ValueError, match="must be positional in the signature"):

        @deprecated_parameters(ParameterRemove(old_name="verbose", old_index=1, transform=None))
        def func(data, **kwargs):
            return kwargs


def test_remove_old_index_extra_arguments_still_fail():
    with pytest.raises(TypeError):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            func_remove_old_index([1], 4, True, "unexpected")
