# AutoTransform
# Large scale, component based code modification library
#
# Licensed under the MIT License <http://opensource.org/licenses/MIT>
# SPDX-License-Identifier: MIT
# Copyright (c) 2022-present Nathan Rockenbach <http://github.com/nathro>

# @black_format

"""The implementation for the CodeownersBatcher."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, ClassVar, Dict, List, Optional, Sequence

from autotransform.batcher.base import Batch, Batcher, BatcherName
from autotransform.item.base import Item
from autotransform.item.file import FileItem
from codeowners import CodeOwners


class CodeownersBatcher(Batcher):
    """A batcher which uses Github CODEOWNERS files to separate changes by owner. Titles will
    be of the form 'prefix <owner>'

    Attributes:
        codeowners_location (str): The location of the CODEOWNERS file.
        prefix (str): The prefix to use for titles.
        max_batch_size (Optional[int]): The maximum size of any batch. If None, then batches will
            have no max size. Defaults to None.
        metadata (Optional[Dict[str, Any]], optional): The metadata to associate with
            Batches. Defaults to None.
        name (ClassVar[BatcherName]): The name of the Component.
    """

    codeowners_location: str
    prefix: str
    max_batch_size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    name: ClassVar[BatcherName] = BatcherName.CODEOWNERS

    # pylint: disable=too-many-branches
    def batch(self, items: Sequence[Item]) -> List[Batch]:
        """Take filtered Items and batch them based on CODEOWNERS.

        Args:
            items (Sequence[Item]): The filtered Items to separate.

        Returns:
            List[Batch]: A list of Batches representing all items owned by a given
                owner.
        """

        team_owners: Dict[str, List[Item]] = {}
        individual_owners: Dict[str, List[Item]] = {}
        no_owners: List[Item] = []

        with open(self.codeowners_location, mode="r", encoding="UTF-8") as codeowners_file:
            codeowners = CodeOwners(codeowners_file.read())

        # Build Owner Dictionaries
        for item in items:
            assert isinstance(item, FileItem)
            owner = codeowners.of(item.get_path())

            if not owner:
                no_owners.append(item)
                continue

            owner_tuple = owner[0]
            if owner_tuple[0] == "USERNAME":
                owner_name = owner_tuple[1].removeprefix("@")
                if owner_name not in individual_owners:
                    individual_owners[owner_name] = []
                individual_owners[owner_name].append(item)

            if owner_tuple[0] == "TEAM":
                owner_name = owner_tuple[1].removeprefix("@")
                if owner_name not in team_owners:
                    team_owners[owner_name] = []
                team_owners[owner_name].append(item)

        batches: List[Batch] = []

        # Add batches based on team owners
        for team_owner, team_items in team_owners.items():
            i = 1
            if self.max_batch_size is not None and len(team_items) > self.max_batch_size:
                num_chunks = math.ceil(len(team_items) / self.max_batch_size)
                chunk_size = math.ceil(len(team_items) / num_chunks)
                item_chunks = [
                    team_items[i : i + chunk_size] for i in range(0, len(team_items), chunk_size)
                ]
                title = f"[{i}/{num_chunks}]{self.prefix} {team_owner}"
            else:
                num_chunks = 1
                item_chunks = [team_items]
                title = f"{self.prefix} {team_owner}"
            for chunk_items in item_chunks:
                batch: Batch = {"items": chunk_items, "title": title}
                # Deepcopy metadata to ensure mutations don't apply to all Batches
                metadata = deepcopy(self.metadata or {})
                if "team_reviewers" in metadata and team_owner not in metadata["team_reviewers"]:
                    metadata["team_reviewers"].append(team_owner)
                else:
                    metadata["team_reviewers"] = [team_owner]
                batch["metadata"] = metadata
                batches.append(batch)
                i += 1
                title = f"[{i}/{num_chunks}]{self.prefix} {team_owner}"

        # Add batches based on individual owners
        for individual_owner, individual_items in individual_owners.items():
            i = 1
            if self.max_batch_size is not None and len(individual_items) > self.max_batch_size:
                num_chunks = math.ceil(len(individual_items) / self.max_batch_size)
                chunk_size = math.ceil(len(individual_items) / num_chunks)
                item_chunks = [
                    individual_items[i : i + chunk_size]
                    for i in range(0, len(individual_items), chunk_size)
                ]
                title = f"[{i}/{num_chunks}]{self.prefix} {individual_owner}"
            else:
                num_chunks = 1
                item_chunks = [individual_items]
                title = f"{self.prefix} {individual_owner}"
            for chunk_items in item_chunks:
                batch = {"items": chunk_items, "title": title}
                # Deepcopy metadata to ensure mutations don't apply to all Batches
                metadata = deepcopy(self.metadata or {})
                if "reviewers" in metadata and individual_owner not in metadata["reviewers"]:
                    metadata["reviewers"].append(individual_owner)
                else:
                    metadata["reviewers"] = [individual_owner]
                batch["metadata"] = metadata
                batches.append(batch)
                i += 1
                title = f"[{i}/{num_chunks}]{self.prefix} {individual_owner}"

        # Add unowned batch
        if no_owners:
            i = 1
            if self.max_batch_size is not None and len(no_owners) > self.max_batch_size:
                num_chunks = math.ceil(len(no_owners) / self.max_batch_size)
                chunk_size = math.ceil(len(no_owners) / num_chunks)
                item_chunks = [
                    no_owners[i : i + chunk_size] for i in range(0, len(no_owners), chunk_size)
                ]
                title = f"[{i}/{num_chunks}]{self.prefix} unowned"
            else:
                num_chunks = 1
                item_chunks = [no_owners]
                title = f"{self.prefix} unowned"
            for chunk_items in item_chunks:
                batch = {"items": chunk_items, "title": title}
                if self.metadata is not None:
                    # Deepcopy metadata to ensure mutations don't apply to all Batches
                    batch["metadata"] = deepcopy(self.metadata)
                batches.append(batch)
                i += 1
                title = f"[{i}/{num_chunks}]{self.prefix} unowned"

            batches.append(batch)

        return batches
