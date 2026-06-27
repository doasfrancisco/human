"""fran++ lexer: tokenizes TLA+ source code."""

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Module structure
    MODULE_START = auto()   # ----
    MODULE_END = auto()     # ====
    MODULE = auto()
    EXTENDS = auto()
    VARIABLE = auto()
    CONSTANT = auto()

    # Literals
    TRUE = auto()
    FALSE = auto()
    NUMBER = auto()
    STRING = auto()

    # Identifiers
    IDENT = auto()

    # Operators
    DEF = auto()            # ==
    EQ = auto()             # =
    NEQ = auto()            # #
    AND = auto()            # /\
    OR = auto()             # \/
    IN = auto()             # \in
    NOTIN = auto()          # \notin
    IF = auto()
    THEN = auto()
    ELSE = auto()
    PRIME = auto()          # '
    NOT = auto()            # ~ or \lnot or \neg
    IMPLIES = auto()        # =>
    LT = auto()
    GT = auto()
    LTE = auto()            # <=
    GTE = auto()            # >=
    PLUS = auto()
    MINUS = auto()
    TIMES = auto()
    DIV = auto()            # \div
    MOD = auto()            # %
    DOTDOT = auto()         # ..

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LANGLE = auto()         # <<
    RANGLE = auto()         # >>
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    COLON = auto()

    # Temporal
    BOX = auto()            # []

    # Special
    UNDERSCORE = auto()

    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r})"


