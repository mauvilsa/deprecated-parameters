from importlib.util import find_spec
from typing import Callable, Optional, Union

from ._decorator import default_remove_message, default_rename_message, default_when, deprecated_parameters

__all__ = [
    "mypy_plugin",
]

decorator_fullname = f"{deprecated_parameters.__module__}.{deprecated_parameters.__qualname__}"


if find_spec("mypy"):
    from mypy.errorcodes import ErrorCode
    from mypy.nodes import CallExpr, Decorator, TypeInfo
    from mypy.plugin import FunctionSigContext, MethodSigContext, Plugin
    from mypy.types import FunctionLike

    DEPRECATED_ARG = ErrorCode("deprecated-arg", "Check number, names and kinds of arguments in calls", "Deprecations")

    def get_deprecation_value(deprecation: CallExpr, arg_name: str, default=None):
        for value, name in zip(deprecation.args, deprecation.arg_names):
            if name == arg_name:
                assert hasattr(value, "value")
                return value.value
        return default

    def signature_hook(ctx: Union[FunctionSigContext, MethodSigContext]) -> FunctionLike:
        if not hasattr(ctx.context, "callee") or not hasattr(ctx.context.callee, "node"):
            return ctx.default_signature

        if isinstance(ctx.context.callee.node, Decorator):
            decorators = getattr(ctx.context.callee.node, "original_decorators", [])
        elif isinstance(ctx.context.callee.node, TypeInfo) and "__init__" in ctx.context.callee.node.names:
            decorators = getattr(ctx.context.callee.node.names["__init__"].node, "original_decorators", [])
        else:
            return ctx.default_signature

        if any(d.callee.fullname == decorator_fullname for d in decorators):
            assert hasattr(ctx.context, "arg_names")
            decorator = next(d for d in decorators if d.callee.fullname == decorator_fullname)
            for deprecation in decorator.args:
                if deprecation.callee.name == "ParameterRemove":
                    old_name = get_deprecation_value(deprecation, "old_name")
                    if old_name in ctx.context.arg_names:
                        message = get_deprecation_value(deprecation, "message", default_remove_message)
                        when = get_deprecation_value(deprecation, "when", default_when)
                        ctx.api.fail(
                            message % {"func": ctx.context.callee.name, "old_name": old_name, "when": when},
                            ctx.context,
                            code=DEPRECATED_ARG,
                        )
                elif deprecation.callee.name == "ParameterRename":
                    old_name = get_deprecation_value(deprecation, "old_name")
                    if old_name in ctx.context.arg_names:
                        message = get_deprecation_value(deprecation, "message", default_rename_message)
                        when = get_deprecation_value(deprecation, "when", default_when)
                        new_name = get_deprecation_value(deprecation, "new_name")
                        ctx.api.fail(
                            message
                            % {
                                "func": ctx.context.callee.name,
                                "old_name": old_name,
                                "new_name": new_name,
                                "when": when,
                            },
                            ctx.context,
                            code=DEPRECATED_ARG,
                        )

        return ctx.default_signature

    def function_signature_hook(ctx: FunctionSigContext) -> FunctionLike:
        return signature_hook(ctx)

    def method_signature_hook(ctx: MethodSigContext) -> FunctionLike:
        return signature_hook(ctx)

    class MypyDeprecatedParametersPlugin(Plugin):
        """A mypy plugin to check for deprecated parameters in functions and methods."""

        def get_function_signature_hook(self, fullname: str) -> Optional[Callable[[FunctionSigContext], FunctionLike]]:
            return function_signature_hook

        def get_method_signature_hook(self, fullname: str) -> Optional[Callable[[MethodSigContext], FunctionLike]]:
            return method_signature_hook


def mypy_plugin(version: str):
    return MypyDeprecatedParametersPlugin
