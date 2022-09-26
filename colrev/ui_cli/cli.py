#! /usr/bin/env python3
"""Command-line interface for CoLRev."""
import datetime
import logging
import os
from pathlib import Path

import click
import click_completion.core
import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.record
import colrev.review_manager
import colrev.ui_cli.cli_colors as colors
import colrev.ui_cli.cli_status_printer

# pylint: disable=too-many-lines
# pylint: disable=redefined-builtin
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument

# Note: autocompletion needs bash/... activation:
# https://click.palletsprojects.com/en/7.x/bashcomplete/


def __custom_startswith(string, incomplete):
    """A custom completion matching that supports case insensitive matching"""
    if os.environ.get("_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE"):
        string = string.lower()
        incomplete = incomplete.lower()
    return string.startswith(incomplete)


click_completion.core.startswith = __custom_startswith
click_completion.init()


class SpecialHelpOrder(click.Group):
    def __init__(self, *args, **kwargs):
        self.help_priorities = {}
        super().__init__(*args, **kwargs)

    def get_help(self, ctx):
        self.list_commands = self.list_commands_for_help
        return super().get_help(ctx)

    def list_commands_for_help(self, ctx):
        """reorder the list of commands when listing the help"""
        commands = super().list_commands(ctx)
        return (
            c[1]
            for c in sorted(
                (self.help_priorities.get(command, 1), command) for command in commands
            )
        )

    def command(self, *args, **kwargs):
        """Behaves the same as `click.Group.command()` except capture
        a priority for listing command names in help.
        """
        help_priority = kwargs.pop("help_priority", 1)
        help_priorities = self.help_priorities

        def decorator(fun):
            # pylint: disable=super-with-arguments
            cmd = super(SpecialHelpOrder, self).command(*args, **kwargs)(fun)
            help_priorities[cmd.name] = help_priority
            return cmd

        return decorator


def get_value(msg: str, options: list) -> str:
    valid_response = False
    user_input = ""
    while not valid_response:
        print(f" {msg} (" + "|".join(options) + ")")
        user_input = input()
        if user_input in options:
            valid_response = True
    return user_input


@click.group(cls=SpecialHelpOrder)
@click.pass_context
def main(ctx):
    """CoLRev

    Main commands: init | status | search, load, screen, ...

    Documentation:  https://github.com/geritwagner/colrev/docs
    """


@main.command(help_priority=1)
@click.option(
    "--type",
    type=str,
    help="Review type (e.g., literature_review (default), curated_masterdata, realtime)",
)
@click.option(
    "--example",
    is_flag=True,
    default=False,
    help="Add search results example",
)
@click.pass_context
def init(ctx, type, example):
    """Initialize repository"""
    # pylint: disable=import-outside-toplevel
    import colrev.ops.init
    import colrev.ui_web.settings_editor

    try:
        if type is None:
            # TODO : the type (if not passed as an argument) should
            # be selected as the first step of the web-ui
            type = "literature_review"

        colrev.review_manager.ReviewManager.get_init_operation(
            review_type=type,
            example=example,
        )

        review_manager = colrev.review_manager.ReviewManager()
        settings_operation = colrev.ui_web.settings_editor.SettingsEditor(
            review_manager=review_manager
        )
        settings_operation.open_settings_editor()

    except (
        colrev_exceptions.ParameterError,
        colrev_exceptions.NonEmptyDirectoryError,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=2)
@click.option(
    "-a",
    "--analytics",
    is_flag=True,
    default=False,
    help="Print analytics",
)
@click.pass_context
def status(ctx, analytics) -> None:
    """Show status"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        status_operation = review_manager.get_status_operation()

        if analytics:
            analytic_results = status_operation.get_analytics()
            for cid, data_item in reversed(analytic_results.items()):
                print(f"{cid} - {data_item}")
            return

        colrev.ui_cli.cli_status_printer.print_project_status(status_operation)

    except KeyboardInterrupt:
        print("Stopped...")
    except (
        colrev_exceptions.CoLRevUpgradeError,
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.RepoSetupError,
    ) as exc:
        logging.error(exc)
        return


@main.command(help_priority=3)
@click.option(
    "-a",
    "--add",
    type=str,
    help="""
