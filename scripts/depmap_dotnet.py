#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministic dependency mapper for .NET/C# codebases (stdlib only).

Implements the kit's dependency-map contract (prompts/01-dependency-map.md).
Parses `using` directives via regex. Unlike Java imports (which name a class),
C# `using` directives name a namespace, so each `using Foo.Bar;` creates
edges to every in-repo file whose `namespace` declaration matches `Foo.Bar`.
System.* and Microsoft.* (BCL/runtime) are excluded, as are any namespaces
that don't resolve to in-repo files (third-party).

Handles file-scoped namespaces (`namespace Foo.Bar;`) and block-scoped
(`namespace Foo.Bar { ... }`). `using static`, `global using`, and alias
usings (`using X = ...`) are parsed for the namespace portion.

Usage:
  python3 depmap_dotnet.py --root path/to/repo --out path/to/migration/depmap
Output: edges.tsv, order.txt, cycles.txt (same contract as depmap_python.py)

Test: python3 scripts/depmap_dotnet.py --root fixtures/dotnet --out /tmp/depmap-dotnet && diff /tmp/depmap-dotnet/edges.tsv fixtures/dotnet/expected_edges.tsv && diff /tmp/depmap-dotnet/cycles.txt fixtures/dotnet/expected_cycles.txt && diff /tmp/depmap-dotnet/order.txt fixtures/dotnet/expected_order.txt
"""

import argparse
import re
import sys
from pathlib import Path

USING_RE = re.compile(
    r"^\s*(?:global\s+)?using\s+(?:static\s+)?([\w.]+)\s*;", re.MULTILINE
)
ALIAS_USING_RE = re.compile(
    r"^\s*(?:global\s+)?using\s+\w+\s*=\s*([\w.]+)\s*;", re.MULTILINE
)
NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+([\w.]+)\s*[;{]", re.MULTILINE
)
STDLIB_PREFIXES = ("System", "Microsoft")
SKIP_DIRS = {".git", "bin", "obj", "generated", "node_modules", "vendor"}


def find_cs_files(root: Path):
    return sorted(
        p for p in root.rglob("*.cs")
        if not any(part in SKIP_DIRS or part.startswith(".")
                   for part in p.relative_to(root).parts)
    )


def build_namespace_index(files, root):
    """Map namespace -> list of repo-relative paths declaring it."""
    ns_to_files = {}
    file_ns = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        m = NAMESPACE_RE.search(text)
        ns = m.group(1) if m else ""
        file_ns[rel] = ns
        ns_to_files.setdefault(ns, []).append(rel)
    return ns_to_files, file_ns


def extract_edges(files, root):
    ns_to_files, file_ns = build_namespace_index(files, root)
    rel = {p: p.relative_to(root).as_posix() for p in files}
    edges = set()
    for path in files:
        src_rel = rel[path]
        text = path.read_text(encoding="utf-8", errors="replace")
        used_ns = set()
        for m in USING_RE.finditer(text):
            used_ns.add(m.group(1))
        for m in ALIAS_USING_RE.finditer(text):
            ns = m.group(1)
            while ns:
                if ns in ns_to_files:
                    used_ns.add(ns)
                    break
                ns = ns.rpartition(".")[0]
        for ns in used_ns:
            if ns.startswith(STDLIB_PREFIXES):
                continue
            # try exact namespace match, then walk up for static usings
            candidates = []
            ns_probe = ns
            while ns_probe:
                if ns_probe in ns_to_files:
                    candidates = ns_to_files[ns_probe]
                    break
                ns_probe = ns_probe.rpartition(".")[0]
            for dst in candidates:
                if dst != src_rel:
                    edges.add((src_rel, dst))
    return sorted(edges), sorted(rel.values())


def tarjan_scc(nodes, edges):
    adj = {n: [] for n in nodes}
    for a, b in edges:
        adj[a].append(b)
    for n in adj:
        adj[n].sort()
    counter = [0]
    stack, on_stack = [], set()
    idx, low = {}, {}
    sccs = []
    for start in nodes:
        if start in idx:
            continue
        work = [(start, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                idx[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack.add(node)
            recurse = False
            for i in range(pi, len(adj[node])):
                succ = adj[node][i]
                if succ not in idx:
                    work[-1] = (node, i + 1)
                    work.append((succ, 0))
                    recurse = True
                    break
                elif succ in on_stack:
                    low[node] = min(low[node], idx[succ])
            if recurse:
                continue
            if low[node] == idx[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(sorted(scc))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return sccs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    files = find_cs_files(root)
    edges, nodes = extract_edges(files, root)
    sccs = tarjan_scc(nodes, edges)
    cycles = [s for s in sccs if len(s) > 1]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "edges.tsv").write_text(
        "from\tto\n" + "".join(f"{a}\t{b}\n" for a, b in edges))
    (args.out / "order.txt").write_text(
        "# migration order: one batch per line, dependencies first\n"
        + "".join("\t".join(s) + "\n" for s in sccs))
    (args.out / "cycles.txt").write_text(
        f"# strongly connected components > 1 file: {len(cycles)}\n"
        + "".join("\t".join(s) + "\n" for s in cycles))
    print(f"files={len(files)} edges={len(edges)} batches={len(sccs)} cycles={len(cycles)}")
    if len(files) > 1 and not edges:
        print(
            "WARN: 0 edges across multiple files. If these files use types "
            "from each other, check that namespace declarations match the "
            "using directives and that --root points to the solution root.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
