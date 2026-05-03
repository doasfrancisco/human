#!/usr/bin/env python3
"""fran++ compiler -- English-like specs -> Python

Usage:
    python fran.py <spec.fpp>               compile to <spec>.py
    python fran.py <spec.fpp> -o out.py     compile to out.py
    python fran.py <spec.fpp> --run         compile and run
    python fran.py <spec.fpp> --ast         show AST
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from macros import expand
from lexer import Lexer
from parser import Parser
from codegen import PythonCodeGen


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__.strip())
        sys.exit(0)

    spec_file = sys.argv[1]
    output_file = None
    run_after = False
    show_ast = False
    show_expand = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] in ('-o', '--output') and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]; i += 2
        elif sys.argv[i] == '--run':
            run_after = True; i += 1
        elif sys.argv[i] == '--ast':
            show_ast = True; i += 1
        elif sys.argv[i] == '--expand':
            show_expand = True; i += 1
        else:
            print(f"Unknown option: {sys.argv[i]}", file=sys.stderr); sys.exit(1)

    with open(spec_file, 'r', encoding='utf-8') as f:
        source = f.read()

    source = expand(source)

    if show_expand:
        print(source)
        return

    tokens = Lexer(source).tokenize()
    module = Parser(tokens).parse()

    if show_ast:
        print(f"Module: {module.name}")
        print(f"  variables: {module.variables}")
        print(f"  actions:   {[a.name for a in module.actions]}")
        print(f"  constraints: {module.constraints}")
        print(f"  goal: {module.goal}")
        return

    code = PythonCodeGen(module).generate()

    if not output_file:
        output_file = os.path.splitext(os.path.basename(spec_file))[0] + ".py"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(code)

    print(f"fran++ compiled {spec_file} -> {output_file}")

    if run_after:
        print()
        os.system(f'{sys.executable} "{output_file}"')


if __name__ == "__main__":
    main()