Format: RETRIEVE * FROM crossref WHERE title LIKE '%keyword%'
""",
)
@click.option("-v", "--view", is_flag=True, default=False, help="View search sources")
@click.option(
    "-s",
    "--selected",
    type=str,
    help="Only retrieve search results for selected sources",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.option(
    "-f",
    "--force_mode",
    is_flag=True,
    default=False,
    help="Force mode: conduct full search again",
)
@click.pass_context
def search(ctx, add, view, selected, setup_custom_script, force_mode) -> None:
    """Retrieve search records"""

    try:
        review_manager = colrev.review_manager.ReviewManager(force_mode=force_mode)
        search_operation = review_manager.get_search_operation()

        if add:
            search_operation.add_source(query=add)
            return
        if view:
            search_operation.view_sources()
            return
        if setup_custom_script:
            search_operation.setup_custom_script()
            print("Activated custom_search_script.py.")
            print("Please update the source in settings.json and commit.")
            return

        search_operation.main(selection_str=selected)

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.NoSearchFeedRegistered,
        colrev_exceptions.ServiceNotAvailableException,
        colrev_exceptions.ParameterError,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=4)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.option(
    "-c",
    "--combine_commits",
    is_flag=True,
    default=False,
    help="Combine load of multiple sources in one commit.",
)
@click.pass_context
def load(ctx, keep_ids, combine_commits) -> None:
    """Import records"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        # already start LocalIndex (for set_ids)
        review_manager.get_local_index(startup_without_waiting=True)
        load_operation = review_manager.get_load_operation()

        load_operation.check_update_sources()

        if combine_commits:
            logging.info(
                "Combine mode: all search sources will be loaded in one commit"
            )

        # Note : reinitialize to load new scripts:
        load_operation = review_manager.get_load_operation()
        load_operation.main(keep_ids=keep_ids, combine_commits=combine_commits)

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.SearchSettingsError,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=5)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.option(
    "--reset_records",
    default="NA",
    type=str,
    help="Reset record metadata to the imported version. "
    "Format: --reset_records ID1,ID2,ID3",
)
@click.option(
    "-rid",
    "--reset_ids",
    is_flag=True,
    default=False,
    help="Reset IDs that have been changed (to fix the sort order in data/records.bib)",
)
@click.option(
    "-d",
    "--debug",
    type=str,
    help="Debug the preparation step for a selected record (can be 'all').",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom prep script.",
)
@click.option(
    "-df",
    "--debug_file",
    type=click.Path(exists=True),
    help="Debug the preparation step for a selected record (in a file).",
)
@click.option("-f", "--force", is_flag=True, default=False)
@click.pass_context
def prep(
    ctx,
    keep_ids,
    reset_records,
    reset_ids,
    debug,
    debug_file,
    setup_custom_script,
    force,
) -> None:
    """Prepare records"""

    # pylint: disable=import-outside-toplevel
    # TODO : catch inside prep:
    from sqlite3 import OperationalError

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, debug_mode=debug
        )
        prep_operation = review_manager.get_prep_operation()

        if reset_records != "NA":
            try:
                reset_records = str(reset_records)
            except ValueError:
                pass
            reset_records = reset_records.split(",")
            prep_operation.reset_records(reset_ids=reset_records)
            return
        if reset_ids:
            prep_operation.reset_ids()
            return
        if debug or debug_file:
            prep_operation.main(
                keep_ids=keep_ids, debug_ids=debug, debug_file=debug_file
            )
            return
        if setup_custom_script:
            prep_operation.setup_custom_script()
            print("Activated custom_prep_script.py.")
            print(
                "Please check and adapt its position in the settings.json and commit."
            )
            return

        prep_operation.main(keep_ids=keep_ids)

        print()
        print("Please check the changes (especially those with low_confidence)")
        print("To reset record(s) based on their ID, run")
        print("   colrev prep --reset_records ID1,ID2,...")
        print()

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.MissingDependencyError,
    ) as exc:
        logging.error(exc)
        return
    except colrev_exceptions.ServiceNotAvailableException as exc:
        logging.error(exc)
        print("You can use the force mode to override")
        print("  colrev prep -f")
    except OperationalError as exc:
        logging.error(
            "SQLite Error: %s. "
            "Another colrev process is accessing a shared resource. "
            "Please try again later.",
            exc,
        )


def view_dedupe_details(dedupe_operation) -> None:

    info = dedupe_operation.get_info()

    if len(info["same_source_merges"]) > 0:
        print(f"\n\n{colors.RED}Same source merges to check:{colors.END}")
        print("\n- " + "\n- ".join(info["same_source_merges"]))


