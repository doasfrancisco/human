"""fran++ code generator: TLA+ AST → Python source code."""

from dataclasses import dataclass
from tla_parser import (
    Module, OpDef, Expr,
    BoolLit, NumLit, StrLit, Ident, PrimedIdent,
    BinOp, UnaryOp, SetLit, SeqLit, SetMembership,
    FuncCall, IfThenElse, TemporalBox,
)


@dataclass
class NextBranch:
    """A single branch from the Next disjunction."""
    action_name: str
    args: list[Expr]


class PythonCodeGen:
    def __init__(self, module: Module):
        self.module = module
        self.ops: dict[str, OpDef] = {op.name: op for op in module.operators}
        self.I = "    "  # indent

    def generate(self) -> str:
        lines: list[str] = []
        lines.append("import random")
        lines.append("")

        # Constants
        for c in self.module.constants:
            lines.append(f"{c} = 3  # TODO: set value")
        if self.module.constants:
            lines.append("")

        init_op = self.ops.get("Init")
        next_op = self.ops.get("Next")

        # Collect action branches from Next
        branches = self._collect_branches(next_op.body) if next_op else []
        # Unique action names (preserving order)
        seen = set()
        action_names = []
        for b in branches:
            if b.action_name not in seen:
                action_names.append(b.action_name)
                seen.add(b.action_name)

        # Invariants
        inv_names = [n for n in self.ops if "Invariant" in n or "invariant" in n]

        # ── Class ──────────────────────────────────────────────────────
        cls = self.module.name
        lines.append(f"class {cls}:")

        # __init__
        lines.append(f"{self.I}def __init__(self):")
        if init_op:
            inits = self._init_assignments(init_op.body)
            for var, val in inits.items():
                lines.append(f"{self.I}{self.I}self.{var} = {val}")
        else:
            for v in self.module.variables:
                lines.append(f"{self.I}{self.I}self.{v} = None")
        lines.append("")

        # Action methods
        for aname in action_names:
            if aname not in self.ops:
                continue
            op = self.ops[aname]
            guards, effects = self._split_guards_effects(op.body)
            params = ["self"] + op.params
            mname = self._snake(aname)

            lines.append(f"{self.I}def {mname}({', '.join(params)}):  # TLA+: {aname}")
            # Build print lines for each state change
            prints = []
            for e in effects:
                # e looks like "self.var = value" — extract var and value
                if e.startswith("self.") and " = " in e:
                    var = e.split(" = ")[0].replace("self.", "")
                    prints.append(f'print(f"{var} = {{self.{var}}}\")')

            if guards:
                gstr = " and ".join(guards)
                lines.append(f"{self.I}{self.I}if {gstr}:")
                for e in effects:
                    lines.append(f"{self.I}{self.I}{self.I}{e}")
                for p in prints:
                    lines.append(f"{self.I}{self.I}{self.I}{p}")
                lines.append(f"{self.I}{self.I}{self.I}return True")
                lines.append(f"{self.I}{self.I}return False")
            else:
                for e in effects:
                    lines.append(f"{self.I}{self.I}{e}")
                for p in prints:
                    lines.append(f"{self.I}{self.I}{p}")
                lines.append(f"{self.I}{self.I}return True")
            lines.append("")

        # step()
        if branches:
            lines.append(f"{self.I}def step(self):")
            lines.append(f"{self.I}{self.I}actions = []")
            for b in branches:
                op = self.ops.get(b.action_name)
                if not op:
                    continue
                guards, _ = self._split_guards_effects(op.body)
                mname = self._snake(b.action_name)

                # Build the callable
                if b.args:
                    arg_strs = ", ".join(self._to_py(a) for a in b.args)
                    call = f"lambda: self.{mname}({arg_strs})"
                else:
                    call = f"self.{mname}"

                if guards:
                    gstr = " and ".join(guards)
                    lines.append(f"{self.I}{self.I}if {gstr}:")
                    lines.append(f"{self.I}{self.I}{self.I}actions.append({call})")
                else:
                    lines.append(f"{self.I}{self.I}actions.append({call})")

            lines.append(f"{self.I}{self.I}if actions:")
            lines.append(f"{self.I}{self.I}{self.I}random.choice(actions)()")
            lines.append("")

        # check()
        if inv_names:
            lines.append(f"{self.I}def check(self):")
            for iname in inv_names:
                checks = self._invariant_checks(self.ops[iname].body)
                for c in checks:
                    lines.append(f"{self.I}{self.I}assert {c}, \"{iname} violated\"")
            lines.append("")

        return "\n".join(lines) + "\n"

    # ── Helpers ────────────────────────────────────────────────────────

    def _collect_branches(self, expr: Expr) -> list[NextBranch]:
        """Walk Next disjunction tree → list of action references."""
        if isinstance(expr, BinOp) and expr.op == '\\/':
            return self._collect_branches(expr.left) + self._collect_branches(expr.right)
        if isinstance(expr, Ident):
            return [NextBranch(expr.name, [])]
        if isinstance(expr, FuncCall):
            return [NextBranch(expr.name, expr.args)]
        return []

    def _init_assignments(self, expr: Expr) -> dict[str, str]:
        """Extract var=value pairs from Init conjunction."""
        result: dict[str, str] = {}
        for conj in self._flatten_and(expr):
            if isinstance(conj, BinOp) and conj.op == '=':
                if isinstance(conj.left, Ident) and conj.left.name in self.module.variables:
                    result[conj.left.name] = self._to_py(conj.right)
        return result

    def _split_guards_effects(self, expr: Expr) -> tuple[list[str], list[str]]:
        """Separate action body into guard conditions and state updates."""
        guards: list[str] = []
        effects: list[str] = []
        for conj in self._flatten_and(expr):
            if self._has_prime(conj):
                if isinstance(conj, BinOp) and conj.op == '=' and isinstance(conj.left, PrimedIdent):
                    effects.append(f"self.{conj.left.name} = {self._to_py(conj.right)}")
                else:
                    effects.append(self._to_py(conj))
            else:
                guards.append(self._to_py(conj))
        return guards, effects

    def _flatten_and(self, expr: Expr) -> list[Expr]:
        if isinstance(expr, BinOp) and expr.op == '/\\':
            return self._flatten_and(expr.left) + self._flatten_and(expr.right)
        return [expr]

    def _has_prime(self, expr: Expr) -> bool:
        if isinstance(expr, PrimedIdent):
            return True
        if isinstance(expr, BinOp):
            return self._has_prime(expr.left) or self._has_prime(expr.right)
        if isinstance(expr, UnaryOp):
            return self._has_prime(expr.operand)
        if isinstance(expr, FuncCall):
            return any(self._has_prime(a) for a in expr.args)
        if isinstance(expr, IfThenElse):
            return (self._has_prime(expr.cond) or
                    self._has_prime(expr.then_expr) or
                    self._has_prime(expr.else_expr))
        return False

    def _invariant_checks(self, expr: Expr) -> list[str]:
        return [self._to_py(c) for c in self._flatten_and(expr)]

    def _to_py(self, expr: Expr) -> str:
        """Convert TLA+ AST node → Python expression string."""
        if isinstance(expr, BoolLit):
            return str(expr.value)
        if isinstance(expr, NumLit):
            return str(expr.value)
        if isinstance(expr, StrLit):
            return f'"{expr.value}"'
        if isinstance(expr, Ident):
            if expr.name in self.module.variables:
                return f"self.{expr.name}"
            return expr.name
        if isinstance(expr, PrimedIdent):
            return f"self.{expr.name}"
        if isinstance(expr, BinOp):
            l = self._to_py(expr.left)
            r = self._to_py(expr.right)
            py_op = {'=': '==', '#': '!=', '/\\': 'and', '\\/': 'or'}.get(expr.op, expr.op)
            return f"{l} {py_op} {r}"
        if isinstance(expr, UnaryOp):
            if expr.op == '~':
                return f"not {self._to_py(expr.operand)}"
            return f"{expr.op}{self._to_py(expr.operand)}"
        if isinstance(expr, SetLit):
            elems = ", ".join(self._to_py(e) for e in expr.elements)
            return "{" + elems + "}"
        if isinstance(expr, SeqLit):
            elems = ", ".join(self._to_py(e) for e in expr.elements)
            return f"[{elems}]"
        if isinstance(expr, SetMembership):
            return f"{self._to_py(expr.elem)} in {self._to_py(expr.set_expr)}"
        if isinstance(expr, FuncCall):
            args = [self._to_py(a) for a in expr.args]
            # Map TLA+ stdlib → Python
            if expr.name == 'Append' and len(args) == 2:
                return f"{args[0]} + [{args[1]}]"
            if expr.name == 'Head' and len(args) == 1:
                return f"{args[0]}[0]"
            if expr.name == 'Tail' and len(args) == 1:
                return f"{args[0]}[1:]"
            if expr.name == 'Len' and len(args) == 1:
                return f"len({args[0]})"
            if expr.name == 'Cardinality' and len(args) == 1:
                return f"len({args[0]})"
            return f"{expr.name}({', '.join(args)})"
        if isinstance(expr, IfThenElse):
            c = self._to_py(expr.cond)
            t = self._to_py(expr.then_expr)
            e = self._to_py(expr.else_expr)
            return f"{t} if {c} else {e}"
        if isinstance(expr, TemporalBox):
            return ""
        return "None  # TODO"

    def _snake(self, name: str) -> str:
        """CamelCase → snake_case, avoiding reserved method names."""
        out: list[str] = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0:
                out.append('_')
            out.append(ch.lower())
        result = ''.join(out)
        if result in ('step', 'check'):
            result = f"do_{result}"
        return result
