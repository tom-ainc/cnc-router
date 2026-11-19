# Copyright (C) 2026 Admix Pty. Ltd. - All Rights Reserved.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""The page for the user of a `systems.json`: one HTML file with no scripts and nothing fetched.

`Model.write` calls `page`; `python3 systems_page.py systems.json` writes the page of a file.
"""

import json
import sys
from html import escape
from pathlib import Path

STYLE = """
:root { --bg: #fff; --fg: #1b1f24; --dim: #5c6670; --line: #d5dae0; --box: #f4f6f8;
  --pass: #1a7f37; --fail: #c62828; --warn: #9a6700; --none: #5c6670; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #14171a; --fg: #e4e8ec; --dim: #98a2ad; --line: #353c44; --box: #1d2125;
    --pass: #4cc26b; --fail: #ff7b72; --warn: #e0a93b; --none: #98a2ad; } }
body { background: var(--bg); color: var(--fg); font: 15px/1.45 system-ui, sans-serif;
  max-width: 1100px; margin: 0 auto; padding: 16px; }
h1 { font-size: 24px; margin: 0 0 4px; } h2 { font-size: 17px; margin: 32px 0 8px; }
.dim { color: var(--dim); } .scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 6px 10px 6px 0; border-bottom: 1px solid var(--line); }
th { color: var(--dim); font-weight: 500; font-size: 13px; }
td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
code { font: 13px ui-monospace, monospace; }
.status { font-weight: 600; white-space: nowrap; }
.pass { color: var(--pass); } .fail { color: var(--fail); }
.not_verified { color: var(--warn); } .cannot_verify { color: var(--none); }
.counts span { margin-right: 16px; }
ul.tree, ul.tree ul { list-style: none; margin: 0; padding-left: 20px; border-left: 1px solid var(--line); }
ul.tree { padding-left: 0; border: 0; } ul.tree li { padding: 3px 0; }
.block { background: var(--box); border: 1px solid var(--line); border-radius: 6px; padding: 8px; margin: 8px 0; }
svg { max-width: 100%; height: auto; } svg text { fill: currentColor; font: 13px system-ui, sans-serif; }
details summary { cursor: pointer; color: var(--dim); }
.problems { border: 1px solid var(--fail); border-radius: 6px; padding: 8px 12px; }
"""

STATUS_TEXT = {"pass": "pass", "fail": "FAIL", "not_verified": "not verified", "cannot_verify": "cannot verify"}
# Rows the user must read first come first.
STATUS_ORDER = ("fail", "not_verified", "cannot_verify", "pass")


def _number(value):
    return "" if value is None else f"{value:.4g}"


def _table(head, rows):
    if not rows:
        return ""
    cells = "".join(f"<th>{escape(h)}</th>" for h in head)
    return f'<div class="scroll"><table><tr>{cells}</tr>{"".join(rows)}</table></div>'


def _row(*cells):
    """A table row. A cell is HTML; a tuple `("n", html)` is a number cell."""
    out = []
    for cell in cells:
        kind, html = cell if isinstance(cell, tuple) else ("", cell)
        out.append(f'<td class="{kind}">{html}</td>')
    return f"<tr>{''.join(out)}</tr>"


def _ids(ids):
    return " ".join(f"<code>{escape(i)}</code>" for i in ids)


def _section(data, key, title, body):
    reason = data.get("skipped", {}).get(key)
    if not body:
        body = f'<p class="dim">{escape(reason) if reason else "Nothing written yet."}</p>'
    return f"<h2>{escape(title)}</h2>{body}"


def _evidence(evidence):
    return "; ".join(f"{escape(str(k))}: {escape(str(v))}" for k, v in evidence.items())


def _before(result):
    """A result's margin in the baseline, or its status there where it had no margin."""
    before = result.get("before")
    if before is None:
        return '<span class="dim">new</span>'
    text = _number(before["margin"]) or STATUS_TEXT[before["status"]]
    return f'{text} <span class="fail">passed before</span>' if result.get("regressed") else text


