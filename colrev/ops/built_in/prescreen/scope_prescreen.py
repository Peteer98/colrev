#! /usr/bin/env python
"""Prescreen based on specified scope"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.language_service
import colrev.env.package_manager
import colrev.record

if typing.TYPE_CHECKING:
    import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class ScopePrescreen(JsonSchemaMixin):

    """Rule-based prescreen (scope)"""

    settings: ScopePrescreenSettings
    ci_supported: bool = True

    @dataclass
    class ScopePrescreenSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for ScopePrescreen"""

        # pylint: disable=invalid-name
        # pylint: disable=too-many-instance-attributes

        endpoint: str
        TimeScopeFrom: typing.Optional[int]
        TimeScopeTo: typing.Optional[int]
        LanguageScope: typing.Optional[list]
        ExcludeComplementaryMaterials: typing.Optional[bool]
        OutletInclusionScope: typing.Optional[dict]
        OutletExclusionScope: typing.Optional[dict]
        ENTRYTYPEScope: typing.Optional[list]

        _details = {
            "TimeScopeFrom": {
                "tooltip": "Lower bound for the time scope",
                "min": 1900,
                "max": 2050,
            },
            "TimeScopeTo": {
                "tooltip": "Upper bound for the time scope",
                "min": 1900,
                "max": 2050,
            },
            "LanguageScope": {"tooltip": "Language scope"},
            "ExcludeComplementaryMaterials": {
                "tooltip": "Whether complementary materials (coverpages etc.) are excluded"
            },
            "OutletInclusionScope": {
                "tooltip": "Particular outlets that should be included (exclusively)"
            },
            "OutletExclusionScope": {
                "tooltip": "Particular outlets that should be excluded"
            },
            "ENTRYTYPEScope": {
                "tooltip": "Particular ENTRYTYPEs that should be included (exclusively)"
            },
        }

    settings_class = ScopePrescreenSettings

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
    ) -> None:
        if "TimeScopeFrom" in settings:
            settings["TimeScopeFrom"] = int(settings["TimeScopeFrom"])
            assert settings["TimeScopeFrom"] > 1900
            assert settings["TimeScopeFrom"] < 2100
        if "TimeScopeTo" in settings:
            settings["TimeScopeTo"] = int(settings["TimeScopeTo"])
            assert settings["TimeScopeTo"] > 1900
            assert settings["TimeScopeTo"] < 2100
        if "LanguageScope" in settings:
            self.language_service = colrev.env.language_service.LanguageService()
            self.language_service.validate_iso_639_3_language_codes(
                lang_code_list=settings["LanguageScope"]
            )
        self.review_manager = prescreen_operation.review_manager
        self.settings = self.settings_class.load_settings(data=settings)

        self.predatory_journals_beal = self.__load_predatory_journals_beal()

        self.title_complementary_materials_keywords = (
            colrev.env.utils.load_complementary_material_keywords()
        )

    def __load_predatory_journals_beal(self) -> dict:
        predatory_journals = {}

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/ops/predatory_journals_beall.csv")
        )

        if filedata:
            for pred_journal in filedata.decode("utf-8").splitlines():
                predatory_journals[pred_journal.lower()] = pred_journal.lower()

        return predatory_journals

    def __conditional_prescreen_entrytypes(self, record: colrev.record.Record) -> None:
        if self.settings.ENTRYTYPEScope:
            if record.data["ENTRYTYPE"] not in self.settings.ENTRYTYPEScope:
                record.prescreen_exclude(reason="not in ENTRYTYPEScope")

    def __conditional_prescreen_outlets_exclusion(
        self, record: colrev.record.Record
    ) -> None:
        if self.settings.OutletExclusionScope:
            if "values" in self.settings.OutletExclusionScope:
                for resource in self.settings.OutletExclusionScope["values"]:
                    for key, value in resource.items():
                        if key in record.data and record.data.get(key, "") == value:
                            record.prescreen_exclude(reason="in OutletExclusionScope")
            if "list" in self.settings.OutletExclusionScope:
                for resource in self.settings.OutletExclusionScope["list"]:
                    for key, value in resource.items():
                        if not (
                            key == "resource" and value == "predatory_journals_beal"
                        ):
                            continue
                        if "journal" not in record.data:
                            continue
                        if (
                            record.data["journal"].lower()
                            in self.predatory_journals_beal
                        ):
                            record.prescreen_exclude(reason="predatory_journals_beal")

    def __conditional_prescreen_outlets_inclusion(
        self, record: colrev.record.Record
    ) -> None:
        if self.settings.OutletInclusionScope:
            in_outlet_scope = False
            if "values" in self.settings.OutletInclusionScope:
                for outlet in self.settings.OutletInclusionScope["values"]:
                    for key, value in outlet.items():
                        if key in record.data and record.data.get(key, "") == value:
                            in_outlet_scope = True
            if not in_outlet_scope:
                record.prescreen_exclude(reason="not in OutletInclusionScope")

    def __conditional_prescreen_timescope(self, record: colrev.record.Record) -> None:
        if self.settings.TimeScopeFrom:
            if int(record.data.get("year", 0)) < self.settings.TimeScopeFrom:
                record.prescreen_exclude(
                    reason="not in TimeScopeFrom " f"(>{self.settings.TimeScopeFrom})"
                )

        if self.settings.TimeScopeTo:
            if int(record.data.get("year", 5000)) > self.settings.TimeScopeTo:
                record.prescreen_exclude(
                    reason="not in TimeScopeTo " f"(<{self.settings.TimeScopeTo})"
                )

    def __conditional_prescreen_complementary_materials(
        self, record: colrev.record.Record
    ) -> None:
        if self.settings.ExcludeComplementaryMaterials:
            if "title" in record.data:
                if (
                    record.data["title"].lower()
                    in self.title_complementary_materials_keywords
                ):
                    record.prescreen_exclude(reason="complementary material")

    def __conditional_presecreen_not_in_ranking(
        self, record: colrev.record.Record
    ) -> None:
        if record.data["journal_ranking"] == "not included in a ranking":
            record.set_status(
                target_state=colrev.record.RecordState.rev_prescreen_excluded
            )

    def __conditional_prescreen(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        record_dict: dict,
        include_unranked_journals: bool,
    ) -> None:
        if record_dict["colrev_status"] != colrev.record.RecordState.md_processed:
            return

        # Note : LanguageScope is covered in prep
        # because dedupe cannot handle merges between languages
        record = colrev.record.Record(data=record_dict)

        self.__conditional_prescreen_entrytypes(record=record)
        self.__conditional_prescreen_outlets_inclusion(record=record)
        self.__conditional_prescreen_outlets_exclusion(record=record)
        self.__conditional_prescreen_timescope(record=record)
        self.__conditional_prescreen_complementary_materials(record=record)

        if include_unranked_journals is True:
            self.__conditional_presecreen_not_in_ranking(record=record)

        if (
            record.data["colrev_status"]
            == colrev.record.RecordState.rev_prescreen_excluded
        ):
            self.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(50, " ")
                + "Prescreen excluded (automatically)"
            )
        elif (
            len(self.review_manager.settings.prescreen.prescreen_package_endpoints) == 1
        ):
            record.set_status(
                target_state=colrev.record.RecordState.rev_prescreen_included
            )
            self.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(50, " ")
                + "Prescreen included (automatically)"
            )

    def add_endpoint(self, *, params: dict) -> None:
        """Add  the scope_prescreen as an endpoint"""

        for (
            existing_scope_prescreen
        ) in self.review_manager.settings.prescreen.prescreen_package_endpoints:
            if existing_scope_prescreen["endpoint"] != "colrev.scope_prescreen":
                continue
            self.review_manager.logger.info(
                "Integrating into existing colrev.scope_prescreen"
            )
            for key, value in params.items():
                if (
                    key in existing_scope_prescreen
                    and existing_scope_prescreen[key] != value
                ):
                    self.review_manager.logger.info(
                        f"Replacing {key} ({existing_scope_prescreen[key]} -> {value})"
                    )
                existing_scope_prescreen[key] = value
            return

        # Insert (if not added before)
        self.review_manager.settings.prescreen.prescreen_package_endpoints.insert(
            0, {**{"endpoint": "colrev.scope_prescreen"}, **params}
        )

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> dict:
        """Prescreen records based on the scope parameters"""

        repeat_input_question = True
        include_unranked_journals = False
        while repeat_input_question is True:
            print("Include Journals that are not included in any ranking?")
            choice = input("Y/N\n")
            if choice == "N":
                include_unranked_journals = True
                repeat_input_question = False
            if choice == "Y":
                break

        for record_dict in records.values():
            self.__conditional_prescreen(
                prescreen_operation=prescreen_operation,
                record_dict=record_dict,
                include_unranked_journals=include_unranked_journals,
            )

        prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()
        prescreen_operation.review_manager.create_commit(
            msg="Pre-screen (scope)",
            manual_author=False,
        )
        return records