@main.command(help_priority=6)
@click.option(
    "-f",
    "--fix_errors",
    is_flag=True,
    default=False,
    help="Fix errors marked in duplicates_to_validate.xlsx "
    "or non_duplicates_to_validate.xlsx or "
    "a dupes.txt file containing comma-separated ID tuples",
)
@click.option("-v", "--view", is_flag=True, default=False, help="View dedupe info")
@click.option(
    "--source_comparison",
    is_flag=True,
    default=False,
    help="Export a spreadsheet for (non-matched) source comparison",
)
@click.option("--force", is_flag=True, default=False)
@click.pass_context
def dedupe(
    ctx,
    fix_errors,
    view,
    source_comparison,
    force,
) -> None:
    """Deduplicate records"""

    try:
        review_manager = colrev.review_manager.ReviewManager(force_mode=force)
        state_transition_process = not view
        dedupe_operation = review_manager.get_dedupe_operation(
            notify_state_transition_operation=state_transition_process
        )

        if fix_errors:
            dedupe_operation.fix_errors()
            print(
                "You can manually remove the duplicates_to_validate.xlsx, "
                "non_duplicates_to_validate.xlsx, and dupes.txt files."
            )
            return

        if view:
            view_dedupe_details(dedupe_operation)
            return

        if source_comparison:
            dedupe_operation.source_comparison()
            return

        # TODO : move to active learning init:
        logging.basicConfig()
        logging.getLogger("dedupe.canopy_index").setLevel(logging.WARNING)

        dedupe_operation.main()

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
        colrev_exceptions.DedupeError,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=7)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print statistics of records with colrev_status md_needs_manual_preparation",
)
@click.pass_context
def prep_man(ctx, stats) -> None:
    """Manual preparation of records (not yet fully implemented)"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        prep_man_operation = review_manager.get_prep_man_operation()

        if stats:
            prep_man_operation.prep_man_stats()
            return

        prep_man_operation.main()

    except colrev_exceptions.InvalidSettingsError as exc:
        logging.error(exc)


@main.command(help_priority=9)
@click.option(
    "--include_all",
    is_flag=True,
    default=False,
    help="Include all records in prescreen",
)
@click.option(
    "--export_format",
    type=click.Choice(["CSV", "XLSX"], case_sensitive=False),
    help="Export table with the screening decisions",
)
@click.option(
    "--import_table",
    type=click.Path(exists=True),
    help="Import file with the screening decisions (csv supported)",
)
@click.option(
    "--create_split",
    type=int,
    help="Split the prescreen between n researchers "
    + "(same size, non-overlapping samples)",
)
@click.option(
    "--split",
    type=str,
    default="",
    help="Prescreen a split sample",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def prescreen(
    ctx,
    include_all,
    export_format,
    import_table,
    create_split,
    split,
    setup_custom_script,
) -> None:
    """Pre-screen based on titles and abstracts"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        prescreen_operation = review_manager.get_prescreen_operation()

        if export_format:
            prescreen_operation.export_table(export_table_format=export_format)
            return
        if import_table:
            prescreen_operation.import_table(import_table_path=import_table)
            return
        if include_all:
            prescreen_operation.include_all_in_prescreen()
            return
        if create_split:
            splits = prescreen_operation.create_prescreen_split(
                create_split=create_split
            )
            for created_split in splits:
                print(created_split + "\n")
            return
        if setup_custom_script:
            prescreen_operation.setup_custom_script()
            print("Activated custom_prescreen_script.py.")
            return

        prescreen_operation.main(split_str=split)

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
        colrev_exceptions.CleanRepoRequiredError,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=10)