def _results(data):
    requirements = {r["id"]: r for r in data["requirements"]}
    results = sorted(data["results"], key=lambda r: STATUS_ORDER.index(r["status"]))
    counts = {s: sum(r["status"] == s for r in results) for s in STATUS_ORDER}
    compared = any("before" in r for r in results)
    rows = []
    for result in results:
        r = requirements[result["requirement"]]
        limit = f"{escape(r['kind'])} {_number(r['limit'])} {escape(r['unit'])}" if r["kind"] else ""
        detail = [escape(r["text"])]
        for label, text in (("note", escape(result["note"])), ("evidence", _evidence(result["evidence"]))):
            if text:
                detail.append(f'<span class="dim">{label}: {text}</span>')
        if len(result["cases"]) > 1:
            cases = "".join(
                f'<li><span class="{c["status"]}">{STATUS_TEXT[c["status"]]}</span> {escape(c["case"])}'
                f" {_number(c['measured'])} (margin {_number(c['margin'])})</li>"
                for c in result["cases"]
            )
            detail.append(
                f"<details><summary>{len(result['cases'])} cases; worst: {escape(result['case'])}"
                f"</summary><ul>{cases}</ul></details>"
            )
        rows.append(
            _row(
                f'<span class="status {result["status"]}">{STATUS_TEXT[result["status"]]}</span>',
                f"<code>{escape(r['id'])}</code>",
                "<br>".join(detail),
                _ids(r["applies_to"]),
                ("n", _number(result["measured"])),
                ("n", limit),
                ("n", _number(result["margin"])),
                *([("n", _before(result))] if compared else []),
                f'<span class="dim">{escape(r["source"])}, {escape(r["method"])}</span>',
            )
        )
    summary = "".join(f'<span class="status {s}">{n} {STATUS_TEXT[s]}</span>' for s, n in counts.items() if n)
    head = ["Status", "Id", "Requirement", "Applies to", "Measured", "Limit", "Margin", "Source, method"]
    if compared:
        head.insert(7, "Margin before")
    return f'<p class="counts">{summary}</p>' + _table(head, rows) if rows else ""


def _tree(data):
    children = {}
    for node in data["nodes"]:
        children.setdefault(node["parent"], []).append(node)

    def item(node):
        facts = []
        if node["quantity"] != 1:
            facts.append(f"× {node['quantity']}")
        if node["material"]:
            facts.append(escape(node["material"]))
        total = data.get("totals", {}).get(node["id"])
        if total:
            # A sum with no masses under it says nothing, so it is left out.
            if total["mass_kg"]:
                missing = f" without {_ids(total['no_mass'])}" if total["no_mass"] else ""
                facts.append(f"{_number(total['mass_kg'])} kg in all{missing}")
            if total["cost"]:
                facts.append(f"cost {_number(total['cost'])}")
        elif node["mass_kg"] is not None:
            facts.append(f"{_number(node['mass_kg'])} kg")
        if node["bought"]:
            facts.append("bought")
        if node["shows"]:
            facts.append("drawn as " + ", ".join(escape(s) for s in node["shows"]))
        below = "".join(item(c) for c in children.get(node["id"], []))
        return (
            f"<li><code>{escape(node['id'])}</code> {escape(node['name'])} "
            f'<span class="dim">{" · ".join(facts)}</span>{f"<ul>{below}</ul>" if below else ""}</li>'
        )

    roots = "".join(item(n) for n in children.get(None, []))
    return f'<ul class="tree">{roots}</ul>' if roots else ""


def _block(block, names):
    """One block as a drawing: inputs enter on the left, outputs leave on the right."""
    rows = max(len(block["inputs"]), len(block["outputs"]), 1)
    height, left, right = rows * 26 + 24, 250, 450
    parts = [
        f'<rect x="{left}" y="4" width="{right - left}" height="{height - 8}" rx="6" fill="none" stroke="currentColor"/>',
        f'<text x="{(left + right) / 2}" y="{height / 2 + 4}" text-anchor="middle" font-weight="600">'
        f"{escape(names.get(block['node'], block['node']))}</text>",
    ]
    for ports, x0, x1, text_x, anchor in (
        (block["inputs"], 170, left, 162, "end"),
        (block["outputs"], right, right + 80, right + 88, "start"),
    ):
        for i, port in enumerate(ports):
            y = 25 + i * 26
            unit = f" [{port['unit']}]" if port["unit"] else ""
            parts.append(f'<line x1="{x0}" y1="{y}" x2="{x1 - 7}" y2="{y}" stroke="currentColor"/>')
            parts.append(f'<path d="M{x1} {y} l-8 -4 v8 z" fill="currentColor"/>')
            parts.append(f'<text x="{text_x}" y="{y + 4}" text-anchor="{anchor}">{escape(port["name"] + unit)}</text>')
    label = f"Block of {block['node']}"
    svg = f'<svg viewBox="0 0 700 {height}" width="700" role="img" aria-label="{escape(label)}">{"".join(parts)}</svg>'
    notes = []
    if block["relation"]:
        notes.append(escape(block["relation"]))
    notes.append("runs in the script" if block["runs"] else "not computed")
    return f'<div class="block"><code>{escape(block["node"])}</code> <span class="dim">{" · ".join(notes)}</span><br>{svg}</div>'


