"""fran++ parser: TLA+ tokens → AST."""

from dataclasses import dataclass, field
from typing import Union
from lexer import Token, TokenType


# ── AST nodes ──────────────────────────────────────────────────────────

@dataclass
class BoolLit:
    value: bool

@dataclass
class NumLit:
    value: int

@dataclass
class StrLit:
    value: str

@dataclass
class Ident:
    name: str

@dataclass
class PrimedIdent:
    name: str

@dataclass
class BinOp:
    op: str
    left: 'Expr'
    right: 'Expr'

@dataclass
class UnaryOp:
    op: str
    operand: 'Expr'

@dataclass
class SetLit:
    elements: list['Expr']

@dataclass
class SeqLit:
    elements: list['Expr']

@dataclass
class SetMembership:
    elem: 'Expr'
    set_expr: 'Expr'

@dataclass
class FuncCall:
    name: str
    args: list['Expr']

@dataclass
class IfThenElse:
    cond: 'Expr'
    then_expr: 'Expr'
    else_expr: 'Expr'

@dataclass
class TemporalBox:
    """[][Action]_var — skipped during codegen."""
    action: 'Expr'
    var: str

Expr = Union[BoolLit, NumLit, StrLit, Ident, PrimedIdent, BinOp, UnaryOp,
             SetLit, SeqLit, SetMembership, FuncCall, IfThenElse, TemporalBox]


@dataclass
class OpDef:
    name: str
    params: list[str]
    body: Expr


@dataclass
class Module:
    name: str
    extends: list[str]
    constants: list[str]
    variables: list[str]
    operators: list[OpDef]


# ── Parser ─────────────────────────────────────────────────────────────

