# Changelog

All notable changes to this project will be documented in this file. Versions
follow [Semantic Versioning](https://semver.org/) (`<major>.<minor>.<patch>`)
and adhere to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## v0.1.0 (unreleased)

### Added

- `deprecated_parameters` decorator to mark parameters of functions and methods
  as deprecated, accepting any number of deprecations and issuing a
  `DeprecationWarning` attributed to the caller when a deprecated argument is
  given.
- `ParameterRemove` to declare a parameter that is gone from the signature. By
  default the argument is dropped from the call, so that old callers get a
  warning instead of a `TypeError`, and the warning states that the value they
  give is ignored. An optional `old_index` gives the position the parameter had,
  so that callers still giving it positionally are rescued as well.
- `ParameterRename` to declare a parameter that has been renamed. By default the
  argument is reassigned to the new name, and giving both names in the same call
  raises a `ValueError`.
- `transform` parameter, which adapts a call that uses the deprecated form to a
  signature that is already written the way it will stay, or `None` to leave the
  call untouched and only warn, for a signature that has not changed yet.
- Validation when the decorator is applied, rejecting deprecations that are
  inconsistent with the signature, such as a transform that would silently
  discard the value given by the caller, or a `transform=None` for a parameter
  that neither the signature nor a `**kwargs` can receive.
- Customization of the reported message through the `when` and `message`
  parameters.
- `get_deprecated_parameters` to introspect the deprecations of a callable.
- `mypy_plugin` to report the use of deprecated parameters statically, under the
  `deprecated-arg` error code, for functions, methods and constructors, both in
  the module where they are declared and in modules that import them. The
  signature is widened so that a deprecated form is not additionally reported as
  an unexpected keyword argument or as too many positional arguments, and a
  renamed parameter keeps the type of the parameter it was renamed to.
- `ParameterPositional` to declare a parameter that is no longer accepted
  positionally. By default the argument is moved to its keyword, so that old
  callers get a warning instead of a `TypeError`. The position the parameter had
  is given explicitly as `old_index` and validated against the signature.
- `ParameterValueRemove` to remove a single value from the set a parameter
  accepts, leaving the parameter itself in place. By default the value is
  replaced with `new_value`, and the signature is widened so that dropping the
  value from the annotation is not reported as an incompatible argument type.
- `version` parameter recording the release in which a parameter was deprecated,
  validated as a PEP 440 version, reported as `deprecated since <version>` and
  available to custom messages as `%(version)s`.
- `category` parameter to choose the warning class per deprecation, for example
  `FutureWarning` for deprecations aimed at the users of a library.
- Detection of deprecated parameters and values given positionally, not only as
  keyword arguments.
- Support for coroutine functions, warning when the coroutine is created so that
  the warning points at the caller.
- Documentation of the deprecations as `.. deprecated::` directives appended to
  the docstring, one per deprecation, which happens only while sphinx is
  building and therefore needs nothing to be enabled.
- `generate_stub`, which renders the declared deprecations as PEP 702
  `@overload` plus `@deprecated` declarations, so that type checkers without a
  plugin system, such as pyright, ty and pyrefly, report them too. Also
  available as the `deprecated-parameters-stubgen` command.
- `example` directory with a library that uses every kind of deprecation once, runnable to see
  the warnings, checkable with mypy and buildable with sphinx to see the documented
  deprecations.
- `README.md` and this changelog.
