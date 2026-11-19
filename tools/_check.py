#!/usr/bin/env python3
"""Checks a file after editing. Used by 'edit'. Exit 0 = fine, 1 = problem, 2 = can't check this type."""
import ast
import json
import re
import sys

# One tap, or an undo line from Life Tracker v8 ("undo 2026-11-15 08:10 coffee", which can itself be undone)
LOG_LINE = re.compile(r"^\d{4}-\d{2}-\d{2},\d{2}:\d{2},(undo \d{4}-\d{2}-\d{2} \d{2}:\d{2} )*[a-z0-9][a-z0-9-]*$")
# Home Assistant's File integration starts the file with a title line and a line of dashes
HEADER = re.compile(r"^(.*\(Log started: .*\)|-{10,})\s*$")


def check_yaml(text):
    try:
        import yaml
    except ImportError:
        return 2, "can't check YAML here (PyYAML isn't installed)"

    # Home Assistant reads YAML with libyaml (CSafeLoader). The pure-Python loader is stricter
    # (it rejects e.g. "{text: Log a coffee?}"), so use libyaml too when it's there.
    class Loader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
        pass

    # Home Assistant tags like !include and !secret: accept them without following them
    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    try:
        yaml.load(text, Loader=Loader)
    except yaml.YAMLError as e:
        return 1, f"YAML error: {e}"
    return 0, "YAML is valid"


def bad_log_lines(text):
    bad, top = [], True
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if top and HEADER.match(line):   # header lines are fine, but only above the first tap
            continue
        top = False
        if not LOG_LINE.match(line):
            bad.append((n, line))
    return bad


def main(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if path.endswith(".py"):
        try:
            ast.parse(text, filename=path)
            return 0, "Python is valid"
        except SyntaxError as e:
            return 1, f"Python error on line {e.lineno}: {e.msg}"
    if path.endswith(".json"):
        try:
            json.loads(text)
            return 0, "JSON is valid"
        except json.JSONDecodeError as e:
            return 1, f"JSON error on line {e.lineno}: {e.msg}"
    if path.endswith((".yaml", ".yml")):
        return check_yaml(text)
    if path.endswith("tag_log.csv"):
        bad = bad_log_lines(text)
        if bad:
            return 1, "These lines don't look like 'YYYY-MM-DD,HH:MM,entry':\n" + "\n".join(
                f"  line {n}: {line}" for n, line in bad[:10])
        return 0, "every log line looks right"
    return 2, "no automatic check for this type of file"


if __name__ == "__main__":
    code, msg = main(sys.argv[1])
    print(msg)
    sys.exit(code)