@click.option(
    "--include_all",
    is_flag=True,
    default=False,
    help="Include all records in the screen",
)
@click.option(
    "-ac",
    "--add_criterion",
    type=str,
    help="Add a screening criterion. "
    "Format: -ac 'criterion_name,criterion explanation'",
)
@click.option(
    "-dc",
    "--delete_criterion",
    type=str,
    help="Delete a screening criterion. Format: -dc 'criterion_name'",
)
@click.option(
    "--create_split",
    type=int,
    help="Split the prescreen between n researchers "
    + "(same size, non-overlapping samples)",
)
@click.option(
    "--split",
    type=str,
    default="",
    help="Prescreen a split sample",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def screen(
    ctx,
    include_all,
    add_criterion,
    delete_criterion,
    create_split,
    split,
    setup_custom_script,
) -> None:
    """Screen based on exclusion criteria and fulltext documents"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        screen_operation = review_manager.get_screen_operation()

        if include_all:
            screen_operation.include_all_in_screen()
            return
        if add_criterion:
            screen_operation.add_criterion(criterion_to_add=add_criterion)
            return
        if delete_criterion:
            screen_operation.delete_criterion(criterion_to_delete=delete_criterion)
            return
        if create_split:
            splits = screen_operation.create_screen_split(create_split=create_split)
            for created_split in splits:
                print(created_split + "\n")
            return
        if setup_custom_script:
            screen_operation.setup_custom_script()
            print("Activated custom_screen_script.py.")
            return

        screen_operation.main(split_str=split)

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=11)
@click.option(
    "-c",
    "--copy-to-repo",
    is_flag=True,
    default=False,
    help="Copy PDF files to the repository (the /pdfs directory)",
)
@click.option(
    "-r",
    "--rename",
    is_flag=True,
    default=False,
    help="Rename the PDF files according to record IDs",
)
@click.option(
    "--relink_files",
    is_flag=True,
    default=False,
    help="Recreate links to PDFs based on colrev pdf-IDs (when PDFs were renamed)",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def pdf_get(ctx, copy_to_repo, rename, relink_files, setup_custom_script) -> None:
    """Retrieve PDFs to the default pdf directory (/pdfs)"""

    try:
        review_manager = colrev.review_manager.ReviewManager()

        state_transition_operation = not relink_files and not setup_custom_script
        pdf_get_operation = review_manager.get_pdf_get_operation(
            notify_state_transition_operation=state_transition_operation
        )

        if relink_files:
            pdf_get_operation.relink_files()
            return
        if copy_to_repo:
            pdf_get_operation.copy_pdfs_to_repo()
            return
        if rename:
            pdf_get_operation.rename_pdfs()
            return
        if setup_custom_script:
            pdf_get_operation.setup_custom_script()
            print("Activated custom_pdf_get_script.py.")
            return

        pdf_get_operation.main()

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=12)
@click.option(
    "--update_colrev_pdf_ids", is_flag=True, default=False, help="Update colrev_pdf_ids"
)
@click.option(
    "--reprocess",
    is_flag=True,
    default=False,
    help="Prepare all PDFs again (pdf_needs_manual_preparation).",
)
@click.option(
    "--debug",
    "-d",
    is_flag=True,
    default=False,
    help="Debug",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def pdf_prep(ctx, update_colrev_pdf_ids, reprocess, debug, setup_custom_script) -> None:
    """Prepare PDFs"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        pdf_prep_operation = review_manager.get_pdf_prep_operation(
            reprocess=reprocess, debug=debug
        )

        if update_colrev_pdf_ids:
            pdf_prep_operation.update_colrev_pdf_ids()
            return
        if setup_custom_script:
            pdf_prep_operation.setup_custom_script()
            print("Activated custom_pdf_prep_script.py.")
            return

        pdf_prep_operation.main()

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=13)
@click.pass_context
@click.option(
    "-e",
    "--export",
    is_flag=True,
    default=False,
    help="Export spreadsheet.",
)
def pdf_get_man(ctx, export) -> None:
    """Get PDFs manually"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        pdf_get_man_operation = review_manager.get_pdf_get_man_operation()

        if export:
            records = pdf_get_man_operation.review_manager.dataset.load_records_dict()
            pdf_get_man_records = [
                r
                for r in records.values()
                if r["colrev_status"]
                in [
                    colrev.record.RecordState.pdf_needs_manual_retrieval,
                    colrev.record.RecordState.rev_prescreen_included,
                ]
            ]
            pdf_get_man_records_df = pd.DataFrame.from_records(pdf_get_man_records)
            pdf_get_man_records_df = pdf_get_man_records_df[
                pdf_get_man_records_df.columns.intersection(
                    {
                        "ID",
                        "author",
                        "year",
                        "title",
                        "journal",
                        "booktitle",
                        "volume",
                        "number",
                        "url",
                        "doi",
                    }
                )
            ]
            pdf_get_man_records_df.to_csv("pdf_get_man_records.csv", index=False)
            pdf_get_man_operation.review_manager.logger.info(
                "Created pdf_get_man_records.csv"
            )
            return

        pdf_get_man_operation.main()

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
    ) as exc:
        logging.error(exc)


def delete_first_pages_cli(pdf_get_man_operation, record_id) -> None:

    records = pdf_get_man_operation.review_manager.dataset.load_records_dict()
    while True:
        if record_id in records:
            record = records[record_id]
            if "file" in record:
                print(record["file"])
                pdf_path = pdf_get_man_operation.review_manager.path / Path(
                    record["file"]
                )
                pdf_get_man_operation.extract_coverpage(pdf_path)
            else:
                print("no file in record")
        if "n" == input("Extract coverpage from another PDF? (y/n)"):
            break
        record_id = input("ID of next PDF for coverpage extraction:")


@main.command(help_priority=14)
@click.option(
    "-dfp",
    "--delete_first_page",
    type=str,
    help="Delete first page of PDF. Format: --delete_first_page ID",
)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print statistics of records with colrev_status pdf_needs_manual_preparation",
)
@click.option(
    "--extract",
    is_flag=True,
    default=False,
    help="Extract records for manual_preparation (to csv and bib)",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Apply manual preparation (from csv or bib)",
)
@click.pass_context
def pdf_prep_man(ctx, delete_first_page, stats, extract, apply) -> None:
    """Prepare PDFs manually"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()

        if delete_first_page:
            delete_first_pages_cli(pdf_prep_man_operation, delete_first_page)
            return
        if stats:
            pdf_prep_man_operation.pdf_prep_man_stats()
            return
        if extract:
            pdf_prep_man_operation.extract_needs_pdf_prep_man()
            return
        if apply:
            pdf_prep_man_operation.apply_pdf_prep_man()
            return

        pdf_prep_man_operation.main()

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
    ) as exc:
        logging.error(exc)