class LexerError(Exception):
    pass


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
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return '\0'

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def remaining(self):
        return self.source[self.pos:]

    def match_str(self, expected: str) -> bool:
        if self.source[self.pos:self.pos + len(expected)] == expected:
            for _ in range(len(expected)):
                self.advance()
            return True
        return False

    def skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\r':
            self.advance()

    def skip_comment(self) -> bool:
        # Line comment: \*
        if self.remaining().startswith('\\*'):
            while self.pos < len(self.source) and self.source[self.pos] != '\n':
                self.advance()
            return True
        # Block comment: (* ... *)
        if self.remaining().startswith('(*'):
            self.advance()
            self.advance()
            while self.pos < len(self.source) - 1:
                if self.source[self.pos] == '*' and self.source[self.pos + 1] == ')':
                    self.advance()
                    self.advance()
                    return True
                self.advance()
            self.error("Unterminated block comment")
        return False

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace()
            if self.pos >= len(self.source):
                break

            if self.skip_comment():
                continue

            ch = self.source[self.pos]
            sl, sc = self.line, self.col

            # Newlines
            if ch == '\n':
                self.advance()
                self.tokens.append(Token(TokenType.NEWLINE, '\n', sl, sc))
                continue

            # ---- (module start, 4+ dashes)
            if ch == '-' and self.remaining()[:4] == '----':
                dashes = ''
                while self.pos < len(self.source) and self.source[self.pos] == '-':
                    dashes += self.advance()
                self.tokens.append(Token(TokenType.MODULE_START, dashes, sl, sc))
                continue

            # ==== (module end, 4+ equals)
            if ch == '=' and self.remaining()[:4] == '====':
                equals = ''
                while self.pos < len(self.source) and self.source[self.pos] == '=':
                    equals += self.advance()
                self.tokens.append(Token(TokenType.MODULE_END, equals, sl, sc))
                continue

            # == (definition) — before single =
            if ch == '=' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.DEF, '==', sl, sc))
                continue

            # => (implies)
            if ch == '=' and self.peek(1) == '>':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.IMPLIES, '=>', sl, sc))
                continue

            # =< (less-than-or-equal alt syntax)
            if ch == '=' and self.peek(1) == '<':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.LTE, '=<', sl, sc))
                continue

            # = (equality)
            if ch == '=':
                self.advance()
                self.tokens.append(Token(TokenType.EQ, '=', sl, sc))
                continue

            # # (not equal)
            if ch == '#':
                self.advance()
                self.tokens.append(Token(TokenType.NEQ, '#', sl, sc))
                continue

            # /\ (and)
            if ch == '/' and self.peek(1) == '\\':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.AND, '/\\', sl, sc))
                continue

            # \/ (or)
            if ch == '\\' and self.peek(1) == '/':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.OR, '\\/', sl, sc))
                continue

            # \keyword (\in, \notin, \div, \lnot, \neg, \union, \subseteq, etc.)
            if ch == '\\' and self.peek(1).isalpha():
                self.advance()  # skip backslash
                word = ''
                while self.pos < len(self.source) and self.source[self.pos].isalpha():
                    word += self.advance()
                kw_map = {
                    'in': TokenType.IN,
                    'notin': TokenType.NOTIN,
                    'div': TokenType.DIV,
                    'lnot': TokenType.NOT,
                    'neg': TokenType.NOT,
                }
                tt = kw_map.get(word, TokenType.IDENT)
                self.tokens.append(Token(tt, '\\' + word, sl, sc))
                continue

            # ' (prime)
            if ch == "'":
                self.advance()
                self.tokens.append(Token(TokenType.PRIME, "'", sl, sc))
                continue

            # ~ (not)
            if ch == '~':
                self.advance()
                self.tokens.append(Token(TokenType.NOT, '~', sl, sc))
                continue

            # << and >>
            if ch == '<' and self.peek(1) == '<':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.LANGLE, '<<', sl, sc))
                continue
            if ch == '>' and self.peek(1) == '>':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.RANGLE, '>>', sl, sc))
                continue

            # <= and >=
            if ch == '<' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.LTE, '<=', sl, sc))
                continue
            if ch == '>' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.GTE, '>=', sl, sc))
                continue

            # < and >
            if ch == '<':
                self.advance()
                self.tokens.append(Token(TokenType.LT, '<', sl, sc))
                continue
            if ch == '>':
                self.advance()
                self.tokens.append(Token(TokenType.GT, '>', sl, sc))
                continue

            # [] (box / temporal)
            if ch == '[' and self.peek(1) == ']':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.BOX, '[]', sl, sc))
                continue

            # .. (range)
            if ch == '.' and self.peek(1) == '.':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.DOTDOT, '..', sl, sc))
                continue

            # Single-char tokens
            simple = {
                '(': TokenType.LPAREN, ')': TokenType.RPAREN,
                '{': TokenType.LBRACE, '}': TokenType.RBRACE,
                '[': TokenType.LBRACKET, ']': TokenType.RBRACKET,
                ',': TokenType.COMMA, ':': TokenType.COLON,
                '+': TokenType.PLUS, '-': TokenType.MINUS,
                '*': TokenType.TIMES, '%': TokenType.MOD,
                '_': TokenType.UNDERSCORE,
            }
            if ch in simple:
                self.advance()
                self.tokens.append(Token(simple[ch], ch, sl, sc))
                continue

            # Numbers
            if ch.isdigit():
                num = ''
                while self.pos < len(self.source) and self.source[self.pos].isdigit():
                    num += self.advance()
                self.tokens.append(Token(TokenType.NUMBER, num, sl, sc))
                continue

            # Strings
            if ch == '"':
                self.advance()
                s = ''
                while self.pos < len(self.source) and self.source[self.pos] != '"':
                    s += self.advance()
                if self.pos < len(self.source):
                    self.advance()
                self.tokens.append(Token(TokenType.STRING, s, sl, sc))
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == '_':
                ident = ''
                while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
                    ident += self.advance()
                keywords = {
                    'MODULE': TokenType.MODULE,
                    'EXTENDS': TokenType.EXTENDS,
                    'VARIABLE': TokenType.VARIABLE,
                    'VARIABLES': TokenType.VARIABLE,
                    'CONSTANT': TokenType.CONSTANT,
                    'CONSTANTS': TokenType.CONSTANT,
                    'TRUE': TokenType.TRUE,
                    'FALSE': TokenType.FALSE,
                    'and': TokenType.AND,
                    'or': TokenType.OR,
                    'IF': TokenType.IF,
                    'THEN': TokenType.THEN,
                    'ELSE': TokenType.ELSE,
                }
                tt = keywords.get(ident, TokenType.IDENT)
                self.tokens.append(Token(tt, ident, sl, sc))
                continue

            self.error(f"Unexpected character: {ch!r}")

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return self.tokens
