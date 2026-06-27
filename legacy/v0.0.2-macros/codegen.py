"""fran++ code generator: AST -> Python BFS solver."""

from parser import (
    Module, Action, Constraint, Expr,
    NumLit, StrLit, BoolLit, Ident, BinOp, UnaryOp, FuncCall,
)

I1 = "    "
I2 = "        "
I3 = "            "
I4 = "                "


class PythonCodeGen:
    def __init__(self, module: Module):
        self.module = module
        self.var_names = {v.name for v in module.variables}

    def generate(self) -> str:
        L: list[str] = []

        L.append("from collections import deque")
        L.append("")
        L.append("")
        L.append("def solve():")

        # Initial state
        pairs = ", ".join(
            f'"{v.name}": {self._py(v.initial)}'
            for v in self.module.variables
        )
        L.append(f"{I1}initial = {{{pairs}}}")
        L.append("")

        # Action functions
        for action in self.module.actions:
            fn = self._snake(action.name)
            L.append(f"{I1}def {fn}(s):")
            if action.guard:
                L.append(f"{I2}if not ({self._py_s(action.guard)}):")
                L.append(f"{I3}return None")
            updates = ", ".join(
                f'"{a.var}": {self._py_s(a.value)}'
                for a in action.assignments
            )
            L.append(f"{I2}return {{**s, {updates}}}")
            L.append("")

        # Action list
        L.append(f"{I1}all_actions = [")
        for action in self.module.actions:
            fn = self._snake(action.name)
            L.append(f'{I2}("{action.name}", {fn}),')
        L.append(f"{I1}]")
        L.append("")

        # Constraints
        if self.module.constraints:
            L.append(f"{I1}def is_valid(s):")
            checks = " and ".join(
                f'{self._py(c.low)} <= s["{c.var}"] <= {self._py(c.high)}'
                for c in self.module.constraints
            )
            L.append(f"{I2}return {checks}")
            L.append("")

        # Goal
        if self.module.goal:
            L.append(f"{I1}def is_goal(s):")
            L.append(f"{I2}return {self._py_s(self.module.goal)}")
            L.append("")

        # BFS
        valid = " and is_valid(next_state)" if self.module.constraints else ""
        L.append(f"{I1}queue = deque([(initial, [])])")
        L.append(f"{I1}visited = {{tuple(sorted(initial.items()))}}")
        L.append("")
        L.append(f"{I1}while queue:")
        L.append(f"{I2}state, path = queue.popleft()")
        # Goal check
        L.append(f"{I2}if is_goal(state):")
        L.append(        r'{0}print(f"Solution found in {{len(path)}} steps:\n")'.format(I3))
        L.append(        r'{0}desc = ", ".join(f"{{k}}={{v}}" for k, v in sorted(initial.items()))'.format(I3))
        L.append(        r'{0}print(f"  Start: {{desc}}")'.format(I3))
        L.append(f"{I3}for action_name, result in path:")
        L.append(        r'{0}desc = ", ".join(f"{{k}}={{v}}" for k, v in sorted(result.items()))'.format(I4))
        L.append(        r'{0}print(f"  {{action_name}} -> {{desc}}")'.format(I4))
        L.append(f"{I3}return")
        L.append("")
        # Explore actions
        L.append(f"{I2}for action_name, action_fn in all_actions:")
        L.append(f"{I3}next_state = action_fn(state)")
        L.append(f"{I3}if next_state is None:")
        L.append(f"{I4}continue")
        L.append(f"{I3}key = tuple(sorted(next_state.items()))")
        L.append(f"{I3}if key not in visited{valid}:")
        L.append(f"{I4}visited.add(key)")
        L.append(f"{I4}queue.append((next_state, path + [(action_name, next_state)]))")
        L.append("")
        L.append(    r'{0}print("No solution found")'.format(I1))
        L.append("")
        L.append("")
        L.append("solve()")

        return "\n".join(L) + "\n"

    # -- Expression compilers --

    def _py(self, expr: Expr) -> str:
        """Expression -> Python (raw values, no state dict)."""
        if isinstance(expr, NumLit):  return str(expr.value)
        if isinstance(expr, StrLit):  return f'"{expr.value}"'
        if isinstance(expr, BoolLit): return str(expr.value)
        if isinstance(expr, Ident):   return expr.name
        if isinstance(expr, BinOp):
            return f"{self._py(expr.left)} {expr.op} {self._py(expr.right)}"
        if isinstance(expr, UnaryOp):
            return f"{expr.op}{self._py(expr.operand)}"
        if isinstance(expr, FuncCall):
            args = ", ".join(self._py(a) for a in expr.args)
            return f"{expr.name}({args})"
        return "None"

    def _py_s(self, expr: Expr, in_binop=False) -> str:
        """Expression -> Python with s['var'] references."""
        if isinstance(expr, NumLit):  return str(expr.value)
        if isinstance(expr, StrLit):  return f'"{expr.value}"'
        if isinstance(expr, BoolLit): return str(expr.value)
        if isinstance(expr, Ident):
            if expr.name in self.var_names:
                return f's["{expr.name}"]'
            return expr.name
        if isinstance(expr, BinOp):
            l = self._py_s(expr.left, True)
            r = self._py_s(expr.right, True)
            result = f"{l} {expr.op} {r}"
            return f"({result})" if in_binop else result
        if isinstance(expr, UnaryOp):
            return f"{expr.op}{self._py_s(expr.operand)}"
        if isinstance(expr, FuncCall):
            args = ", ".join(self._py_s(a) for a in expr.args)
            return f"{expr.name}({args})"
        return "None"

    def _snake(self, name: str) -> str:
        out: list[str] = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0:
                out.append('_')
            out.append(ch.lower())
        return ''.join(out)
