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


COMMENT_RE = r'(?<!\\)%[^\n]*\n'
ENTITY_RE = r'\\(thmdep|thmdepcref){([^}]*)}{([^}]*)}|\\(label|begin|end){([^}]*)}'
DEFAULT_IGNORE_ENVS = ('comment', 'optional', 'obsolete', 'error')
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


def extract(s, edges, ifpath, options):
    curr_node = ''
    ignore_mode = False
    empty_thm_warned = False
    s = re.sub(COMMENT_RE, '\n', s, flags=re.MULTILINE)
    for match in re.finditer(ENTITY_RE, s, flags=re.MULTILINE):
        if match.group(4) is not None:
            cmd, arg = match.group(4), match.group(5)
            if ignore_mode:
                if cmd == 'end' and arg in options['ignore_envs']:
                    ignore_mode = False
            else:
                if cmd == 'begin' and arg in options['ignore_envs']:
                    ignore_mode = True
                elif cmd == 'label':
                    curr_node = arg
        elif not ignore_mode:
            lems, thm = match.group(2), match.group(3)
            if thm == '':
                thm = curr_node
                if curr_node == '' and not empty_thm_warned:
                    warn(r'use of empty thm before \label in ' + ifpath)
                    empty_thm_warned = True
            for lem in lems.split(','):
                if (not lem.startswith(options['exclude_prefixes'])
                        and not thm.startswith(options['exclude_prefixes'])):  # noqa
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


def process(edges, options):
    nodes = defaultdict(VertexInfo)
    seen_edges = set()
    for (u, v) in edges:
        if (u, v) not in seen_edges:
            seen_edges.add((u, v))
            nodes[u].adj.append(v)
            nodes[v].radj.append(u)
    bfs(nodes)

    bad_nodes = set()
    if options['max_dist'] is not None:
        max_dist = options['max_dist']
        for v, vinf in nodes.items():
            if vinf.dist > max_dist:
                bad_nodes.add(v)
    for v in bad_nodes:
        del nodes[v]
    for u, uinf in nodes.items():
        uinf.adj = [v for v in uinf.adj if v in nodes]
        uinf.radj = [v for v in uinf.radj if v in nodes]

    return nodes


def output(nodes, format, options, raw_options, ofp):
    if format == 'tikz':
        header = '\\begin{tikzpicture}\n\\graph[#1] {'.replace('#1', ', '.join(raw_options))
        print(header, file=ofp)
        for v, vinf in nodes.items():
            sub_parts = []
            if options['show_label']:
                sub_parts.append((r'\texttt', v))
            if options['show_dist']:
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
    parser.add_argument('--ignore-env', dest='ignore_envs', action='append',
        help='envs to ignore')
    parser.add_argument('--show-label', action='store_true', default=False,
        help='show the \\label text in node')
    parser.add_argument('--show-dist', action='store_true', default=False,
        help='show the distance from topmost theorems')
    parser.add_argument('--max-dist', type=int,
        help='maximum distance allowed for a node to be displayed')
    args = parser.parse_args()

    option_names = ['exclude_prefixes', 'ignore_envs', 'max_dist', 'show_label', 'show_dist']
    args.exclude_prefixes = tuple(args.exclude_prefixes or ())
    args.ignore_envs = tuple(args.ignore_envs or DEFAULT_IGNORE_ENVS)
    arg_vars = vars(args)
    options = {optname: arg_vars[optname] for optname in option_names}
    raw_options = args.raw_options or DEFAULT_RAW_OPTIONS[args.format]

    edges = []
    for ifpath in args.ifpaths:
        with open(ifpath) as ifp:
            s = ifp.read()
        extract(s, edges, ifpath, options)
    nodes = process(edges, options)

    if args.output is None:
        output(nodes, args.format, options, raw_options, sys.stdout)
    else:
        with open(args.output, 'w') as ofp:
            output(nodes, args.format, options, raw_options, ofp)


if __name__ == '__main__':
    main()
