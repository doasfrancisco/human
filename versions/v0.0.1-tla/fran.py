#!/usr/bin/env python3
"""fran++ compiler — TLA+ → Python

Usage:
    python fran.py <spec.tla>               compile to <spec>.py
    python fran.py <spec.tla> -o out.py     compile to out.py
    python fran.py <spec.tla> --run         compile and run immediately
    python fran.py <spec.tla> --ast         show parsed AST (debug)
"""

import sys
import os

# Allow imports from the same directory as this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import Lexer
from tla_parser import Parser
from codegen import PythonCodeGen


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__.strip())
        sys.exit(0)

    spec_file = sys.argv[1]
    output_file = None
    run_after = False
    show_ast = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] in ('-o', '--output') and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--run':
            run_after = True
            i += 1
        elif sys.argv[i] == '--ast':
            show_ast = True
            i += 1
        else:
            print(f"Unknown option: {sys.argv[i]}", file=sys.stderr)
            sys.exit(1)

    # Read source
    with open(spec_file, 'r') as f:
        source = f.read()

    # Lex
    tokens = Lexer(source).tokenize()

    # Parse
    module = Parser(tokens).parse()

    if show_ast:
        print(f"Module: {module.name}")
        print(f"  extends:   {module.extends}")
        print(f"  constants: {module.constants}")
        print(f"  variables: {module.variables}")
        for op in module.operators:
            print(f"  op {op.name}({', '.join(op.params)}) == {op.body}")
        return

    # Generate Python
    python_code = PythonCodeGen(module).generate()

    # Write output
    if not output_file:
        base = os.path.splitext(os.path.basename(spec_file))[0]
        output_file = base + ".py"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(python_code)

    print(f"fran++ compiled {spec_file} → {output_file}")

    if run_after:
        print()
        os.system(f'{sys.executable} "{output_file}"')


if __name__ == "__main__":
    main()
