import re

def tokenize(text):
    tokens = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        m = re.match(r'[0-9]+', text[i:])
        if m:
            tokens.append(('number', m.group()))
            i += m.end()
            continue
        m = re.match(r'[a-zA-Z][a-zA-Z0-9]*', text[i:])
        if m:
            tokens.append(('name', m.group()))
            i += m.end()
            continue
        if text[i] in '+-*/':
            tokens.append(('op', text[i]))
            i += 1
            continue
        if text[i] in '()':
            tokens.append(('paren', text[i]))
            i += 1
            continue
        raise ValueError(f"Unexpected character: {text[i]!r}")
    return tokens

if __name__ == "__main__":
    print(tokenize("3 + foo * (12 - x)"))