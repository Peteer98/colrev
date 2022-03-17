<p align="center">
<img src="docs/figures/logo_small.png" width="400">
</p>

# CoLRev Framework

[![License](https://img.shields.io/github/license/geritwagner/colrev_core.svg)](https://github.com/geritwagner/colrev_core/releases/)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![GitHub release](https://img.shields.io/github/v/release/geritwagner/colrev_core.svg)](https://github.com/geritwagner/colrev_core/releases/)

This repository contains the core engine for the CoLRev framework (**C**olaborative **L**iterature **Rev**iews), the reference implementation, and documentation on the CoLRev standard.

# Usage and Documentation

See the [documentation](docs/source/index.rst).

# Credits

The reference implementation builds on the shoulders of amazing projects (growing giants) and benefits from their ongoing improvements

- [GitPython](https://github.com/gitpython-developers/GitPython), which is available under a [BSD 3-Clause License](https://github.com/gitpython-developers/GitPython/blob/main/LICENSE). [![GitPython](https://img.shields.io/github/commit-activity/y/gitpython-developers/GitPython?color=green&style=plastic)](https://github.com/gitpython-developers/GitPython)
- [pre-commit](https://github.com/pre-commit/pre-commit), which is available under an [MIT License](https://github.com/pre-commit/pre-commit/blob/master/LICENSE). [![pre-commit](https://img.shields.io/github/commit-activity/y/pre-commit/pre-commit?color=green&style=plastic)](https://github.com/pre-commit/pre-commit.six)
- [docker-py](https://github.com/docker/docker-py), which is available under an [Apache-2.0 License](https://github.com/docker/docker-py/blob/master/LICENSE). [![docker-py](https://img.shields.io/github/commit-activity/y/docker/docker-py?color=green&style=plastic)](https://github.com/docker/docker-py)
- [dedupe](https://github.com/dedupeio/dedupe), which is available under an [MIT License](https://github.com/dedupeio/dedupe/blob/master/LICENSE). [![dedupe](https://img.shields.io/github/commit-activity/y/dedupeio/dedupe?color=green&style=plastic)](https://github.com/dedupeio/dedupe)
- [pandas](https://github.com/pandas-dev/pandas), which is available under a [BSD 3-Clause License](https://github.com/pandas-dev/pandas/blob/master/LICENSE). [![pandas](https://img.shields.io/github/commit-activity/y/pandas-dev/pandas?color=green&style=plastic)](https://github.com/pandas-dev/pandas)
- [PDFMiner.six](https://github.com/pdfminer/pdfminer.six), which is available under an [MIT License](https://github.com/pdfminer/pdfminer.six/blob/develop/LICENSE). [![PDFMiner.six](https://img.shields.io/github/commit-activity/y/pdfminer/pdfminer.six?color=green&style=plastic)](https://github.com/pdfminer/pdfminer.six)
- [bibtexparser](https://github.com/sciunto-org/python-bibtexparser), which is available under a [BSD License](https://github.com/sciunto-org/python-bibtexparser/blob/master/COPYING).

Dynamically loaded

- [git](https://github.com/git/git), which is available under a [GNU Public License 2 (GPL 2)](https://github.com/git/git/blob/master/COPYING). [![git](https://img.shields.io/github/commit-activity/y/git/git?color=green&style=plastic)](https://github.com/git/git)
- [Zotero translation services](https://github.com/zotero/translation-server), which are available under a [GNU Public License (GPL)](https://github.com/zotero/translation-server/blob/master/COPYING). [![ocrmypdf](https://img.shields.io/github/commit-activity/y/zotero/translation-server?color=green&style=plastic)](https://github.com/zotero/translation-server), which builds on
- [Zotero translators](https://github.com/zotero/translators), which are available under a [GNU Public License (GPL)](https://github.com/zotero/translators/blob/master/COPYING). [![ocrmypdf](https://img.shields.io/github/commit-activity/y/zotero/translators?color=green&style=plastic)](https://github.com/zotero/translators)
- [GROBID](https://github.com/kermitt2/grobid), which is available under an [Apache 2.0 License](https://github.com/kermitt2/grobid/blob/master/LICENSE). [![GROBID](https://img.shields.io/github/commit-activity/y/kermitt2/grobid?color=green&style=plastic)](https://github.com/kermitt2/grobid)
- [OCRmyPDF](https://github.com/jbarlow83/OCRmyPDF), which is available under a [Mozilla Public License 2.0 (MPL-2.0)](https://github.com/jbarlow83/OCRmyPDF/blob/master/LICENSE). [![ocrmypdf](https://img.shields.io/github/commit-activity/y/jbarlow83/OCRmyPDF?color=green&style=plastic)](https://github.com/jbarlow83/OCRmyPDF), which builds on
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), which is available under an [Apache-2.0 License](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE). [![docker-py](https://img.shields.io/github/commit-activity/y/tesseract-ocr/tesseract?color=green&style=plastic)](https://github.com/tesseract-ocr/tesseract)
- [pandoc](https://github.com/jgm/pandoc), which is available under a [GNU Public License 2 (GPL 2)](https://github.com/jgm/pandoc/blob/master/COPYRIGHT). [![ocrmypdf](https://img.shields.io/github/commit-activity/y/jgm/pandoc?color=green&style=plastic)](https://github.com/jgm/pandoc)
- [CSL](https://github.com/citation-style-language/styles), which is available under the [Creative Commons Attribution-ShareAlike 3.0 Unported license](https://github.com/citation-style-language/styles). [![ocrmypdf](https://img.shields.io/github/commit-activity/y/citation-style-language/styles?color=green&style=plastic)](https://github.com/citation-style-language/styles)
- [Elasticsearch](https://github.com/elastic/elasticsearch), which is available under the [(i) a dual license under the Server Side Public License, v 1 and the Elastic License 2.0 or (ii) an Apache License 2.0 compatible license or (iii) solely under the Elastic License 2.0](https://github.com/elastic/elasticsearch/blob/master/LICENSE.txt). [![elasticsearch](https://img.shields.io/github/commit-activity/y/elastic/elasticsearch?color=green&style=plastic)](https://github.com/elastic/elasticsearch)


For meta-data preparation and PDF retrieval, we rely on the following data sources

- [Crossref](https://www.crossref.org/) with over 125,000,000 curated metadata records across disciplines
- [Semantic Scholar](https://www.semanticscholar.org/) with over 175,000,000 records across disciplines
- [dblp](https://dblp.org/) with over 5,750,000 curated metadata records in the IT/IS disciplines
- [Open Library](https://openlibrary.org/) with over 20,000,000 curated metadata records (books)
- [Unpaywall](https://unpaywall.org/) with over 30,000,000 free papers

# Contributing, changes, and releases


Contributions, code and features are always welcome

- See [contributing guidelines](CONTRIBUTING.md).
- Bug reports or feedback? Please use the [issue tracker](https://github.com/geritwagner/colrev_core/issues) and let us know.
- To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

For further information, see [changes](CHANGELOG.md) and [releases](https://github.com/geritwagner/colrev_core/releases).

# License

This project is distributed under the [MIT License](LICENSE) the documentation is distributed under the [CC-0](https://creativecommons.org/publicdomain/zero/1.0/) license.
If you contribute to the project, you agree to share your contribution following these licenses.
