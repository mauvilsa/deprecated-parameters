from importlib.util import find_spec
from typing import Any, Callable, List, Optional, Union

from ._decorator import (
    ParameterDeprecation,
    ParameterPositional,
    ParameterRemove,
    ParameterRename,
    ParameterValueRemove,
    _rescued_positional,
    deprecated_parameters,
    unset,
)

__all__ = [
    "mypy_plugin",
]

decorator_fullname = f"{deprecated_parameters.__module__}.{deprecated_parameters.__qualname__}"

deprecation_classes = {
    "ParameterRemove": ParameterRemove,
    "ParameterRename": ParameterRename,
    "ParameterPositional": ParameterPositional,
    "ParameterValueRemove": ParameterValueRemove,
}


if find_spec("mypy"):
    from mypy.errorcodes import ErrorCode
    from mypy.nodes import (
        ARG_NAMED,
        ARG_NAMED_OPT,
        ARG_OPT,
        ARG_POS,
        ARG_STAR,
        ARG_STAR2,
        BytesExpr,
        CallExpr,
        ComplexExpr,
        Decorator,
        Expression,
        FloatExpr,
        IntExpr,
        NameExpr,
        StrExpr,
        TypeInfo,
        UnaryExpr,
    )
    from mypy.plugin import FunctionSigContext, MethodSigContext, Plugin
    from mypy.types import AnyType, CallableType, FunctionLike, LiteralType, NoneType, Type, TypeOfAny, UnionType

    DEPRECATED_ARG = ErrorCode("deprecated-arg", "Check number, names and kinds of arguments in calls", "Deprecations")

    named_kinds = (ARG_NAMED, ARG_NAMED_OPT)
    positional_kinds = (ARG_POS, ARG_OPT)

    def literal_value(expression: Optional[Expression]) -> Any:
        """Python value of a literal expression, or unset when it is not a literal."""
        if isinstance(expression, (StrExpr, BytesExpr, IntExpr, FloatExpr, ComplexExpr)):
            return expression.value
        if isinstance(expression, NameExpr):
            return {"builtins.True": True, "builtins.False": False, "builtins.None": None}.get(
                expression.fullname or "", unset
            )
        if isinstance(expression, UnaryExpr) and expression.op == "-":
            operand = literal_value(expression.expr)
            return unset if operand is unset else -operand
        return unset

    def build_deprecation(call: CallExpr) -> Optional[ParameterDeprecation]:
        """Rebuild a deprecation instance from its call expression, to render the very same message."""
        name = getattr(call.callee, "name", None)
        cls = deprecation_classes.get(name or "")
        if cls is None:
            return None
        kwargs = {}
        for argument, argument_name in zip(call.args, call.arg_names):
            if argument_name is None:
                return None  # the deprecation classes are keyword-only, so this does not type check anyway
            value = literal_value(argument)
            if value is unset:
                if argument_name in ("old_value", "new_value"):
                    return None  # can not be compared against, so the deprecation is not checkable
                continue  # e.g. category, which does not take part in the message
            kwargs[argument_name] = value
        try:
            return cls(**kwargs)
        except (TypeError, ValueError):
            return None

    def get_deprecations(decorator: CallExpr) -> List[ParameterDeprecation]:
        deprecations = []
        for argument in decorator.args:
            if isinstance(argument, CallExpr):
                deprecation = build_deprecation(argument)
                if deprecation is not None:
                    deprecations.append(deprecation)
        return deprecations

    def insert_argument(signature: CallableType, name: str, kind, arg_type: Type, index: int) -> CallableType:
        return signature.copy_modified(
            arg_kinds=[*signature.arg_kinds[:index], kind, *signature.arg_kinds[index:]],
            arg_names=[*signature.arg_names[:index], name, *signature.arg_names[index:]],
            arg_types=[*signature.arg_types[:index], arg_type, *signature.arg_types[index:]],
        )

    def end_of_positional(signature: CallableType) -> int:
        """Index just after the leading positional arguments, before any *args, **kwargs or named ones."""
        index = 0
        for kind in signature.arg_kinds:
            if kind not in positional_kinds:
                break
            index += 1
        return index

    def add_deprecated_argument(signature: CallableType, name: str, type_of: Optional[str]) -> CallableType:
        """Add a deprecated name to a signature, so that it is not also reported as unexpected."""
        if name in signature.arg_names:
            return signature
        arg_type: Type = AnyType(TypeOfAny.special_form)
        if type_of is not None and type_of in signature.arg_names:
            arg_type = signature.arg_types[signature.arg_names.index(type_of)]
        # Keep *args and **kwargs last, as mypy expects them to be.
        index = len(signature.arg_kinds)
        for position, kind in enumerate(signature.arg_kinds):
            if kind in (ARG_STAR, ARG_STAR2):
                index = position
                break
        return insert_argument(signature, name, ARG_NAMED_OPT, arg_type, index)

    def add_positional_argument(signature: CallableType, name: str) -> CallableType:
        """Add a name that is no longer in the signature to its positional part, for a removed parameter."""
        if name in signature.arg_names:
            return signature
        arg_type: Type = AnyType(TypeOfAny.special_form)
        return insert_argument(signature, name, ARG_OPT, arg_type, end_of_positional(signature))

    def allow_positional(signature: CallableType, name: str) -> CallableType:
        """Move a keyword-only argument to the positional section, keeping its type."""
        if name not in signature.arg_names:
            return signature
        index = signature.arg_names.index(name)
        if signature.arg_kinds[index] not in named_kinds:
            return signature
        arg_type = signature.arg_types[index]
        without = signature.copy_modified(
            arg_kinds=[*signature.arg_kinds[:index], *signature.arg_kinds[index + 1 :]],
            arg_names=[*signature.arg_names[:index], *signature.arg_names[index + 1 :]],
            arg_types=[*signature.arg_types[:index], *signature.arg_types[index + 1 :]],
        )
        return insert_argument(without, name, ARG_OPT, arg_type, end_of_positional(without))

    #: Types whose values can be expressed as a Literal, and the instance backing them.
    literal_fallbacks = {
        str: "builtins.str",
        bytes: "builtins.bytes",
        bool: "builtins.bool",
        int: "builtins.int",
    }

    def as_type(api, value: Any) -> Optional[Type]:
        """Type matching a single python value, to widen a signature with it."""
        if value is None:
            return NoneType()
        # bool before int, since bool is a subclass of it, hence the exact type lookup.
        fallback = literal_fallbacks.get(type(value))
        if fallback is None:
            return None  # e.g. a float, which the type system has no literal for
        return LiteralType(value, api.named_generic_type(fallback, []))

    def allow_deprecated_value(signature: CallableType, api, name: str, old_value: Any) -> CallableType:
        """Widen the type of an argument with a deprecated value, which the signature may have dropped."""
        if name not in signature.arg_names:
            return signature
        value_type = as_type(api, old_value)
        if value_type is None:
            return signature
        index = signature.arg_names.index(name)
        widened = UnionType.make_union([signature.arg_types[index], value_type])
        return signature.copy_modified(
            arg_types=[*signature.arg_types[:index], widened, *signature.arg_types[index + 1 :]],
        )

    def call_arguments(context) -> tuple:
        """Names and expressions of a call, and how many arguments were given positionally."""
        names = list(getattr(context, "arg_names", []) or [])
        args = list(getattr(context, "args", []) or [])
        kinds = list(getattr(context, "arg_kinds", []) or [])
        num_positional = sum(1 for kind in kinds if kind == ARG_POS)
        return names, args, num_positional

    def given_expression(names: list, args: list, name: str, index: Optional[int]) -> Optional[Expression]:
        """Expression given for a parameter, by keyword or at a positional index."""
        if name in names:
            return args[names.index(name)]
        if index is not None and index < len(args) and names[index] is None:
            return args[index]
        return None

    def signature_hook(
        ctx: Union[FunctionSigContext, MethodSigContext],
        deprecations: List[ParameterDeprecation],
        func_name: str,
    ) -> FunctionLike:
        signature = ctx.default_signature
        if not isinstance(signature, CallableType):
            return signature
        names, args, num_positional = call_arguments(ctx.context)

        # The parameters that left the positional part of the signature, either removed or now
        # keyword-only. Widened in old_index order, so that the arguments end up back in the positions
        # the caller used.
        for rescued in _rescued_positional(deprecations):
            if isinstance(rescued, ParameterPositional):
                signature = allow_positional(signature, rescued.name)
            else:
                signature = add_positional_argument(signature, rescued.name)
            if rescued.old_index < num_positional:
                ctx.api.fail(rescued.format(func_name), ctx.context, code=DEPRECATED_ARG)

        for deprecation in deprecations:
            if isinstance(deprecation, (ParameterRemove, ParameterRename)):
                type_of = deprecation.new_name if isinstance(deprecation, ParameterRename) else None
                if deprecation.old_name in names:
                    ctx.api.fail(deprecation.format(func_name), ctx.context, code=DEPRECATED_ARG)
                signature = add_deprecated_argument(signature, deprecation.old_name, type_of)

            elif isinstance(deprecation, ParameterPositional) and deprecation.transform is None:
                if deprecation.old_index < num_positional:
                    ctx.api.fail(deprecation.format(func_name), ctx.context, code=DEPRECATED_ARG)

            elif isinstance(deprecation, ParameterValueRemove):
                index = signature.arg_names.index(deprecation.name) if deprecation.name in signature.arg_names else None
                expression = given_expression(names, args, deprecation.name, index)
                value = literal_value(expression)
                if value is not unset and type(value) is type(deprecation.old_value) and value == deprecation.old_value:
                    ctx.api.fail(deprecation.format(func_name), ctx.context, code=DEPRECATED_ARG)
                signature = allow_deprecated_value(signature, ctx.api, deprecation.name, deprecation.old_value)

        return signature

    class MypyDeprecatedParametersPlugin(Plugin):
        """A mypy plugin to check for deprecated parameters in functions and methods."""

        def get_deprecations(self, fullname: str) -> Optional[List[ParameterDeprecation]]:
            """Return the deprecations declared for a callable, or None if it has none."""
            symbol = self.lookup_fully_qualified(fullname)
            node = symbol.node if symbol else None
            if isinstance(node, TypeInfo):
                # A call to a class is a call to its __init__, though reported with the name of the class.
                init = node.names.get("__init__")
                node = init.node if init else None
            if not isinstance(node, Decorator):
                return None
            decorators = [
                d
                for d in getattr(node, "original_decorators", [])
                if isinstance(d, CallExpr) and getattr(d.callee, "fullname", None) == decorator_fullname
            ]
            if not decorators:
                return None
            return get_deprecations(decorators[0]) or None

        def get_signature_hook(self, fullname: str):
            deprecations = self.get_deprecations(fullname)
            if not deprecations:
                return None
            func_name = fullname.rsplit(".", 1)[-1]
            return lambda ctx: signature_hook(ctx, deprecations, func_name)

        def get_function_signature_hook(self, fullname: str) -> Optional[Callable[[FunctionSigContext], FunctionLike]]:
            return self.get_signature_hook(fullname)

        def get_method_signature_hook(self, fullname: str) -> Optional[Callable[[MethodSigContext], FunctionLike]]:
            return self.get_signature_hook(fullname)


def mypy_plugin(version: str):
    return MypyDeprecatedParametersPlugin
