"""fran++ macro expander: text-level expansion before lexing.

Macros are programs that write fran++ code at compile time.

    macro change(denominations, target)
        variables
            remaining = {target}
        for coin in {denominations}
            action Use{coin}
                when remaining >= {coin}

    module CoinChange
        change([1, 5, 10, 25], 67)

The expander runs BEFORE the lexer sees anything. It outputs plain fran++.
"""

import re
import textwrap


class MacroError(Exception):
    pass


class Macro:
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body  # dedented body lines


def expand(source: str) -> str:
    """Expand all macros in source. Returns plain fran++ text."""
    macros, rest = _extract_macros(source)
    if not macros:
        return source
    return _expand_calls(rest, macros)


def _extract_macros(source):
    """Split source into macro definitions and everything else."""
    lines = source.split('\n')
    macros = {}
    rest = []
    i = 0

    while i < len(lines):
        m = re.match(r'^macro\s+(\w+)\s*\(([^)]*)\)\s*$', lines[i].strip())
        if m:
            name = m.group(1)
            params = [p.strip() for p in m.group(2).split(',') if p.strip()]
            i += 1

            # Collect indented body
            body = []
            while i < len(lines):
                if lines[i].strip() == '' or lines[i].startswith((' ', '\t')):
                    body.append(lines[i])
                    i += 1
                else:
                    break

            # Strip trailing blank lines
            while body and body[-1].strip() == '':
                body.pop()

            # Dedent to remove the macro-level indentation
            body = textwrap.dedent('\n'.join(body)).split('\n')
            macros[name] = Macro(name, params, body)
        else:
            rest.append(lines[i])
            i += 1

    return macros, '\n'.join(rest)


def _expand_calls(source, macros):
    """Find macro calls and replace them with expanded body."""
    lines = source.split('\n')
    result = []

    for line in lines:
        expanded = False
        for name, macro in macros.items():
            pattern = rf'^(\s*){re.escape(name)}\s*\((.+)\)\s*$'
            m = re.match(pattern, line)
            if m:
                args = _parse_args(m.group(2))
                if len(args) != len(macro.params):
                    raise MacroError(
                        f"'{name}' expects {len(macro.params)} args, got {len(args)}"
                    )
                bindings = dict(zip(macro.params, args))
                result.extend(_expand_body(macro.body, bindings))
                expanded = True
                break

        if not expanded:
            result.append(line)

    return '\n'.join(result)


# -- Argument parsing --

def _parse_args(args_str):
    """Parse '[1, 5, 10], 67' into [['1','5','10'], '67']."""
    args = []
    depth = 0
    current = ''

    for ch in args_str:
        if ch == '[':
            depth += 1
            current += ch
        elif ch == ']':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            args.append(current.strip())
            current = ''
        else:
            current += ch

    if current.strip():
        args.append(current.strip())

    return [_parse_value(a) for a in args]


def _parse_value(s):
    """'[1, 5, 10]' -> ['1','5','10'],  '67' -> '67'."""
    if s.startswith('[') and s.endswith(']'):
        return [x.strip() for x in s[1:-1].split(',') if x.strip()]
    return s


# -- Body expansion --

def _expand_body(body_lines, bindings):
    """Expand macro body: substitute {params} and unroll for-loops."""
    result = []
    i = 0

    while i < len(body_lines):
        line = body_lines[i]
        stripped = line.strip()

        # Blank lines pass through
        if stripped == '':
            result.append('')
            i += 1
            continue

        # Comments pass through
        if stripped.startswith('#'):
            i += 1
            continue

        # for VAR in {PARAM}
        m = re.match(r'^(\s*)for\s+(\w+)\s+in\s+\{(\w+)\}\s*$', line)
        if m:
            for_indent = len(m.group(1))
            loop_var = m.group(2)
            param_name = m.group(3)

            if param_name not in bindings:
                raise MacroError(f"Unknown parameter in for loop: {param_name}")
            items = bindings[param_name]
            if not isinstance(items, list):
                raise MacroError(f"for loop requires list, got: {items}")

            # Collect loop body: lines indented deeper than the for line
            i += 1
            loop_body = []
            while i < len(body_lines):
                if body_lines[i].strip() == '':
                    loop_body.append(body_lines[i])
                    i += 1
                    continue
                line_indent = len(body_lines[i]) - len(body_lines[i].lstrip())
                if line_indent > for_indent:
                    loop_body.append(body_lines[i])
                    i += 1
                else:
                    break

            # Strip trailing blanks from loop body
            while loop_body and loop_body[-1].strip() == '':
                loop_body.pop()

            # Unroll: expand loop body once per item
            for item in items:
                inner = {**bindings, loop_var: item}
                for lb in loop_body:
                    result.append(_substitute(lb, inner))
                result.append('')  # blank line between unrolled blocks

            continue

        # Regular line — substitute and emit
        result.append(_substitute(line, bindings))
        i += 1

    return result


def _substitute(line, bindings):
    """Replace {name} placeholders in a line."""
    def replacer(m):
        key = m.group(1)
        if key in bindings:
            val = bindings[key]
            if isinstance(val, list):
                return ', '.join(val)
            return str(val)
        return m.group(0)

    return re.sub(r'\{(\w+)\}', replacer, line)
