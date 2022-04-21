# AutoTransform
# Large scale, component based code modification library
#
# Licensed under the MIT License <http://opensource.org/licenses/MIT>
# SPDX-License-Identifier: MIT
# Copyright (c) 2022-present Nathan Rockenbach <http://github.com/nathro>

"""The type of Batcher, used create a 1:1 mapping."""

from enum import Enum


class BatcherType(str, Enum):
    """A simple enum for 1:1 Batcher to type mapping."""

    CHUNK = "chunk"
    DIRECTORY = "directory"
    SINGLE = "single"
