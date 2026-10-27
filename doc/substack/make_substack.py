"""
Makes the Substack versions of the article from pysequitur_article.md:

    python doc/substack/make_substack.py

pysequitur_article_substack.md is the article with the header image after the
subtitle and each table replaced by its image from make_images.py, in order.
pysequitur_article_substack.html is its body for pasting into the Substack
editor, made with pandoc. The title and subtitle go into their own fields, and
each image becomes a paragraph IMAGEMARK_name, where the image is uploaded.
"""
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARTICLE = HERE / 'pysequitur_article.md'
TABLES = ['table_speed', 'table_agents']


def substack_markdown(text):
    lines = text.split('\n')
    # title, blank, subtitle, then the header image
    out = lines[:3] + ['', '![](article_images/header.png)']
    tables = iter(TABLES)
    in_table = False
    for line in lines[3:]:
        if line.startswith('|'):
            if not in_table:
                out.append('![](article_images/%s.png)' % next(tables))
            in_table = True
            continue
        in_table = False
        out.append(line)
    assert next(tables, None) is None, 'fewer tables than images'
    return '\n'.join(out)


def substack_html(markdown):
    body = markdown.split('\n', 4)[4]  # without the title and subtitle
    html = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '--wrap=none'], input=body,
                          capture_output=True, text=True, check=True).stdout
    html = re.sub(r'<figure>\s*<img src="article_images/([\w-]+)\.png"[^>]*/>.*?</figure>',
                  r'<p>IMAGEMARK_\1</p>', html, flags=re.S)
    html = re.sub(r'<p><img src="article_images/([\w-]+)\.png"[^>]*/></p>', r'<p>IMAGEMARK_\1</p>', html)
    assert '<img' not in html
    return html


def main():
    markdown = substack_markdown(ARTICLE.read_text())
    (HERE / 'pysequitur_article_substack.md').write_text(markdown)
    (HERE / 'pysequitur_article_substack.html').write_text(substack_html(markdown))


if __name__ == '__main__':
    main()
