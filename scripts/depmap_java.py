#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministic dependency mapper for Java codebases (stdlib only).

Implements the kit's dependency-map contract (prompts/01-dependency-map.md).
Parses `import` declarations via regex — the syntax is unambiguous (same
rationale as depmap_c.py for #include). Fully-qualified class names are
resolved against an index built from package declarations + filenames.
JDK stdlib (java.*, javax.*), third-party imports that don't resolve to an
in-repo file, and static imports are all handled: only in-repo edges are
emitted.

Wildcard imports (import com.example.*) expand to all in-repo classes in
that package.

Usage:
  python3 depmap_java.py --root path/to/repo --out path/to/migration/depmap
Output: edges.tsv, order.txt, cycles.txt (same contract as depmap_python.py)

Test: python3 scripts/depmap_java.py --root fixtures/java --out /tmp/depmap-java && diff /tmp/depmap-java/edges.tsv fixtures/java/expected_edges.tsv && diff /tmp/depmap-java/cycles.txt fixtures/java/expected_cycles.txt && diff /tmp/depmap-java/order.txt fixtures/java/expected_order.txt
"""

import argparse
import re
import sys
from pathlib import Path

IMPORT_RE = re.compile(
    r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;", re.MULTILINE
)
PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
SKIP_DIRS = {".git", "build", "target", "generated", "node_modules", "vendor"}


def find_java_files(root: Path):
    return sorted(
        p for p in root.rglob("*.java")
        if not any(part in SKIP_DIRS or part.startswith(".")
                   for part in p.relative_to(root).parts)
    )


def build_fqn_index(files, root):
    """Map fully-qualified class name -> repo-relative path."""
    index = {}
    pkg_members = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        m = PACKAGE_RE.search(text)
        pkg = m.group(1) if m else ""
        class_name = path.stem
        fqn = f"{pkg}.{class_name}" if pkg else class_name
        rel = path.relative_to(root).as_posix()
        index[fqn] = rel
        pkg_members.setdefault(pkg, []).append(fqn)
    return index, pkg_members


def extract_edges(files, root):
    index, pkg_members = build_fqn_index(files, root)
    rel = {p: p.relative_to(root).as_posix() for p in files}
    edges = set()
    for path in files:
        src_rel = rel[path]
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in IMPORT_RE.finditer(text):
            imp = m.group(1)
            if imp.startswith("java.") or imp.startswith("javax."):
                continue
            if imp.endswith(".*"):
                pkg = imp[:-2]
                for member_fqn in pkg_members.get(pkg, []):
                    dst = index[member_fqn]
                    if dst != src_rel:
                        edges.add((src_rel, dst))
            elif imp in index:
                dst = index[imp]
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
    files = find_java_files(root)
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
            "WARN: 0 edges across multiple files. If these files import each "
            "other, --root is probably pointing at the wrong directory, or "
            "imports use fully-qualified names that don't match the directory "
            "layout (convention: com.example.Foo -> com/example/Foo.java).",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
