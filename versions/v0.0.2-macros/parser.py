"""fran++ parser: tokens -> AST."""

from dataclasses import dataclass
from typing import Union
from lexer import Token, TokenType


# -- AST nodes --

@dataclass
class NumLit:
    value: int

@dataclass
class StrLit:
    value: str

@dataclass
class BoolLit:
    value: bool

@dataclass
class Ident:
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
class FuncCall:
    name: str
    args: list['Expr']

Expr = Union[NumLit, StrLit, BoolLit, Ident, BinOp, UnaryOp, FuncCall]


@dataclass
class VarDecl:
    name: str
    initial: Expr

@dataclass
class Assignment:
    var: str
    value: Expr

@dataclass
class Action:
    name: str
    guard: Expr | None
    assignments: list[Assignment]

@dataclass
class Constraint:
    var: str
    low: Expr
    high: Expr

@dataclass
class Module:
    name: str
    variables: list[VarDecl]
    actions: list[Action]
    constraints: list[Constraint]
    goal: Expr | None


# -- Parser --

class ParseError(Exception):
    pass

SECTIONS = {TokenType.MODULE, TokenType.VARIABLES, TokenType.ACTION,
            TokenType.CONSTRAINT, TokenType.GOAL}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = [t for t in tokens if t.type != TokenType.NEWLINE]
        self.pos = 0

    def error(self, msg: str):
        tok = self.current()
        raise ParseError(f"Line {tok.line}, col {tok.col}: {msg} (got {tok.type.name} {tok.value!r})")

    def current(self) -> Token:
        return self.tokens[min(self.pos, len(self.tokens) - 1)]

    def advance(self) -> Token:
        tok = self.current(); self.pos += 1; return tok

    def expect(self, tt: TokenType) -> Token:
        if self.current().type != tt:
            self.error(f"Expected {tt.name}")
        return self.advance()

    def match(self, *types) -> Token | None:
        if self.current().type in types:
            return self.advance()
        return None

    # -- Top-level --

    def parse(self) -> Module:
        self.expect(TokenType.MODULE)
        name = self.expect(TokenType.IDENT).value

        variables, actions, constraints, goal = [], [], [], None

        while self.current().type != TokenType.EOF:
            tt = self.current().type
            if tt == TokenType.VARIABLES:
                variables = self._variables()
            elif tt == TokenType.ACTION:
                actions.append(self._action())
            elif tt == TokenType.CONSTRAINT:
                constraints = self._constraints()
            elif tt == TokenType.GOAL:
                goal = self._goal()
            else:
                self.advance()

        return Module(name, variables, actions, constraints, goal)

    def _variables(self) -> list[VarDecl]:
        self.expect(TokenType.VARIABLES)
        result = []
        while self.current().type == TokenType.IDENT:
            name = self.expect(TokenType.IDENT).value
            self.expect(TokenType.EQ)
            result.append(VarDecl(name, self._expr()))
        return result

    def _action(self) -> Action:
        self.expect(TokenType.ACTION)
        name = self.expect(TokenType.IDENT).value
        guard = None
        if self.current().type == TokenType.WHEN:
            self.advance()
            guard = self._expr()
        assignments = []
        while self.current().type == TokenType.SET:
            self.advance()
            var = self.expect(TokenType.IDENT).value
            self.expect(TokenType.TO)
            assignments.append(Assignment(var, self._expr()))
        return Action(name, guard, assignments)

    def _constraints(self) -> list[Constraint]:
        self.expect(TokenType.CONSTRAINT)
        result = []
        while self.current().type == TokenType.IDENT:
            var = self.expect(TokenType.IDENT).value
            self.expect(TokenType.BETWEEN)
            low = self._addition()  # stop before AND
            self.expect(TokenType.AND)
            high = self._addition()
            result.append(Constraint(var, low, high))
        return result

    def _goal(self) -> Expr:
        self.expect(TokenType.GOAL)
        return self._expr()

    # -- Expressions (precedence climbing) --

    def _expr(self) -> Expr:
        return self._or()

    def _or(self) -> Expr:
        left = self._and()
        while self.match(TokenType.OR):
            left = BinOp('or', left, self._and())
        return left

    def _and(self) -> Expr:
        left = self._comparison()
        while self.match(TokenType.AND):
            left = BinOp('and', left, self._comparison())
        return left

    def _comparison(self) -> Expr:
        left = self._addition()
        comp = {
            TokenType.EQ: '==', TokenType.NEQ: '!=',
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
        while self.current().type in (TokenType.TIMES, TokenType.MOD):
            op = '*' if self.current().type == TokenType.TIMES else '%'
            self.advance()
            left = BinOp(op, left, self._unary())
        return left

    def _unary(self) -> Expr:
        if self.match(TokenType.NOT):
            return UnaryOp('not ', self._unary())
        if self.match(TokenType.MINUS):
            return UnaryOp('-', self._unary())
        return self._primary()

    def _primary(self) -> Expr:
        tok = self.current()

        if tok.type == TokenType.NUMBER:
            self.advance(); return NumLit(int(tok.value))
        if tok.type == TokenType.STRING:
            self.advance(); return StrLit(tok.value)
        if tok.type == TokenType.TRUE:
            self.advance(); return BoolLit(True)
        if tok.type == TokenType.FALSE:
            self.advance(); return BoolLit(False)

        # min(...) / max(...)
        if tok.type in (TokenType.MIN, TokenType.MAX):
            name = tok.value.lower()
            self.advance()
            self.expect(TokenType.LPAREN)
            a = self._expr()
            self.expect(TokenType.COMMA)
            b = self._expr()
            self.expect(TokenType.RPAREN)
            return FuncCall(name, [a, b])

        # Parenthesized
        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self._expr()
            self.expect(TokenType.RPAREN)
            return expr

        # Identifier
        if tok.type == TokenType.IDENT:
            self.advance(); return Ident(tok.value)

        self.error("Unexpected token in expression")
