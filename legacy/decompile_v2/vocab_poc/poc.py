import ast
import json
import subprocess
import sys
from pathlib import Path

CALLS = [0]


def ask_claude(prompt):
    CALLS[0] += 1
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "json"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-500:]
    raw = json.loads(r.stdout)["result"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


PASS1 = """You are explaining a Python file to a person, one function at a time. For every top-level function, write a plain explanation of 1 to 3 sentences: what it takes, what it does, what it gives back. Explain each function on its own, as if the others did not exist. Do not compare functions and do not point at shared patterns.

File: example.py
{code}

The functions to explain: {names}.

Return one JSON object only, no code fences:
{{"explanations": {{"function_name": "the explanation"}}}}"""

PASS2 = """Below are explanations of the functions of one Python file, one per function. Several functions share a piece of logic, so their explanations repeat each other.

{expl}

Your job is compression through shared vocabulary:
1. Find the logic that several functions share.
2. Invent the SMALLEST vocabulary of named concepts that shrinks the total text. Each entry is a term and a meaning. The term is a short natural phrase, like "the retry dance". The meaning is one plain line that defines the shared logic fully, so a reader who knows the term needs nothing else. A term must be worth its cost: invent it only when at least 2 functions use it.
3. Rewrite EVERY explanation. Where a term applies, write the term verbatim instead of spelling the logic out, and keep only what is specific to that function. A function that shares nothing keeps a term-free explanation; rewrite it only if you can say the same shorter.

Every term must appear verbatim in at least 2 rewritten explanations.

Return one JSON object only, no code fences:
{{"vocabulary": [{{"term": "...", "meaning": "..."}}], "rewritten": {{"function_name": "the rewritten explanation"}}}}"""


def words(text):
    return len(text.split())


def check_pass1(m, names):
    expl = m.get("explanations")
    assert isinstance(expl, dict), "no explanations object"
    bad = [n for n in names if not (isinstance(expl.get(n), str) and expl[n].strip())]
    assert not bad, f"missing or empty explanations: {', '.join(bad)}"
    return {n: expl[n].strip() for n in names}


def check_pass2(m, names):
    vocab = m.get("vocabulary")
    assert isinstance(vocab, list), "vocabulary must be a list"
    for t in vocab:
        assert isinstance(t, dict) and isinstance(t.get("term"), str) and t["term"].strip(), \
            "a vocabulary entry needs a term string"
        assert isinstance(t.get("meaning"), str) and t["meaning"].strip(), \
            f'the term "{t.get("term")}" needs a meaning'
    rew = m.get("rewritten")
    assert isinstance(rew, dict), "no rewritten object"
    bad = [n for n in names if not (isinstance(rew.get(n), str) and rew[n].strip())]
    assert not bad, f"missing or empty rewritten texts: {', '.join(bad)}"
    out = {n: rew[n].strip() for n in names}
    for t in vocab:
        used = sum(1 for x in out.values() if t["term"].strip() in x)
        assert used >= 2, \
            f'the term "{t["term"].strip()}" appears verbatim in {used} rewritten texts, it must appear in at least 2'
    return [{"term": t["term"].strip(), "meaning": t["meaning"].strip()} for t in vocab], out


def ask_checked(prompt, check, tries):
    note = ""
    errs = []
    m = None
    for attempt in range(tries):
        try:
            m = ask_claude(prompt + note)
            return check(m)
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1}: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit(f"no valid answer after {tries} tries")


def main():
    here = Path(__file__).resolve().parent
    src = (here / "example.py").read_text(encoding="utf-8")
    names = [n.name for n in ast.parse(src).body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    originals = ask_checked(PASS1.format(code=src, names=", ".join(names)),
                            lambda m: check_pass1(m, names), 4)
    print(f"pass 1: {len(originals)} explanations")
    expl_text = "\n".join(f"{n}: {originals[n]}" for n in names)
    vocab, rewritten = ask_checked(PASS2.format(expl=expl_text),
                                   lambda m: check_pass2(m, names), 4)
    print(f"pass 2: {len(vocab)} terms")
    ow = sum(words(t) for t in originals.values())
    rw = sum(words(t) for t in rewritten.values())
    vw = sum(words(t["term"]) + words(t["meaning"]) for t in vocab)
    counts = {"original_words": ow, "rewritten_words": rw, "vocabulary_words": vw,
              "compressed_words": rw + vw, "ratio": round((rw + vw) / ow, 3)}
    out = {"vocabulary": vocab, "originals": originals, "rewritten": rewritten, "counts": counts}
    (here / "out.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    md = ["# vocab poc — compression through shared vocabulary", "", "## dictionary", ""]
    for t in vocab:
        md.append(f"- **{t['term']}** — {t['meaning']}")
    md += ["", "## functions", ""]
    for n in names:
        md += [f"### {n}", "", f"**original:** {originals[n]}", "",
               f"**rewritten:** {rewritten[n]}", ""]
    md += ["## counts", "", f"- original explanations: {ow} words",
           f"- rewritten explanations: {rw} words", f"- dictionary: {vw} words",
           f"- compressed total: {rw + vw} words", f"- ratio: {counts['ratio']}", ""]
    (here / "OUT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"{len(names)} functions, {len(vocab)} terms, {ow} -> {rw}+{vw}={rw + vw} words, "
          f"ratio {counts['ratio']}, {CALLS[0]} claude calls")


if __name__ == "__main__":
    main()
