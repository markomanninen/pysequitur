# Article: Giving AI agents an eye for repetition

Published on Substack on 27 October 2026: [https://markotmanninen.substack.com/p/giving-ai-agents-an-eye-for-repetition](https://markotmanninen.substack.com/p/giving-ai-agents-an-eye-for-repetition)

A Substack article on pysequitur: how Sequitur works and where it comes from,
using the library from Python, through its MCP server and in its visualizer,
what makes it fast, how it compares with nine other implementations in five
languages, and what its tools changed for Claude agents asked about repetition.

| File | Contents |
|---|---|
| [pysequitur_article.md](pysequitur_article.md) | The published text, with its tables as markdown |
| [pysequitur_article_substack.md](pysequitur_article_substack.md) | The same text for Substack, with the tables as images |
| [pysequitur_article_substack.html](pysequitur_article_substack.html) | Its body as HTML, the source the Substack draft is pasted from |
| [article_images/](article_images/) | Header image, the two table images and three screenshots of the visualizer |
| [header_image_prompts.md](header_image_prompts.md) | The prompt the header image was generated from with Figma |
| [make_header.py](make_header.py) | Draws an alternative header, `header_drawn.png`, from pysequitur's analysis of "Pease Porridge Hot" |
| [make_images.py](make_images.py) | Renders the table images and the screenshots with headless Chrome |
| [make_substack.py](make_substack.py) | Makes the Substack markdown and HTML from the article |

The numbers come from [doc/performance.md](../performance.md) and the scripts in
[benchmarks/](../../benchmarks/): the comparison with other implementations in
[benchmarks/other/](../../benchmarks/other/), and the agent field test, with
its questions, transcripts and scoring, in
[benchmarks/field_test/](../../benchmarks/field_test/). The research behind the
history of Sequitur is in [doc/background.md](../background.md).
