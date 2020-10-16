#!/usr/bin/env python

"""
Read commands of the form `\\thmdep{v}{u}` from TeX files and use them to create a TikZ
graph containing edges of the form `"\\cref{u}" -> "\\cref{v}"`.
"""

from __future__ import print_function
import sys
import argparse
import re
from collections import defaultdict, deque


ENTITY_RE = r'\\(thmdep|thmdepcref){([^}]*)}{([^}]*)}|\\(label){([^}]*)}'
DEFAULT_RAW_OPTIONS = {
    'tikz': [
        'nodes={draw, rectangle, align=center}',
        'layered layout',
        'sibling distance=10mm',
        'level distance=15mm'
    ],
}


def warn(msg):
    print('tex-thmdep warning:', msg, file=sys.stderr)


def extract(s, edges, ifpath, exclude_prefixes):
    curr_node = ''
    empty_thm_warned = False
    for match in re.finditer(ENTITY_RE, s, flags=re.MULTILINE):
        if match.group(4) is not None:
            curr_node = match.group(5)
        else:
            lems, thm = match.group(2), match.group(3)
            if thm == '':
                thm = curr_node
                if curr_node == '' and not empty_thm_warned:
                    warn(r'use of empty thm before \label in ' + ifpath)
                    empty_thm_warned = True
            for lem in lems.split(','):
                if not lem.startswith(exclude_prefixes) and not thm.startswith(exclude_prefixes):
                    edges.append((thm, lem))


class VertexInfo(object):
    __slots__ = ('adj', 'radj', 'dist', 'visited')

    def __init__(self):
        self.adj = []
        self.radj = []
        self.dist = None
        self.visited = False


def bfs(nodes):
    q = deque()
    for u, uinf in nodes.items():
        if not uinf.radj:
            q.append(u)
            uinf.dist = 0
    while q:
        u = q.popleft()
        uinf = nodes[u]
        if not uinf.visited:
            uinf.visited = True
            for v in uinf.adj:
                vinf = nodes[v]
                if not vinf.visited:
                    if vinf.dist is None or vinf.dist > uinf.dist + 1:
                        vinf.dist = uinf.dist + 1
                    q.append(v)


def process(edges):
    nodes = defaultdict(VertexInfo)
    seen_edges = set()
    for (u, v) in edges:
        if (u, v) not in seen_edges:
            seen_edges.add((u, v))
            nodes[u].adj.append(v)
            nodes[v].radj.append(u)
    bfs(nodes)
    return nodes


def output(nodes, format, raw_options, show_label, show_dist, ofp):
    if format == 'tikz':
        header = '\\begin{tikzpicture}\n\\graph[#1] {'.replace('#1', ', '.join(raw_options))
        print(header, file=ofp)
        for v, vinf in nodes.items():
            sub_parts = []
            if show_label:
                sub_parts.append((r'\texttt', v))
            if show_dist:
                sub_parts.append(('', 'dist: ' + str(vinf.dist)))
            if sub_parts:
                tinytt_text = r'\\' + r'\\'.join([
                    r'{\tiny#1{#2}}'.replace('#1', x).replace('#2', y)
                    for x, y in sub_parts])
            else:
                tinytt_text = ''
            print(r'"#1"/"\cref{#1}'.replace('#1', v) + tinytt_text + '";', file=ofp)
        for u, uinf in nodes.items():
            for v in uinf.adj:
                line = '"#1" -> "#2";'.replace('#1', u).replace('#2', v)
                print(line, file=ofp)
        print('};\n\\end{tikzpicture}', file=ofp)
    else:
        raise NotImplementedError("format {} is not supported".format(repr(format)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ifpaths', nargs='*', help='paths to input files')
    parser.add_argument('-o', '--output', help='path to output file')
    parser.add_argument('-f', '--format', default='tikz', help='output format')
    parser.add_argument('--raw-option', dest='raw_options', action='append',
        help='option passed directly to output')
    parser.add_argument('--exclude-prefix', dest='exclude_prefixes', action='append',
        help='labels prefixes to exclude')
    parser.add_argument('--show-label', action='store_true', default=False,
        help='show the \\label text in node')
    parser.add_argument('--show-dist', action='store_true', default=False,
        help='show the distance from topmost theorems')
    args = parser.parse_args()

    edges = []
    for ifpath in args.ifpaths:
        with open(ifpath) as ifp:
            s = ifp.read()
        extract(s, edges, ifpath, tuple(args.exclude_prefixes or ()))
    nodes = process(edges)

    raw_options = args.raw_options or DEFAULT_RAW_OPTIONS[args.format]
    if args.output is None:
        output(nodes, args.format, raw_options, args.show_label, args.show_dist, sys.stdout)
    else:
        with open(args.output, 'w') as ofp:
            output(nodes, args.format, raw_options, args.show_label, args.show_dist, ofp)


if __name__ == '__main__':
    main()
