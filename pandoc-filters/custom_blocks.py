#!/usr/bin/env python3
"""
Pandoc filter: convert fenced divs (:::klinik, :::tanım, etc.)
to styled HTML divs or LaTeX tcolorbox environments.
"""
import sys
from pandocfilters import toJSONFilter, RawBlock, Div, stringify

BLOCKS = {
    'klinik':    ('klinik', 'klinik'),
    'tanım':     ('tanim',  'tanım'),
    'mnemonics': ('mnemonics', 'mnemonics'),
    'vaka':      ('vaka',   'vaka'),
    'dikkat':    ('dikkat', 'dikkat'),
    'not':       ('notbox', 'not'),
}


def custom_blocks(key, value, fmt, meta):
    if key != 'Div':
        return None
    attrs, content = value
    _, classes, _ = attrs

    for cls in classes:
        cls_lower = cls.lower()
        if cls_lower in BLOCKS:
            latex_env, html_cls = BLOCKS[cls_lower]
            if fmt in ('latex', 'pdf'):
                return [
                    RawBlock('latex', f'\\begin{{{latex_env}}}'),
                    *content,
                    RawBlock('latex', f'\\end{{{latex_env}}}'),
                ]
            elif fmt in ('html', 'html5'):
                return Div(['', [html_cls, 'custom-block'], []], content)
    return None


if __name__ == '__main__':
    toJSONFilter(custom_blocks)
