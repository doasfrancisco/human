"""fran++ lexer: tokenizes English-like spec syntax."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Section keywords
    MODULE = auto()
    VARIABLES = auto()
    ACTION = auto()
    CONSTRAINT = auto()
    GOAL = auto()

    # Statement keywords
    SET = auto()
    TO = auto()
    WHEN = auto()
    BETWEEN = auto()

    # Logic
    AND = auto()
    OR = auto()
    NOT = auto()

    # Built-in functions
    MIN = auto()
    MAX = auto()

    # Literals
    NUMBER = auto()
    STRING = auto()
    TRUE = auto()
    FALSE = auto()

    # Identifiers
    IDENT = auto()

    # Operators
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    PLUS = auto()
    MINUS = auto()
    TIMES = auto()
    MOD = auto()

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()

    # Structure
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int


class LexerError(Exception):
    pass


KEYWORDS = {
    'module': TokenType.MODULE,
    'variables': TokenType.VARIABLES,
    'action': TokenType.ACTION,
    'constraint': TokenType.CONSTRAINT,
    'goal': TokenType.GOAL,
    'set': TokenType.SET,
    'to': TokenType.TO,
    'when': TokenType.WHEN,
    'between': TokenType.BETWEEN,
    'and': TokenType.AND,
    'or': TokenType.OR,
    'not': TokenType.NOT,
    'min': TokenType.MIN,
    'max': TokenType.MAX,
    'true': TokenType.TRUE,
    'false': TokenType.FALSE,
}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def error(self, msg: str):
        raise LexerError(f"Line {self.line}, col {self.col}: {msg}")

    def peek(self, offset=0):
        p = self.pos + offset
        return self.source[p] if p < len(self.source) else '\0'

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.source):
            # Skip spaces/tabs
            while self.pos < len(self.source) and self.source[self.pos] in ' \t\r':
                self.advance()
            if self.pos >= len(self.source):
                break

            ch = self.source[self.pos]
            sl, sc = self.line, self.col

            # Comments (# to end of line)
            if ch == '#':
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self.advance()
                continue

            # Newline (collapse multiples)
            if ch == '\n':
                self.advance()
                if not self.tokens or self.tokens[-1].type != TokenType.NEWLINE:
                    self.tokens.append(Token(TokenType.NEWLINE, '\n', sl, sc))
                continue

            # Two-char operators
            if ch == '!' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.NEQ, '!=', sl, sc)); continue
            if ch == '<' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.LTE, '<=', sl, sc)); continue
            if ch == '>' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.GTE, '>=', sl, sc)); continue

            # Single-char operators
            simple = {
                '=': TokenType.EQ, '<': TokenType.LT, '>': TokenType.GT,
                '+': TokenType.PLUS, '-': TokenType.MINUS,
                '*': TokenType.TIMES, '%': TokenType.MOD,
                '(': TokenType.LPAREN, ')': TokenType.RPAREN, ',': TokenType.COMMA,
            }
            if ch in simple:
                self.advance()
                self.tokens.append(Token(simple[ch], ch, sl, sc)); continue

            # Numbers
            if ch.isdigit():
                num = ''
                while self.pos < len(self.source) and self.source[self.pos].isdigit():
                    num += self.advance()
                self.tokens.append(Token(TokenType.NUMBER, num, sl, sc)); continue

            # Strings
            if ch == '"':
                self.advance()
                s = ''
                while self.pos < len(self.source) and self.source[self.pos] != '"':
                    s += self.advance()
                if self.pos < len(self.source):
                    self.advance()
                self.tokens.append(Token(TokenType.STRING, s, sl, sc)); continue

            # Words (identifiers and keywords)
            if ch.isalpha() or ch == '_':
                word = ''
                while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
                    word += self.advance()
                tt = KEYWORDS.get(word.lower(), TokenType.IDENT)
                self.tokens.append(Token(tt, word, sl, sc)); continue

            self.error(f"Unexpected character: {ch!r}")

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return self.tokens
