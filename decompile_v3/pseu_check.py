import sys


class Fail(Exception):
    pass


class Parser:
    def __init__(self, text):
        self.text = text
        self.i = 0

    def line(self, at=None):
        pos = self.i if at is None else at
        return self.text.count("\n", 0, pos) + 1

    def fail(self, msg, at=None):
        raise Fail(f"line {self.line(at)}: {msg}")

    def ws(self):
        while self.i < len(self.text) and self.text[self.i] in " \t\r\n":
            self.i += 1

    def eof(self):
        self.ws()
        return self.i >= len(self.text)

    def expect(self, word):
        self.ws()
        if not self.text.startswith(word, self.i):
            self.fail(f"expected {word!r}")
        self.i += len(word)

    def peek_word(self):
        self.ws()
        j = self.i
        while j < len(self.text) and (self.text[j].isalnum() or self.text[j] == "_"):
            j += 1
        return self.text[self.i:j]

    def description(self, what):
        self.ws()
        start = self.i
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch == ";":
                out = self.text[start:self.i].strip()
                if not out:
                    self.fail(f"empty {what}", start)
                self.i += 1
                return out
            if ch in "{}":
                self.fail(f"{what} must not contain {ch!r}", self.i)
            self.i += 1
        self.fail(f"missing ';' after {what}", start)

    def cond(self):
        self.expect("(")
        start = self.i
        depth = 1
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    out = self.text[start:self.i].strip()
                    if not out:
                        self.fail("empty condition", start)
                    self.i += 1
                    return out
            elif ch in "{};":
                self.fail(f"condition must not contain {ch!r}", self.i)
            self.i += 1
        self.fail("unterminated condition", start)

    def block(self):
        self.expect("{")
        n = 0
        while True:
            self.ws()
            if self.i >= len(self.text):
                self.fail("unterminated block")
            if self.text[self.i] == "}":
                if n == 0:
                    self.fail("empty block")
                self.i += 1
                return
            self.statement()
            n += 1

    def statement(self):
        word = self.peek_word()
        if word in ("if", "while", "for"):
            self.i += len(word)
            self.cond()
            self.block()
            if word == "if":
                while self.peek_word() == "elif":
                    self.i += 4
                    self.cond()
                    self.block()
                if self.peek_word() == "else":
                    self.i += 4
                    self.block()
            return
        if word in ("elif", "else"):
            self.fail(f"{word!r} without a matching 'if'")
        self.description("statement")

    def parse(self):
        self.expect("GOAL:")
        self.description("goal")
        self.expect("DEPENDENCIES:")
        self.description("dependencies")
        self.expect("STEPS:")
        n = 0
        while not self.eof():
            self.statement()
            n += 1
        if n == 0:
            self.fail("no steps")


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: pseu_check.py file.pseu ...")
    bad = 0
    for name in sys.argv[1:]:
        try:
            Parser(open(name, encoding="utf-8").read()).parse()
            print(f"OK {name}")
        except (Fail, OSError) as e:
            print(f"FAIL {name}: {e}")
            bad = 1
    sys.exit(bad)


if __name__ == "__main__":
    main()
