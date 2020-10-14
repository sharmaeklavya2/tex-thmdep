#!/usr/bin/env python

"""
Read commands of the form `\\thmdep{v}{u}` from TeX files and use them to create a TikZ
graph containing edges of the form `"\\cref{u}" -> "\\cref{v}"`.
"""

from __future__ import print_function
import sys
import argparse
import re

EDGE_RE = r'\\thmdep(|cref){([^}]+)}{([^}]+)}'
DEFAULT_OPTIONS = {
    'tikz': [
        'nodes={draw, rectangle}',
        'layered layout',
        'sibling distance=10mm',
        'level distance=10mm'
    ],
}


def extract(s, edges, exclude_prefixes):
    for match in re.finditer(EDGE_RE, s, flags=re.MULTILINE):
        lems, thm = match.group(2), match.group(3)
        for lem in lems.split(','):
            if not lem.startswith(exclude_prefixes) and not thm.startswith(exclude_prefixes):
                edges.append((lem, thm))


def output(edges, format, options, ofp):
    nodes = set()
    for (lem, thm) in edges:
        nodes.add(lem)
        nodes.add(thm)
    if format == 'tikz':
        header = '\\begin{tikzpicture}\n\\graph[#1] {'.replace('#1', ', '.join(options))
        print(header, file=ofp)
        for node in nodes:
            print('"#1"/"\\cref{#1}";'.replace('#1', node), file=ofp)
        for (lem, thm) in edges:
            line = '"#2" -> "#1";'.replace('#2', thm).replace('#1', lem)
            print(line, file=ofp)
        print('};\n\\end{tikzpicture}', file=ofp)
    else:
        raise NotImplementedError("format {} is not supported".format(repr(format)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ifpaths', nargs='*', help='paths to input files')
    parser.add_argument('-o', '--output', help='path to output file')
    parser.add_argument('-f', '--format', default='tikz', help='output format')
    parser.add_argument('--option', dest='options', action='append', help='drawing option')
    parser.add_argument('--exclude-prefix', dest='exclude_prefixes', action='append',
        help='labels prefixes to exclude')
    args = parser.parse_args()

    edges = []
    for ifpath in args.ifpaths:
        with open(ifpath) as ifp:
            s = ifp.read()
        extract(s, edges, tuple(args.exclude_prefixes or ()))

    options = args.options or DEFAULT_OPTIONS[args.format]
    if args.output is None:
        output(edges, args.format, options, sys.stdout)
    else:
        with open(args.output, 'w') as ofp:
            output(edges, args.format, options, ofp)


if __name__ == '__main__':
    main()
