#! /usr/bin/env python
"""Checkers for CoLRev repositories"""
from __future__ import annotations

import sys
import typing
from importlib.metadata import version
from pathlib import Path
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT
from typing import TYPE_CHECKING

import git
import yaml
from git.exc import GitCommandError
from git.exc import InvalidGitRepositoryError

import colrev.exceptions as colrev_exceptions
import colrev.process

if TYPE_CHECKING:
    import colrev.review_manager


PASS, FAIL = 0, 1


class Checker:
    __COLREV_HOOKS_URL = "https://github.com/geritwagner/colrev-hooks"

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:

        self.review_manager = review_manager

    def get_colrev_versions(self) -> list[str]:
        current_colrev_version = version("colrev")
        last_colrev_version = current_colrev_version
        last_commit_message = self.review_manager.dataset.get_commit_message(
            commit_nr=0
        )
        cmsg_lines = last_commit_message.split("\n")
        for cmsg_line in cmsg_lines[0:100]:
            if "colrev:" in cmsg_line and "version" in cmsg_line:
                last_colrev_version = cmsg_line[cmsg_line.find("version ") + 8 :]
        return [last_colrev_version, current_colrev_version]

    def __check_software(self) -> None:
        last_version, current_version = self.get_colrev_versions()
        if last_version != current_version:
            raise colrev_exceptions.CoLRevUpgradeError(last_version, current_version)
        if not sys.version_info > (2, 7):
            raise colrev_exceptions.CoLRevException("CoLRev does not support Python 2.")
        if sys.version_info < (3, 5):
            self.review_manager.logger.warning(
                "CoLRev uses Python 3.8 features (currently, %s is installed). Please upgrade.",
                sys.version_info,
            )

    def __lsremote(self, *, url: str) -> dict:
        remote_refs = {}
        git_repo = git.cmd.Git()
        for ref in git_repo.ls_remote(url).split("\n"):
            hash_ref_list = ref.split("\t")
            remote_refs[hash_ref_list[1]] = hash_ref_list[0]
        return remote_refs

    def __colrev_hook_up_to_date(self) -> bool:

        with open(".pre-commit-config.yaml", encoding="utf8") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)

        local_hooks_version = ""
        for repository in pre_commit_config["repos"]:
            if repository["repo"] == self.__COLREV_HOOKS_URL:
                local_hooks_version = repository["rev"]

        refs = self.__lsremote(url=self.__COLREV_HOOKS_URL)
        remote_sha = refs["HEAD"]
        if remote_sha == local_hooks_version:
            return True
        return False

    def __update_colrev_hooks(self) -> None:
        if self.__COLREV_HOOKS_URL not in self.__get_installed_repos():
            return
        try:
            if not self.__colrev_hook_up_to_date():
                self.review_manager.logger.info("Updating pre-commit hooks")
                check_call(["pre-commit", "autoupdate"], stdout=DEVNULL, stderr=STDOUT)
                self.review_manager.dataset.add_changes(
                    path=Path(".pre-commit-config.yaml")
                )
        except GitCommandError:
            self.review_manager.logger.warning(
                "No Internet connection, cannot check remote "
                "colrev-hooks repository for updates."
            )
        return

    def check_repository_setup(self) -> None:

        # 1. git repository?
        if not self.__is_git_repo():
            raise colrev_exceptions.RepoSetupError("no git repository. Use colrev init")

        # 2. colrev project?
        if not self.__is_colrev_project():
            raise colrev_exceptions.RepoSetupError(
                "No colrev repository."
                + "To retrieve a shared repository, use colrev init."
                + "To initalize a new repository, "
                + "execute the command in an empty directory."
            )

        # 3. Pre-commit hooks installed?
        self.__require_colrev_hooks_installed()

        # 4. Pre-commit hooks up-to-date?
        self.__update_colrev_hooks()

    def in_virtualenv(self) -> bool:
        def get_base_prefix_compat() -> str:
            return (
                getattr(sys, "base_prefix", None)
                or getattr(sys, "real_prefix", None)
                or sys.prefix
            )

        return get_base_prefix_compat() != sys.prefix

    def __check_git_conflicts(self) -> None:
        # Note: when check is called directly from the command line.
        # pre-commit hooks automatically notify on merge conflicts

        git_repo = self.review_manager.dataset.get_repo()
        unmerged_blobs = git_repo.index.unmerged_blobs()

        for path, list_of_blobs in unmerged_blobs.items():
            for (stage, _) in list_of_blobs:
                if stage != 0:
                    raise colrev_exceptions.GitConflictError(path)

    def __is_git_repo(self) -> bool:
        try:
            _ = self.review_manager.dataset.get_repo().git_dir
            return True
        except InvalidGitRepositoryError:
            return False

    def __is_colrev_project(self) -> bool:
        required_paths = [
            Path(".pre-commit-config.yaml"),
            Path(".gitignore"),
            Path("settings.json"),
        ]
        if not all((self.review_manager.path / x).is_file() for x in required_paths):
            return False
        return True

    def __get_installed_hooks(self) -> list:
        installed_hooks = []
        with open(".pre-commit-config.yaml", encoding="utf8") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
        for repository in pre_commit_config["repos"]:
            installed_hooks.extend([hook["id"] for hook in repository["hooks"]])
        return installed_hooks

    def __get_installed_repos(self) -> list:
        installed_repos = []
        with open(".pre-commit-config.yaml", encoding="utf8") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
        for repository in pre_commit_config["repos"]:
            installed_repos.append(repository["repo"])
        return installed_repos

    def __require_colrev_hooks_installed(self) -> bool:
        required_hooks = [
            "colrev-hooks-check",
            "colrev-hooks-format",
            "colrev-hooks-report",
            "colrev-hooks-share",
        ]
        installed_hooks = self.__get_installed_hooks()
        hooks_activated = set(required_hooks).issubset(set(installed_hooks))
        if not hooks_activated:
            missing_hooks = [x for x in required_hooks if x not in installed_hooks]
            raise colrev_exceptions.RepoSetupError(
                f"missing hooks in .pre-commit-config.yaml ({', '.join(missing_hooks)})"
            )

        pch_file = Path(".git/hooks/pre-commit")
        if pch_file.is_file():
            with open(pch_file, encoding="utf8") as file:
                if "File generated by pre-commit" not in file.read(4096):
                    raise colrev_exceptions.RepoSetupError(
                        "pre-commit hooks not installed (use pre-commit install)"
                    )
        else:
            raise colrev_exceptions.RepoSetupError(
                "pre-commit hooks not installed (use pre-commit install)"
            )

        psh_file = Path(".git/hooks/pre-push")
        if psh_file.is_file():
            with open(psh_file, encoding="utf8") as file:
                if "File generated by pre-commit" not in file.read(4096):
                    raise colrev_exceptions.RepoSetupError(
                        "pre-commit push hooks not installed "
                        "(use pre-commit install --hook-type pre-push)"
                    )
        else:
            raise colrev_exceptions.RepoSetupError(
                "pre-commit push hooks not installed "
                "(use pre-commit install --hook-type pre-push)"
            )

        pcmh_file = Path(".git/hooks/prepare-commit-msg")
        if pcmh_file.is_file():
            with open(pcmh_file, encoding="utf8") as file:
                if "File generated by pre-commit" not in file.read(4096):
                    raise colrev_exceptions.RepoSetupError(
                        "pre-commit prepare-commit-msg hooks not installed "
                        "(use pre-commit install --hook-type prepare-commit-msg)"
                    )
        else:
            raise colrev_exceptions.RepoSetupError(
                "pre-commit prepare-commit-msg hooks not installed "
                "(use pre-commit install --hook-type prepare-commit-msg)"
            )

        return True

    def check_repo(self) -> dict:
        """Check whether the repository is in a consistent state
        Entrypoint for pre-commit hooks
        """

        # pylint: disable=not-a-mapping

        self.review_manager.notified_next_process = colrev.process.ProcessType.check

        # We work with exceptions because each issue may be raised in different checks.
        # Currently, linting is limited for the scripts.

        environment_manager = self.review_manager.get_environment_manager()
        check_scripts: list[dict[str, typing.Any]] = [
            {
                "script": environment_manager.check_git_installed,
                "params": [],
            },
            {
                "script": environment_manager.check_docker_installed,
                "params": [],
            },
            {
                "script": environment_manager.build_docker_images,
                "params": [],
            },
            {"script": self.__check_git_conflicts, "params": []},
            {"script": self.check_repository_setup, "params": []},
            {"script": self.__check_software, "params": []},
        ]

        if self.review_manager.dataset.records_file.is_file():
            if self.review_manager.dataset.records_file_in_history():
                prior = self.review_manager.dataset.retrieve_prior()
                self.review_manager.logger.debug("prior")
                self.review_manager.logger.debug(
                    self.review_manager.p_printer.pformat(prior)
                )
            else:  # if RECORDS_FILE not yet in git history
                prior = {}

            status_data = self.review_manager.dataset.retrieve_status_data(prior=prior)

            main_refs_checks = [
                {"script": self.review_manager.dataset.check_sources, "params": []},
                {
                    "script": self.review_manager.dataset.check_main_records_duplicates,
                    "params": {"status_data": status_data},
                },
            ]

            if prior:  # if RECORDS_FILE in git history
                main_refs_checks.extend(
                    [
                        {
                            "script": self.review_manager.dataset.check_persisted_id_changes,
                            "params": {"prior": prior, "status_data": status_data},
                        },
                        {
                            "script": self.review_manager.dataset.check_main_records_origin,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.review_manager.dataset.check_fields,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.review_manager.dataset.check_status_transitions,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.review_manager.dataset.check_main_records_screen,
                            "params": {"status_data": status_data},
                        },
                    ]
                )

            check_scripts.extend(main_refs_checks)

            data_operation = self.review_manager.get_data_operation(
                notify_state_transition_operation=False
            )
            data_checks = [
                {
                    "script": data_operation.main,
                    "params": [],
                },
                {
                    "script": self.review_manager.update_status_yaml,
                    "params": [],
                },
            ]

            check_scripts.extend(data_checks)

        failure_items = []
        for check_script in check_scripts:
            try:
                if not check_script["params"]:
                    self.review_manager.logger.debug(
                        "%s() called", check_script["script"].__name__
                    )
                    check_script["script"]()
                else:
                    self.review_manager.logger.debug(
                        "%s(params) called", check_script["script"].__name__
                    )
                    if isinstance(check_script["params"], list):
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](**check_script["params"])
                self.review_manager.logger.debug(
                    "%s: passed\n", check_script["script"].__name__
                )
            except (
                colrev_exceptions.MissingDependencyError,
                colrev_exceptions.GitConflictError,
                colrev_exceptions.PropagatedIDChange,
                colrev_exceptions.DuplicateIDsError,
                colrev_exceptions.OriginError,
                colrev_exceptions.FieldValueError,
                colrev_exceptions.StatusTransitionError,
                colrev_exceptions.UnstagedGitChangesError,
                colrev_exceptions.StatusFieldValueError,
            ) as exc:
                failure_items.append(f"{type(exc).__name__}: {exc}")

        if len(failure_items) > 0:
            return {"status": FAIL, "msg": "  " + "\n  ".join(failure_items)}
        return {"status": PASS, "msg": "Everything ok."}


if __name__ == "__main__":
    pass