def _plain(value):
    """A task detail's value as text: a list's items joined, anything else that is not text as JSON."""
    if isinstance(value, str):
        return escape(value)
    if isinstance(value, list) and all(not isinstance(v, (dict, list)) for v in value):
        return escape(", ".join(str(v) for v in value))
    return escape(json.dumps(value))


def _task(task):
    """The task's details but its kind: a list of objects (concepts, hypotheses) as a table with a
    column for each key, anything else as a line."""
    out = []
    for key, value in task.items():
        if key == "kind":
            continue
        label = escape(str(key).replace("_", " ").capitalize())
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            columns = list(dict.fromkeys(k for v in value for k in v))
            rows = [_row(*(_plain(v.get(c, "")) for c in columns)) for v in value]
            out.append(f"<h2>{label}</h2>" + _table([c.replace("_", " ").capitalize() for c in columns], rows))
        else:
            out.append(f'<p><span class="dim">{label}:</span> {_plain(value)}</p>')
    return "".join(out)


def page(data):
    """The page of a `systems.json` already read, as text."""
    names = {n["id"]: n["name"] for n in data["nodes"]}
    problems = "".join(f"<li>{escape(p)}</li>" for p in data["problems"])
    assumptions = [
        _row(
            f'<span class="status {"pass" if a["confirmed"] else "not_verified"}">'
            f"{'confirmed' if a['confirmed'] else 'not confirmed'}</span>",
            f"<code>{escape(a['id'])}</code>",
            f'{escape(a["text"])}<br><span class="dim">{escape(a["reason"])}</span>',
            _ids(a["affects"]),
        )
        for a in sorted(data["assumptions"], key=lambda a: a["confirmed"])
    ]
    interfaces = [
        _row(
            f"<code>{escape(i['id'])}</code>",
            f"{_ids([i['a']])} ↔ {_ids([i['b']])}",
            escape(i["kind"]),
            escape(i["text"]),
            escape(i["keeps"]),
        )
        for i in data["interfaces"]
    ]
    simulations = [
        _row(f"<code>{escape(s['block'])}</code>", escape(json.dumps(s["inputs"])), escape(json.dumps(s["outputs"])))
        for s in data["simulations"]
    ]
    body = [
        f"<h1>{escape(data['name'])}</h1>",
        f'<p class="dim">Written {escape(data.get("written", ""))} · Task: {escape(data["task"]["kind"].replace("_", " "))}</p>',
        _task(data["task"]),
        f'<div class="problems"><strong>The model has errors</strong><ul>{problems}</ul></div>' if problems else "",
        _section(data, "requirements", "Requirements and results", _results(data)),
        _section(data, "assumptions", "Assumptions", _table(("Status", "Id", "Assumption", "Affects"), assumptions)),
        _section(data, "nodes", "Product tree", _tree(data)),
        _section(data, "interfaces", "Interfaces", _table(("Id", "Between", "Kind", "Now", "Must keep"), interfaces)),
        _section(data, "blocks", "Blocks", "".join(_block(b, names) for b in data["blocks"])),
        f"<h2>Simulations run</h2>{_table(('Block', 'Inputs', 'Outputs'), simulations)}" if simulations else "",
    ]
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(data['name'])}</title><style>{STYLE}</style><body>{''.join(body)}</body></html>"
    )


if __name__ == "__main__":
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "systems.json")
    source.with_suffix(".html").write_text(page(json.loads(source.read_text())))