@main.command(help_priority=15)
@click.option(
    "--profile",
    is_flag=True,
    default=False,
    help="Create a sample profile (papers per journal and year)",
)
@click.option(
    "--reading_heuristics",
    is_flag=True,
    default=False,
    help="Heuristics to prioritize reading efforts",
)
@click.option(
    "-a",
    "--add_endpoint",
    type=str,
    help="Add a data_format endpoint (e.g., MANUSCRIPT,STRUCTURED)",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Option to override process preconditions",
)
@click.pass_context
def data(
    ctx, profile, reading_heuristics, add_endpoint, setup_custom_script, force
) -> None:
    """Extract data"""

    # pylint: disable=import-outside-toplevel
    import colrev.ui_cli.add_packages

    try:
        review_manager = colrev.review_manager.ReviewManager(force_mode=force)
        data_operation = review_manager.get_data_operation()

        if profile:
            data_operation.profile()
            return
        if reading_heuristics:
            heuristic_results = data_operation.reading_heuristics()
            review_manager.p_printer.pprint(heuristic_results)
            return
        if setup_custom_script:
            data_operation.setup_custom_script()
            print("Activated custom_data_script.py.")
            print("Please update the data_format in settings.json and commit.")
            return

        if add_endpoint:

            colrev.ui_cli.add_packages.add_data(
                data_operation=data_operation,
                review_manager=review_manager,
                add_endpoint=add_endpoint,
                force=force,
            )

            return

        ret = data_operation.main()
        if ret["ask_to_commit"]:
            if "y" == input("Create commit (y/n)?"):
                review_manager.create_commit(
                    msg="Data and synthesis", manual_author=True
                )
        if ret["no_endpoints_registered"]:
            print(
                "No data format not specified. "
                "To register a data endpoint, "
                "use one (or several) of the following \n"
                "    colrev data --add_endpoint MANUSCRIPT\n"
                "    colrev data --add_endpoint STRUCTURED\n"
                "    colrev data --add_endpoint PRISMA\n"
                "    colrev data --add_endpoint ZETTLR\n"
                "    colrev data --add_endpoint ENDNOTE"
            )

    except (
        colrev_exceptions.InvalidSettingsError,
        colrev_exceptions.ProcessOrderViolation,
    ) as exc:
        logging.error(exc)


def validate_commit(ctx, param, value):
    if value is None:
        return value

    # pylint: disable=import-outside-toplevel
    import git

    repo = git.Repo()
    rev_list = list(repo.iter_commits())

    if value in [x.hexsha for x in rev_list]:
        return value

    print("Error: Invalid value for '--commit': not a git commit id\n")
    print("Select any of the following commit ids:\n")
    print("commit-id".ljust(41, " ") + "date".ljust(24, " ") + "commit message")
    commits_for_checking = []
    for commit in reversed(list(rev_list)):
        commits_for_checking.append(commit)
    for commit in rev_list:
        print(
            commit.hexsha,
            datetime.datetime.fromtimestamp(commit.committed_date),
            " - ",
            commit.message.split("\n")[0],
        )
    print("\n")
    raise click.BadParameter("not a git commit id")


@main.command(help_priority=16)
@click.option(
    "--scope",
    type=click.Choice(["prepare", "merge", "all", "unspecified"], case_sensitive=False),
    default="unspecified",
    help="prepare, merge, or all.",
)
@click.option(
    "--properties", is_flag=True, default=False, help="Git commit id to validate."
)
@click.option(
    "--commit",
    help="Git commit id to validate.",
    default=None,
    callback=validate_commit,
)
@click.option(
    "-t",
    "--tree_hash",
    help="Git tree hash to validate.",
    default=None,
)
@click.pass_context
def validate(ctx, scope, properties, commit, tree_hash) -> None:
    """Validate changes"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        validate_operation = review_manager.get_validate_operation()

        if tree_hash:
            assert not commit
            commit = validate_operation.get_commit_from_tree_hash(tree_hash=tree_hash)
            input(commit)

        validation_details = validate_operation.main(
            scope=scope, properties=properties, target_commit=commit
        )

        if 0 == len(validation_details):
            print("No substantial changes.")
            return

        # pylint: disable=duplicate-code
        keys = [
            "author",
            "title",
            "journal",
            "booktitle",
            "year",
            "volume",
            "number",
            "pages",
        ]

        for record_a, record_b, difference in validation_details:
            # Escape sequence to clear terminal output for each new comparison
            os.system("cls" if os.name == "nt" else "clear")
            if record_a["ID"] == record_b["ID"]:
                print(
                    f"similarity: {str(round(difference, 4))} record {record_a['ID']}"
                )
            else:
                print(
                    f"similarity: {str(round(difference, 4))} "
                    f"record {record_a['ID']} - {record_b['ID']}"
                )

            colrev.record.Record.print_diff_pair(
                record_pair=[record_a, record_b], keys=keys
            )

            user_selection = input("Validate [y,n,d,q]?")

            if "q" == user_selection:
                break
            if "y" == user_selection:
                continue

            # TODO: correct? if not, replace current record with old one

    except colrev_exceptions.InvalidSettingsError as exc:
        logging.error(exc)
        return


@main.command(help_priority=17)
@click.pass_context
@click.option(
    "--id",  # pylint: disable=invalid-name
    help="Record ID to trace (citation_key).",
    required=True,
)
def trace(ctx, id) -> None:  # pylint: disable=invalid-name
    """Trace a record"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        trace_operation = review_manager.get_trace_operation()
        trace_operation.main(record_id=id)

    except colrev_exceptions.InvalidSettingsError as exc:
        logging.error(exc)
        return


def __select_target_repository(local_registry: list) -> Path:
    while True:
        for i, local_source in enumerate(local_registry):
            print(
                f"{i+1} - {local_source['repo_name']} ({local_source['repo_source_path']})"
            )
        sel_str = input("Select target repository: ")
        sel = int(sel_str) - 1
        if sel in range(0, len(local_registry)):
            target = Path(local_registry[sel]["repo_source_path"])
            return target


