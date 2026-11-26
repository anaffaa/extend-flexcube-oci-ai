"""Build the AIDP notebooks (.ipynb) from their readable sources (notebooks/src/*.py).

The .py files are the source of truth. Each "# ---------- Cell N" marker starts a new cell; a leading block of
comments becomes a markdown cell. Run from the repository root after editing any source:

    python3 tools/build_notebooks.py          # writes notebooks/<name>.ipynb next to each src/ folder
    python3 tools/build_notebooks.py --check  # fails if a .ipynb is out of date (use in CI)
"""
import glob, json, os, re, sys

MARKER = re.compile(r"^# (-+ )?Cell \d+")
META = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}}


def build(py_path):
    lines = open(py_path, encoding="utf-8").read().rstrip("\n").split("\n")
    chunks = [[]]
    for line in lines:
        if MARKER.match(line) and chunks[-1]:
            chunks.append([])
        chunks[-1].append(line)
    cells = []
    for i, ch in enumerate(chunks):
        while ch and not ch[-1].strip():
            ch.pop()
        if not ch:
            continue
        if i == 0 and all(l.startswith("#") or not l.strip() for l in ch):
            md = [re.sub(r"^# ?", "", l) + "  \n" for l in ch]
            md[-1] = md[-1].rstrip()
            cells.append({"cell_type": "markdown", "metadata": {}, "source": md})
        else:
            src = [l + "\n" for l in ch]
            src[-1] = src[-1].rstrip("\n")
            cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src})
    return {"cells": cells, "metadata": META, "nbformat": 4, "nbformat_minor": 5}


def main():
    check = "--check" in sys.argv
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stale = 0
    for py in sorted(glob.glob(os.path.join(root, "**", "notebooks", "src", "*.py"), recursive=True)):
        out = os.path.join(os.path.dirname(os.path.dirname(py)), os.path.basename(py)[:-3] + ".ipynb")
        text = json.dumps(build(py), indent=1, ensure_ascii=False) + "\n"
        rel = os.path.relpath(out, root)
        if check:
            if not os.path.exists(out) or open(out, encoding="utf-8").read() != text:
                stale += 1
                print("out of date:", rel)
        else:
            open(out, "w", encoding="utf-8").write(text)
            print("built", rel, len(json.loads(text)["cells"]), "cells")
    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