class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        # Filter newlines — they don't affect TLA+ semantics
        self.tokens = [t for t in tokens if t.type != TokenType.NEWLINE]
        self.pos = 0

    def error(self, msg: str):
        tok = self.current()
        raise ParseError(
            f"Line {tok.line}, col {tok.col}: {msg} "
            f"(got {tok.type.name} {tok.value!r})"
        )

    def current(self) -> Token:
        return self.tokens[min(self.pos, len(self.tokens) - 1)]

    def peek(self, offset=1) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        tok = self.current()
        self.pos += 1
        return tok

    def expect(self, tt: TokenType) -> Token:
        tok = self.current()
        if tok.type != tt:
            self.error(f"Expected {tt.name}")
        return self.advance()

    def match(self, *types) -> Token | None:
        if self.current().type in types:
            return self.advance()
        return None

    # ── Top-level ──────────────────────────────────────────────────────

    def parse(self) -> Module:
        return self._module()

    def _module(self) -> Module:
        self.expect(TokenType.MODULE_START)
        self.expect(TokenType.MODULE)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.MODULE_START)

        extends: list[str] = []
        constants: list[str] = []
        variables: list[str] = []
        operators: list[OpDef] = []

        while self.current().type not in (TokenType.MODULE_END, TokenType.EOF):
            if self.current().type == TokenType.EXTENDS:
                extends = self._extends()
            elif self.current().type == TokenType.VARIABLE:
                variables.extend(self._var_decl())
            elif self.current().type == TokenType.CONSTANT:
                constants.extend(self._var_decl())
            elif self.current().type == TokenType.IDENT:
                operators.append(self._opdef())
            else:
                self.advance()  # skip unrecognized

        self.match(TokenType.MODULE_END)
        return Module(name, extends, constants, variables, operators)

    def _extends(self) -> list[str]:
        self.expect(TokenType.EXTENDS)
        names = [self.expect(TokenType.IDENT).value]
        while self.match(TokenType.COMMA):
            names.append(self.expect(TokenType.IDENT).value)
        return names

    def _var_decl(self) -> list[str]:
        self.advance()  # VARIABLE or CONSTANT keyword
        names = [self.expect(TokenType.IDENT).value]
        while self.match(TokenType.COMMA):
            names.append(self.expect(TokenType.IDENT).value)
        return names

    def _opdef(self) -> OpDef:
        name = self.expect(TokenType.IDENT).value
        params: list[str] = []
        if self.match(TokenType.LPAREN):
            if self.current().type != TokenType.RPAREN:
                params.append(self.expect(TokenType.IDENT).value)
                while self.match(TokenType.COMMA):
                    params.append(self.expect(TokenType.IDENT).value)
            self.expect(TokenType.RPAREN)
        self.expect(TokenType.DEF)
        body = self._expr()
        return OpDef(name, params, body)

    # ── Expressions (precedence climbing) ──────────────────────────────

    def _expr(self) -> Expr:
        return self._or()

    def _or(self) -> Expr:
        left = self._and()
        while self.current().type == TokenType.OR:
            self.advance()
            left = BinOp('\\/', left, self._and())
        return left

    def _and(self) -> Expr:
        left = self._comparison()
        while self.current().type == TokenType.AND:
            self.advance()
            left = BinOp('/\\', left, self._comparison())
        return left

    def _comparison(self) -> Expr:
        left = self._addition()

        # \in
        if self.current().type == TokenType.IN:
            self.advance()
            return SetMembership(left, self._addition())

        # Comparison operators
        comp = {
            TokenType.EQ: '=', TokenType.NEQ: '#',
            TokenType.LT: '<', TokenType.GT: '>',
            TokenType.LTE: '<=', TokenType.GTE: '>=',
        }
        if self.current().type in comp:
            op = comp[self.current().type]
            self.advance()
            return BinOp(op, left, self._addition())

        return left

    def _addition(self) -> Expr:
        left = self._multiplication()
        while self.current().type in (TokenType.PLUS, TokenType.MINUS):
            op = '+' if self.current().type == TokenType.PLUS else '-'
            self.advance()
            left = BinOp(op, left, self._multiplication())
        return left

    def _multiplication(self) -> Expr:
        left = self._unary()
        while self.current().type in (TokenType.TIMES, TokenType.DIV, TokenType.MOD):
            op_map = {TokenType.TIMES: '*', TokenType.DIV: '//', TokenType.MOD: '%'}
            op = op_map[self.current().type]
            self.advance()
            left = BinOp(op, left, self._unary())
        return left

    def _unary(self) -> Expr:
        if self.current().type == TokenType.NOT:
            self.advance()
            return UnaryOp('~', self._unary())
        if self.current().type == TokenType.MINUS:
            self.advance()
            return UnaryOp('-', self._unary())
        return self._primary()

    def _primary(self) -> Expr:
        tok = self.current()

        if tok.type == TokenType.TRUE:
            self.advance(); return BoolLit(True)
        if tok.type == TokenType.FALSE:
            self.advance(); return BoolLit(False)
        if tok.type == TokenType.NUMBER:
            self.advance(); return NumLit(int(tok.value))
        if tok.type == TokenType.STRING:
            self.advance(); return StrLit(tok.value)

        # IF cond THEN expr ELSE expr
        # Branches parse at comparison level so top-level and/or stays outside
        if tok.type == TokenType.IF:
            self.advance()
            cond = self._comparison()
            self.expect(TokenType.THEN)
            then_expr = self._comparison()
            self.expect(TokenType.ELSE)
            else_expr = self._comparison()
            return IfThenElse(cond, then_expr, else_expr)

        # Set literal { ... }
        if tok.type == TokenType.LBRACE:
            return self._set_lit()

        # Sequence literal << ... >>
        if tok.type == TokenType.LANGLE:
            return self._seq_lit()

        # Temporal [][Action]_var
        if tok.type == TokenType.BOX:
            return self._temporal()

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self._expr()
            self.expect(TokenType.RPAREN)
            return expr

        # Identifier / function call / primed variable
        if tok.type == TokenType.IDENT:
            self.advance()
            name = tok.value

            # Function call
            if self.current().type == TokenType.LPAREN:
                self.advance()
                args: list[Expr] = []
                if self.current().type != TokenType.RPAREN:
                    args.append(self._expr())
                    while self.match(TokenType.COMMA):
                        args.append(self._expr())
                self.expect(TokenType.RPAREN)
                return FuncCall(name, args)

            # Primed variable
            if self.current().type == TokenType.PRIME:
                self.advance()
                return PrimedIdent(name)

            return Ident(name)

        self.error("Unexpected token in expression")

    def _set_lit(self) -> SetLit:
        self.expect(TokenType.LBRACE)
        elems: list[Expr] = []
        if self.current().type != TokenType.RBRACE:
            elems.append(self._expr())
            while self.match(TokenType.COMMA):
                elems.append(self._expr())
        self.expect(TokenType.RBRACE)
        return SetLit(elems)

    def _seq_lit(self) -> SeqLit:
        self.expect(TokenType.LANGLE)
        elems: list[Expr] = []
        if self.current().type != TokenType.RANGLE:
            elems.append(self._expr())
            while self.match(TokenType.COMMA):
                elems.append(self._expr())
        self.expect(TokenType.RANGLE)
        return SeqLit(elems)

    def _temporal(self) -> TemporalBox:
        self.expect(TokenType.BOX)
        self.expect(TokenType.LBRACKET)
        action = self._expr()
        self.expect(TokenType.RBRACKET)
        self.expect(TokenType.UNDERSCORE)
        var = self.expect(TokenType.IDENT).value
        return TemporalBox(action, var)