@main.command(help_priority=18)
@click.option(
    "-p",
    "--path",
    type=click.Path(exists=True),
    help="Path to file(s)",
)
@click.pass_context
def distribute(ctx, path) -> None:
    """Distribute records to other local CoLRev repositories"""

    try:
        review_manager = colrev.review_manager.ReviewManager(force_mode=True)
        distribute_operation = review_manager.get_distribute_operation()
        local_registry = distribute_operation.get_local_registry()

        target = __select_target_repository(local_registry=local_registry)

        # Note : add a "distribution mode" option?
        # (whole file -> add as source/load vs. records individually like a prescreen)
        distribute_operation.main(path_str=path, target=target)

    except colrev_exceptions.InvalidSettingsError as exc:
        logging.error(exc)
        return


def print_environment_status(review_manager) -> None:

    environment_manager = review_manager.get_environment_manager()
    environment_details = environment_manager.get_environment_details(
        review_manager=review_manager
    )

    print("\nCoLRev environment status\n")
    print("Index\n")
    if "up" == environment_details["index"]["status"]:
        print(f" - Status: {colors.GREEN}up{colors.END}")
        print(f' - Path          : {environment_details["index"]["path"]}')
        print(f' - Size          : {environment_details["index"]["size"]} records')
        print(f' - Last modified : {environment_details["index"]["last_modified"]}')
    else:
        print(f" - Status: {colors.RED}down{colors.END}")

    print("\nCoLRev projects\n")
    project_repos = [
        x
        for x in environment_details["local_repos"]["repos"]
        if "curated_metadata" not in x["source_url"]
    ]
    for colrev_repo in sorted(project_repos, key=lambda d: d["source_name"]):

        repo_stats = f' {colrev_repo["source_name"]}'
        if colrev_repo["remote"]:
            if colrev_repo["behind_remote"]:
                repo_stats += " (shared, behind remote)"
            else:
                repo_stats += " (shared)"
        print(repo_stats)

        if -1 != colrev_repo["progress"]:
            print(f'    - Progress : {colrev_repo["progress"]*100} %')
        else:
            print("    - Progress : ??")
        print(f'    - Size     : {colrev_repo["size"]} records')
        print(f'    - Path     : {colrev_repo["source_url"]}')

    print("\nCurated CoLRev resources\n")
    curated_repos = [
        x
        for x in environment_details["local_repos"]["repos"]
        if "curated_metadata" in x["source_url"]
    ]
    for colrev_repo in sorted(curated_repos, key=lambda d: d["source_name"]):
        repo_stats = (
            f' - {colrev_repo["source_name"].ljust(60, " ")}: '
            f'{str(colrev_repo["size"]).rjust(10, " ")} records'
        )
        if colrev_repo["behind_remote"]:
            repo_stats += " (behind remote)"
        print(repo_stats)

    print("\n")
    if len(environment_details["local_repos"]["broken_links"]) > 0:
        print("Broken links: \n")
        for broken_link in environment_details["local_repos"]["broken_links"]:
            print(f'- {broken_link["source_url"]}')


@main.command(help_priority=19)
@click.option(
    "-i", "--index", is_flag=True, default=False, help="Create the LocalIndex"
)
@click.option(
    "--install",
    help="Install a new resource providing its url "
    + "(e.g., a curated metadata repository)",
)
@click.option(
    "-a",
    "--analyze",
    is_flag=True,
    default=False,
    help="Analyze the LocalIndex for potential problems",
)
@click.option("--pull", is_flag=True, default=False, help="Pull curated metadata")
@click.option(
    "-s", "--status", is_flag=True, default=False, help="Print environment status"
)
@click.option("--start", is_flag=True, default=False, help="Start environment services")
@click.option("--stop", is_flag=True, default=False, help="Stop environment services")
@click.option(
    "--search",
    is_flag=True,
    default=False,
    help="Start opensearch dashboard service to search the LocalIndex",
)
@click.option(
    "-r",
    "--register",
    is_flag=True,
    default=False,
    help="Register a repository in the CoLRev environment",
)
@click.option(
    "-ur",
    "--unregister",
    type=click.Path(exists=True),
    help="Path of repository to remove from local registry.",
)
@click.pass_context
def env(
    ctx,
    index,
    install,
    analyze,
    pull,
    status,
    start,
    stop,
    search,
    register,
    unregister,
):
    """CoLRev environment commands"""

    # pylint: disable=import-outside-toplevel
    # pylint: disable=too-many-return-statements
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals

    import webbrowser
    import docker

    review_manager = colrev.review_manager.ReviewManager()

    if install:
        env_resources = review_manager.get_resources()
        if env_resources.install_curated_resource(curated_resource=install):
            print("Successfully installed curated resource.")
            print("To make it available to other projects, run")
            print("colrev env --index")
        return

    if pull:
        environment_manager = review_manager.get_environment_manager()
        for curated_resource in environment_manager.load_local_registry():
            curated_resource_path = curated_resource["source_url"]
            if "/curated_metadata/" not in curated_resource_path:
                continue
            review_manager = colrev.review_manager.ReviewManager(
                path_str=curated_resource_path
            )
            review_manager.dataset.pull_if_repo_clean()
            print(f"Pulled {curated_resource_path}")
        return

    if status:
        print_environment_status(review_manager)
        return

    if stop:
        client = docker.from_env()
        environment_manager = review_manager.get_environment_manager()

        images_to_stop = [k for k, v in environment_manager.docker_images.items()]
        for container in client.containers.list():
            if any(x in str(container.image) for x in images_to_stop):
                container.stop()
                print(f"Stopped container {container.name} ({container.image})")
        return

    if register:
        environment_manager = review_manager.get_environment_manager()
        environment_manager.register_repo(path_to_register=Path.cwd())
        return

    if unregister is not None:
        environment_manager = review_manager.get_environment_manager()

        local_registry = environment_manager.load_local_registry()
        if str(unregister) not in [x["source_url"] for x in local_registry]:
            logging.error("Not in local registry (cannot remove): %s", unregister)
        else:
            local_registry = [
                x for x in local_registry if x["source_url"] != str(unregister)
            ]
            environment_manager.save_local_registry(updated_registry=local_registry)
            logging.info("Removed from local registry: %s", unregister)
        return

    local_index = review_manager.get_local_index()
    if search:
        local_index.start_opensearch_docker_dashboards()
        print("Started.")
        webbrowser.open("http://localhost:5601/app/home#/", new=2)

    elif index:
        local_index.index()

    elif start:
        print("Started.")

    elif analyze:
        local_index.analyze()


