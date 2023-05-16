#!/usr/bin/env python
"""Tests for the quality model"""
from __future__ import annotations

import pytest

import colrev.qm.quality_model
import colrev.record


@pytest.mark.parametrize(
    "author_str, defects",
    [
        ("RAI", ["mostly-all-caps"]),
        ("Rai, Arun and B,", ["incomplete-field"]),
        ("Rai, Arun and B", ["name-format-separators"]),
        # additional title
        ("Rai, PhD, Arun", ["name-format-titles"]),
        ("Rai, Phd, Arun", ["name-format-titles"]),
        ("GuyPhD, Arun", []),  #
        (
            "Rai, Arun; Straub, Detmar",
            ["name-format-separators"],
        ),
        # author without capital letters
        # NOTE: it's not a separator error, should be something more relevant
        (
            "Mathiassen, Lars and jonsson, katrin",
            ["name-format-separators"],
        ),
        (
            "University, Villanova and Sipior, Janice",
            ["erroneous-term-in-field"],
        ),
        (
            "Mourato, Inês and Dias, Álvaro and Pereira, Leandro",
            [],
        ),
        ("DUTTON, JANE E. and ROBERTS, LAURA", ["mostly-all-caps"]),
        ("Rai, Arun et al.", ["incomplete-field"]),
        ("Rai, Arun, and others", ["name-abbreviated"]),
    ],
)
def test_get_quality_defects_author(
    author_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - author field"""
    v_t_record.data["author"] = author_str
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    assert v_t_record.has_quality_defects()
    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["author"][
            "note"
        ].split(",")


@pytest.mark.parametrize(
    "title_str, defects",
    [
        ("EDITORIAL", ["mostly-all-caps"]),
        ("SAMJ�", ["erroneous-symbol-in-field"]),
        ("™", ["erroneous-symbol-in-field"]),
        ("Some_Other_Title", ["erroneous-title-field"]),
        ("Some Other_Title", ["erroneous-title-field"]),
        ("Some 0th3r Title", ["erroneous-title-field"]),
        ("Some other title", []),
        ("Some ...", ["incomplete-field"]),
    ],
)
def test_get_quality_defects_title(
    title_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data["title"] = title_str

    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["title"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "journal_str, defects",
    [
        ("A U-ARCHIT URBAN", ["mostly-all-caps"]),
        ("SOS", ["container-title-abbreviated"]),
        ("SAMJ", ["container-title-abbreviated"]),
        ("SAMJ�", ["erroneous-symbol-in-field"]),
        ("A Journal, Conference", ["inconsistent-content"]),
    ],
)
def test_get_quality_defects_journal(
    journal_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - journal field"""
    v_t_record.data["journal"] = journal_str

    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["journal"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "name_str, defects",
    [
        ("Author, Name and Other, Author", ["thesis-with-multiple-authors"]),
    ],
)
def test_thesis_multiple_authors(
    name_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - thesis with multiple authors"""
    v_t_record.data["ENTRYTYPE"] = "thesis"
    v_t_record.data["author"] = name_str

    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return
    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["author"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "year, defects",
    [
        ("204", ["year-format"]),
        ("2004", []),
    ],
)
def test_year(
    year: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - thesis with multiple authors"""
    v_t_record.data["year"] = year

    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return
    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["year"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "titles, defects",
    [
        (
            ["Test title", "journal", "Test title"],
            ["identical-values-between-title-and-container"],
        ),
        (["Test title", "booktitle", "Test Book"], []),
        (
            ["Test title", "booktitle", "Test title"],
            ["identical-values-between-title-and-container"],
        ),
    ],
)
def test_get_quality_defects_identical_title(
    titles: list,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data["title"] = titles[0]
    v_t_record.data[titles[1]] = titles[2]

    if titles[1] == "booktitle":
        v_t_record.data["ENTRYTYPE"] = "incollection"
        v_t_record.data["publisher"] = "not missing"

    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["title"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


def test_get_quality_defects_testing_missing_field_year_forthcoming(
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
):
    """Tests for when year = forthcoming"""

    v_t_record.data["year"] = "forthcoming"
    del v_t_record.data["volume"]
    del v_t_record.data["number"]
    v_t_record.update_masterdata_provenance(qm=quality_model)
    assert (
        v_t_record.data["colrev_masterdata_provenance"]["volume"]["note"]
        == "not-missing"
    )
    assert (
        v_t_record.data["colrev_masterdata_provenance"]["number"]["note"]
        == "not-missing"
    )


@pytest.mark.parametrize(
    "language, defects",
    [
        ("eng", []),
        ("cend", ["language-format-error"]),
    ],
)
def test_get_quality_defects_language_format(
    language: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
):
    """Tests for invalid language code"""

    v_t_record.data["language"] = language
    v_t_record.update_masterdata_provenance(qm=quality_model)
    from pprint import pprint

    pprint(v_t_record)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["language"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "entrytype, missing, defects",
    [
        ("article", [], []),
        ("inproceedings", ["booktitle"], ["number", "journal"]),
        ("incollection", ["booktitle", "publisher"], []),
        ("inbook", ["publisher", "chapter"], ["journal"]),
    ],
)
def test_get_quality_defects_missing_fields(
    entrytype: str,
    missing: [],
    defects: [],
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
):
    """Tests for missing and inconsistent data for ENTRYTYPE"""

    v_t_record.data["ENTRYTYPE"] = entrytype
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not missing:
        assert not v_t_record.has_quality_defects()
        return
    for n in missing:
        assert v_t_record.data["colrev_masterdata_provenance"][n]["note"] == "missing"
    for n in v_t_record.data["colrev_masterdata_provenance"]:
        if n in missing:
            continue
        assert n in defects
        assert (
            v_t_record.data["colrev_masterdata_provenance"][n]["note"]
            == "inconsistent-with-entrytype"
        )
    assert v_t_record.has_quality_defects()
