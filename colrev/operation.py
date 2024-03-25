#!/usr/bin/env python3
"""Types and model of CoLRev operations."""
from __future__ import annotations

import typing
from typing import Any
from typing import Callable
from typing import Optional
from typing import TypeVar

import docker
import git
from docker.errors import DockerException

import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Filepaths
from colrev.constants import OperationsType
from colrev.record.record_state_model import RecordStateModel


F = TypeVar("F", bound=Callable[..., Any])


class Operation:
    """Operations correspond to the work steps in a CoLRev project"""

    # pylint: disable=too-few-public-methods

    force_mode: bool
    type: OperationsType

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        operations_type: OperationsType,
        notify_state_transition_operation: bool = True,
    ) -> None:
        self.review_manager = review_manager
        self.force_mode = self.review_manager.force_mode

        self.type = operations_type

        self.notify_state_transition_operation = notify_state_transition_operation
        if notify_state_transition_operation:
            self.review_manager.notify(operation=self)
        else:
            self.review_manager.notify(operation=self, state_transition=False)

        self.cpus = 4

        self.docker_images_to_stop: typing.List[str] = []

        # Note: the following call seems to block the flow (if debug is enabled)
        # self.review_manager.logger.debug(f"Created {self.type} operation")

        # Note: we call review_manager.notify() in the subclasses
        # to make sure that the review_manager calls the right check_preconditions()

    # pylint: disable=too-many-nested-blocks
    @classmethod
    def decorate(cls) -> Callable:
        """Decorator for operations"""

        def decorator_func(func: F) -> Callable:
            def wrapper_func(self, *args, **kwargs) -> Any:  # type: ignore
                # Invoke the wrapped function
                retval = func(self, *args, **kwargs)
                # Conclude the operation
                self.conclude()
                if self.review_manager.in_ci_environment():
                    print("\n\n")
                return retval

            return wrapper_func

        return decorator_func

    def _check_record_state_model_precondition(self) -> None:
        RecordStateModel.check_operation_precondition(self)

    def _require_clean_repo_general(
        self,
        *,
        git_repo: Optional[git.Repo] = None,
        ignore_pattern: Optional[list] = None,
    ) -> bool:
        if git_repo is None:
            git_repo = git.Repo(self.review_manager.path)

        # Note : not considering untracked files.

        if len(git_repo.index.diff("HEAD")) == 0:
            unstaged_changes = [item.a_path for item in git_repo.index.diff(None)]
            if Filepaths.RECORDS_FILE in unstaged_changes:
                git_repo.index.add([Filepaths.RECORDS_FILE])

        # Principle: working tree always has to be clean
        # because processing functions may change content
        if git_repo.is_dirty(index=False):
            changed_files = [item.a_path for item in git_repo.index.diff(None)]
            raise colrev_exceptions.UnstagedGitChangesError(changed_files)

        if git_repo.is_dirty():
            if ignore_pattern is None:
                changed_files = [item.a_path for item in git_repo.index.diff(None)] + [
                    x.a_path
                    for x in git_repo.head.commit.diff()
                    if x.a_path not in [str(Filepaths.STATUS_FILE)]
                ]
                if len(changed_files) > 0:
                    raise colrev_exceptions.CleanRepoRequiredError(changed_files, "")
            else:
                changed_files = [
                    item.a_path
                    for item in git_repo.index.diff(None)
                    if not any(str(ip) in item.a_path for ip in ignore_pattern)
                ] + [
                    x.a_path
                    for x in git_repo.head.commit.diff()
                    if not any(str(ip) in x.a_path for ip in ignore_pattern)
                ]
                if str(Filepaths.STATUS_FILE) in changed_files:
                    changed_files.remove(str(Filepaths.STATUS_FILE))
                if changed_files:
                    raise colrev_exceptions.CleanRepoRequiredError(
                        changed_files, ",".join([str(x) for x in ignore_pattern])
                    )
        return True

    def check_precondition(self) -> None:
        """Check the operation precondition"""

        if self.force_mode:
            return

        if OperationsType.load == self.type:
            self._require_clean_repo_general(
                ignore_pattern=[
                    Filepaths.SEARCH_DIR,
                    Filepaths.SETTINGS_FILE,
                ]
            )
            self._check_record_state_model_precondition()

        elif OperationsType.prep == self.type:
            if self.notify_state_transition_operation:
                self._require_clean_repo_general()
                self._check_record_state_model_precondition()

        elif OperationsType.prep_man == self.type:
            self._require_clean_repo_general(ignore_pattern=[Filepaths.RECORDS_FILE])
            self._check_record_state_model_precondition()

        elif OperationsType.dedupe == self.type:
            self._require_clean_repo_general()
            self._check_record_state_model_precondition()

        elif OperationsType.prescreen == self.type:
            self._require_clean_repo_general()
            self._check_record_state_model_precondition()

        elif OperationsType.pdf_get == self.type:
            self._require_clean_repo_general(ignore_pattern=[Filepaths.PDF_DIR])
            self._check_record_state_model_precondition()

        elif OperationsType.pdf_get_man == self.type:
            self._require_clean_repo_general(ignore_pattern=[Filepaths.PDF_DIR])
            self._check_record_state_model_precondition()

        elif OperationsType.pdf_prep == self.type:
            self._require_clean_repo_general()
            self._check_record_state_model_precondition()

        elif OperationsType.screen == self.type:
            self._require_clean_repo_general()
            self._check_record_state_model_precondition()

        elif OperationsType.data == self.type:
            # __require_clean_repo_general(
            #     ignore_pattern=[
            #         # data.csv, paper.md etc.?,
            #     ]
            # )
            self._check_record_state_model_precondition()

        # ie., implicit pass for format, explore, check, pdf_prep_man

    def conclude(self) -> None:
        """Conclude the operation (stop Docker containers)"""
        try:
            client = docker.from_env()
            for container in client.containers.list():
                if any(x in container.image.tags for x in self.docker_images_to_stop):
                    container.stop()
        except DockerException:
            pass


class FormatOperation(Operation):
    """A dummy operation that is expected to introduce formatting changes only"""

    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager, operations_type=OperationsType.format
        )
        if notify:
            self.review_manager.notify(operation=self)


class CheckOperation(Operation):
    """A dummy operation that is not expected to introduce changes"""

    # pylint: disable=too-few-public-methods

    def __init__(self, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=OperationsType.check,
            notify_state_transition_operation=False,
        )
