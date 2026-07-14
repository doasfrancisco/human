def pretty(value, indent=2):
    def render(val, depth):
        pad = " " * (indent * depth)
        inner_pad = " " * (indent * (depth + 1))
        if val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, str):
            escaped = val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            return '"' + escaped + '"'
        elif isinstance(val, dict):
            if not val:
                return "{}"
            lines = []
            for k, v in val.items():
                escaped_key = k.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
                key_str = '"' + escaped_key + '"'
                lines.append(inner_pad + key_str + ": " + render(v, depth + 1))
            return "{\n" + ",\n".join(lines) + "\n" + pad + "}"
        elif isinstance(val, list):
            if not val:
                return "[]"
            lines = []
            for item in val:
                lines.append(inner_pad + render(item, depth + 1))
            return "[\n" + ",\n".join(lines) + "\n" + pad + "]"
    return render(value, 0)

if __name__ == "__main__":
    print(pretty({"name": "Alice", "age": 30, "active": True, "score": None, "tags": ["a", "b"], "meta": {}}))
    print(pretty([1, 2, 3]))
    print(pretty({}))
    print(pretty([]))
    print(pretty(None))
    print(pretty(True))
    print(pretty(False))
    print(pretty(42))
    print(pretty("hello"))