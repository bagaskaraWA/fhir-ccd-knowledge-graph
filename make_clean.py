"""Build the review-free clone of the Indonesian thesis tree.

    python make_clean.py

Reads  template_thesis_latex_dteti-id-noreview/
Writes template_thesis_latex_dteti-id-noreview-clean/   (must not already exist)

The clean tree is a derived artefact and is gitignored. Regenerate it whenever the
canonical tree changes; `git status` will not tell you it has gone stale.

The transform
-------------
    \\fromabstract{X}  ->  X          always: keep the value, drop the dagger
    \\crosscheck{X}    ->  X          when X is a VALUE (a number or percentage)
    \\crosscheck{X}    ->  (deleted)  when X is a NOTE (a prose instruction)

The value/note split is the reason this script exists. The documented way to hide the
flags is \\newcommand{\\crosscheck}[1]{}, which silently deletes the argument -- and
roughly a third of the crosschecks in this thesis wrap a figure rather than a note, so
that one-liner would erase numbers like 130.859 and 242.217 from the text without a
warning. is_value() below keeps those and drops only the instructions.

Occurrences inside LaTeX comments are left alone: the preamble and chapter headers
document the macros by name, and rewriting those would garble the documentation.

As a safety net the copied main.tex has both macros redefined to pass their argument
through, so anything the transform misses degrades to showing its content rather than
vanishing.

Note: only *.tex is walked. references.bib keeps its \\crosscheck notes, which are
bibliographic to-dos rather than body text.
"""
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "template_thesis_latex_dteti-id-noreview"
DST = ROOT / "template_thesis_latex_dteti-id-noreview-clean"

if not SRC.is_dir():
    sys.exit(f"ERROR: source tree not found: {SRC}")
if DST.exists():
    sys.exit(f"ERROR: {DST.name} already exists; remove it first")

shutil.copytree(SRC, DST)
print(f"copied {SRC.name} -> {DST.name}")


def spans(txt, macro):
    """Every (start, end, argument) for \\macro{...}, brace-matched so nesting is safe."""
    out, i, pat = [], 0, "\\" + macro + "{"
    while True:
        s = txt.find(pat, i)
        if s == -1:
            return out
        j, depth = s + len(pat), 1
        while j < len(txt) and depth:
            if txt[j] == "{":
                depth += 1
            elif txt[j] == "}":
                depth -= 1
            j += 1
        out.append((s, j, txt[s + len(pat): j - 1]))
        i = j


def in_comment(txt, pos):
    """True if pos sits after an unescaped % on its line."""
    bol = txt.rfind("\n", 0, pos) + 1
    return bool(re.search(r"(?<!\\)%", txt[bol:pos]))


def is_value(arg):
    """A measurement to keep, as opposed to an instruction to delete.

    Values are short, contain a digit, and carry at most one longish word (so that
    '2.150 dari 2.160 sel' and '$+0.067$' count, while a sentence does not)."""
    a = arg.strip()
    if len(a) > 40 or re.search(r"[.!?]\s+[A-Z]", a) or not re.search(r"\d", a):
        return False
    return len(re.findall(r"[A-Za-z]{4,}", a)) <= 1


stats = {"fa": 0, "cc_val": 0, "cc_note": 0}

for tex in sorted(DST.rglob("*.tex")):
    with open(tex, encoding="utf-8", newline="") as f:
        txt = f.read()
    orig = txt
    for macro in ("fromabstract", "crosscheck"):
        while True:
            hit = None
            for s, e, arg in spans(txt, macro):
                if in_comment(txt, s):
                    continue
                hit = (s, e, arg)
                break
            if hit is None:
                break
            s, e, arg = hit
            if macro == "fromabstract":
                txt = txt[:s] + arg + txt[e:]
                stats["fa"] += 1
            elif is_value(arg):
                txt = txt[:s] + arg + txt[e:]
                stats["cc_val"] += 1
            else:
                txt = txt[:s] + txt[e:]
                stats["cc_note"] += 1
    if txt != orig:
        nl = "\r\n" if "\r\n" in orig else "\n"
        lines = [ln.rstrip() for ln in txt.replace("\r\n", "\n").split("\n")]
        txt = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
        with open(tex, "w", encoding="utf-8", newline="") as f:
            f.write(txt.replace("\n", nl))

# Safety net: anything the transform missed degrades to showing its content.
mt = DST / "main.tex"
with open(mt, encoding="utf-8", newline="") as f:
    m = f.read()
m = m.replace(
    "\\newcommand{\\crosscheck}[1]{\\textcolor{red}{\\textbf{[CROSSCHECK: #1]}}}",
    "\\newcommand{\\crosscheck}[1]{#1}")
m = m.replace(
    "\\newcommand{\\fromabstract}[1]{#1\\textsuperscript{\\textcolor{red}{\\dag}}}",
    "\\newcommand{\\fromabstract}[1]{#1}")
with open(mt, "w", encoding="utf-8", newline="") as f:
    f.write(m)

# A compiled PDF copied from the canonical tree would describe different source.
pdf = DST / "main.pdf"
if pdf.exists():
    pdf.unlink()
    print("  removed inherited main.pdf")

print(f"  \\fromabstract unwrapped : {stats['fa']}")
print(f"  \\crosscheck  unwrapped  : {stats['cc_val']}  (values kept)")
print(f"  \\crosscheck  deleted    : {stats['cc_note']}  (notes removed)")
print("  main.tex macros neutralised to pass-through")