@main.command(help_priority=20)
# @click.option("-v", "--view", is_flag=True, default=False)
@click.option(
    "-u",
    "--upgrade",
    is_flag=True,
    default=False,
    help="Update to the latest CoLRev project version",
)
@click.option(
    "-uh",
    "--update_hooks",
    is_flag=True,
    default=False,
    help="Update the pre-commit hooks",
)
@click.option(
    "-m",
    "--modify",
    type=str,
    default="",
    help="Modify the settings through the command line",
)
@click.pass_context
def settings(ctx, upgrade, update_hooks, modify):
    """Settings of the CoLRev project"""

    # pylint: disable=import-outside-toplevel
    # pylint: disable=reimported
    # pylint: disable=too-many-locals

    from subprocess import check_call
    from subprocess import DEVNULL
    from subprocess import STDOUT
    import json
    import ast
    import glom
    import colrev.review_manager

    if upgrade:
        review_manager = colrev.review_manager.ReviewManager(force_mode=True)
        upgrad_operation = review_manager.get_upgrade()
        upgrad_operation.main()
        return

    review_manager = colrev.review_manager.ReviewManager()
    if update_hooks:

        print("Update pre-commit hooks")

        if review_manager.dataset.has_changes():
            print("Clean repo required. Commit or stash changes.")
            return

        scripts_to_call = [
            [
                "pre-commit",
                "autoupdate",
                "--repo",
                "https://github.com/geritwagner/colrev-hooks",
            ],
        ]
        for script_to_call in scripts_to_call:
            check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)

        review_manager.dataset.add_changes(path=".pre-commit-config.yaml")
        review_manager.create_commit(
            msg="Update pre-commit hooks", script_call="colrev settings --update"
        )
        print("Successfully updated pre-commit hooks")
        return

    if modify:

        # TBD: maybe use glom.delete?
        # There is no simply append...
        # (we could replace the (last) position element with
        # keywords like prescreen.sripts.LAST_POSITION)
        # maybe prescreen.scripts.1.REPLACE/ADD/DELETE = ....
        # modify = 'dedupe.scripts=[{"endpoint":"simple_dedupe"}]'

        path, value_string = modify.split("=")
        value = ast.literal_eval(value_string)
        review_manager.logger.info("Change settings.%s to %s", path, value)

        with open("settings.json", encoding="utf-8") as file:
            project_settings = json.load(file)

        glom.assign(project_settings, path, value)

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(project_settings, outfile, indent=4)

        review_manager.dataset.add_changes(path="settings.json")
        review_manager.create_commit(
            msg="Change settings", manual_author=True, saved_args=None
        )
        return

    import colrev.ui_web.settings_editor

    review_manager = colrev.review_manager.ReviewManager(force_mode=True)
    settings_operation = colrev.ui_web.settings_editor.SettingsEditor(
        review_manager=review_manager
    )
    settings_operation.open_settings_editor()


@main.command(help_priority=21)
@click.pass_context
def sync(ctx):
    """Sync records from CoLRev environment to non-CoLRev repo"""

    sync_operation = colrev.review_manager.ReviewManager.get_sync_operation()
    sync_operation.get_cited_papers()

    if len(sync_operation.non_unique_for_import) > 0:
        print("Non-unique keys to resolve:")
        # Resolve non-unique cases
        for case in sync_operation.non_unique_for_import:
            for val in case.values():
                # TODO: there may be more collisions (v3, v4)
                v_1 = sync_operation.format_ref(reference=val[0])
                v_2 = sync_operation.format_ref(reference=val[1])
                if v_1.lower() == v_2.lower():
                    sync_operation.add_to_records_to_import(record=val[0])
                    continue
                print("\n")
                print(f"1: {v_1}")
                print("      " + val[0].get("source_url", ""))
                print("")
                print(f"2: {v_2}")
                print("      " + val[1].get("source_url", ""))
                user_selection = input("Import version 1 or 2 (or skip)?")
                if "1" == user_selection:
                    sync_operation.add_to_records_to_import(record=val[0])
                    continue
                if "2" == user_selection:
                    sync_operation.add_to_records_to_import(record=val[1])
                    continue

    sync_operation.add_to_bib()


