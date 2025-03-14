from importlib.util import find_spec
from typing import Callable, Union

from ._decorator import default_remove_message, default_rename_message, default_when, deprecated_parameters

__all__ = [
    "mypy_plugin",
]

decorator_fullname = f"{deprecated_parameters.__module__}.{deprecated_parameters.__qualname__}"


if find_spec("mypy"):
    from mypy.nodes import CallExpr
    from mypy.plugin import FunctionSigContext, MethodSigContext, Plugin
    from mypy.types import FunctionLike

    def get_deprecation_value(deprecation: CallExpr, arg_name: str, default=None):
        for value, name in zip(deprecation.args, deprecation.arg_names):
            if name == arg_name:
                assert hasattr(value, "value")
                return value.value
        if default is not None:
            return default
        raise ValueError(f"Argument '{arg_name}' not found in deprecation {deprecation}.")

    def signature_hook(ctx: Union[FunctionSigContext, MethodSigContext]) -> FunctionLike:
        assert hasattr(ctx.context, "callee")
        decorators = getattr(ctx.context.callee.node, "original_decorators", [])
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
                        )

        return ctx.default_signature

    def function_signature_hook(ctx: FunctionSigContext) -> FunctionLike:
        return signature_hook(ctx)

    def method_signature_hook(ctx: MethodSigContext) -> FunctionLike:
        return signature_hook(ctx)

    class MypyDeprecatedParametersPlugin(Plugin):
        """A mypy plugin to check for deprecated parameters in functions and methods."""

        def get_function_signature_hook(self, fullname: str) -> Callable[[FunctionSigContext], FunctionLike] | None:
            return function_signature_hook

        def get_method_signature_hook(self, fullname: str) -> Callable[[MethodSigContext], FunctionLike] | None:
            return method_signature_hook


def mypy_plugin(version: str):
    return MypyDeprecatedParametersPlugin