@main.command(help_priority=22)
@click.option(
    "-r",
    "--records_only",
    is_flag=True,
    default=False,
    help="Update records only",
)
@click.option(
    "-p",
    "--project_only",
    is_flag=True,
    default=False,
    help="Push project only",
)
@click.pass_context
def pull(ctx, records_only, project_only):
    """Pull CoLRev project remote and record updates"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        pull_operation = review_manager.get_pull_operation()

        pull_operation.main(records_only=records_only, project_only=project_only)

    except colrev_exceptions.InvalidSettingsError as exc:
        logging.error(exc)


@main.command(help_priority=23)
@click.argument("git_url")
@click.pass_context
def clone(ctx, git_url):
    """Create local clone from shared CoLRev repository with git_url"""

    clone_operation = colrev.review_manager.ReviewManager.get_clone_operation(
        git_url=git_url
    )
    clone_operation.clone_git_repo()


@main.command(help_priority=24)
@click.option(
    "-r",
    "--records_only",
    is_flag=True,
    default=False,
    help="Update records only",
)
@click.option(
    "-p",
    "--project_only",
    is_flag=True,
    default=False,
    help="Push project only",
)
@click.pass_context
def push(ctx, records_only, project_only):
    """Push CoLRev project remote and record updates"""

    try:
        review_manager = colrev.review_manager.ReviewManager()
        push_operation = review_manager.get_push_operation()

        push_operation.main(records_only=records_only, project_only=project_only)

    except colrev_exceptions.InvalidSettingsError as exc:
        logging.error(exc)


@main.command(help_priority=25)
@click.pass_context
def service(ctx):
    """Service for real-time reviews"""

    try:

        review_manager = colrev.review_manager.ReviewManager()
        review_manager.get_service_operation()

    except KeyboardInterrupt:
        print("\nPressed ctrl-c. Shutting down service")

    if review_manager.dataset.has_changes():
        if "y" == input("Commit current changes (y/n)?"):
            review_manager.create_commit(
                msg="Update (work on realtime review)", realtime_override=True
            )
    else:
        print("No changes to commit")


def validate_show(ctx, param, value):
    if value not in ["sample", "settings", "prisma", "venv"]:
        raise click.BadParameter("Invalid argument")


@main.command(help_priority=26)
@click.argument("keyword")
@click.pass_context
def show(ctx, keyword, callback=validate_show):
    """Show aspects (sample, ...)"""

    # pylint: disable=import-outside-toplevel
    import colrev.process
    import colrev.ui_cli.show_printer

    review_manager = colrev.review_manager.ReviewManager()

    if "sample" == keyword:
        colrev.ui_cli.show_printer.print_sample(review_manager=review_manager)

    elif "settings" == keyword:
        print(f"Settings:\n{review_manager.settings}")

    elif "prisma" == keyword:
        status_operation = review_manager.get_status_operation()
        stats_report = status_operation.get_review_status_report(colors=colors)
        print(stats_report)

    elif "venv" == keyword:
        colrev.ui_cli.show_printer.print_venv_notes()


@main.command(help_priority=27)
@click.pass_context
def web(ctx):
    """CoLRev web interface."""

    # pylint: disable=import-outside-toplevel
    import colrev.ui_web.settings_editor

    review_manager = colrev.review_manager.ReviewManager()
    se_instance = colrev.ui_web.settings_editor.SettingsEditor(
        review_manager=review_manager
    )
    se_instance.open_settings_editor()


@main.command(hidden=True)
@click.option(
    "-i", "--case-insensitive/--no-case-insensitive", help="Case insensitive completion"
)
@click.argument(
    "shell",
    required=False,
    type=click_completion.DocumentedChoice(click_completion.core.shells),
)
def show_click(shell, case_insensitive):
    """Show the click-completion-command completion code"""
    extra_env = (
        {"_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE": "ON"}
        if case_insensitive
        else {}
    )
    click.echo(click_completion.core.get_code(shell, extra_env=extra_env))


@main.command(hidden=True)
@click.option(
    "--append/--overwrite", help="Append the completion code to the file", default=None
)
@click.option(
    "-i", "--case-insensitive/--no-case-insensitive", help="Case insensitive completion"
)
@click.argument(
    "shell",
    required=False,
    type=click_completion.DocumentedChoice(click_completion.core.shells),
)
@click.argument("path", required=False)
def install_click(append, case_insensitive, shell, path):
    """Install the click-completion-command completion"""
    extra_env = (
        {"_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE": "ON"}
        if case_insensitive
        else {}
    )
    shell, path = click_completion.core.install(
        shell=shell, path=path, append=append, extra_env=extra_env
    )
    click.echo(f"{shell} completion installed in {path}")
