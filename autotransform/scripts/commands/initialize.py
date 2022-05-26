# AutoTransform
# Large scale, component based code modification library
#
# Licensed under the MIT License <http://opensource.org/licenses/MIT>
# SPDX-License-Identifier: MIT
# Copyright (c) 2022-present Nathan Rockenbach <http://github.com/nathro>

# @black_format

"""The config command is used to update the config files for AutoTransform."""

import json
import os
import pathlib
import subprocess
from argparse import ArgumentParser, Namespace
from configparser import ConfigParser
from typing import Any, Dict, List, Mapping, Tuple

from autotransform.change.state import ChangeState
from autotransform.config.default import DefaultConfigFetcher
from autotransform.repo.base import Repo
from autotransform.repo.git import GitRepo
from autotransform.repo.github import GithubRepo
from autotransform.runner.github import GithubRunner
from autotransform.runner.local import LocalRunner
from autotransform.schema.schema import AutoTransformSchema
from autotransform.step.action import ActionType
from autotransform.step.base import Step
from autotransform.step.condition.comparison import ComparisonType
from autotransform.step.condition.state import ChangeStateCondition
from autotransform.step.condition.updated import UpdatedAgoCondition
from autotransform.step.conditional import ConditionalStep
from autotransform.util.console import choose_yes_or_no, get_str, info, input_int, input_string
from autotransform.util.schedule import input_schedule_bundle


def add_args(parser: ArgumentParser) -> None:
    """Adds the args to a subparser that are required to initialize AutoTransform.

    Args:
        parser (ArgumentParser): The parser for the schema run.
    """

    parser.set_defaults(func=initialize_command_main)


def get_config_credentials(
    get_token: bool, prev_inputs: Mapping[str, Any]
) -> Tuple[Dict[str, str], Mapping[str, Any]]:
    """Get the credentials section of a config file.

    Args:
        get_token (bool): Whether to get a Github Token.
        prev_inputs (Mapping[str, Any]): Previously used input values.

    Returns:
        Tuple[Dict[str, Any], Mapping[str, Any]]: A tuple containing the new section and the
            supplied inputs.
    """

    use_github = choose_yes_or_no("Do you want to configure AutoTransform to use Github?")
    if not use_github:
        return {}, {"use_github": False}

    section: Dict[str, str] = {}
    inputs: Dict[str, Any] = {"use_github": True}

    # Github tokens should only ever be used in user configs
    if get_token:
        github_token = get_str("Enter your Github Token:", secret=True)
        section["github_token"] = github_token

    if choose_yes_or_no("Use Github Enterprise?"):
        github_base_url = input_string(
            "Enter the base URL for GHE API requests (i.e. https://api.your_org-github.com):",
            "Github Enterprise base URL",
            previous=prev_inputs.get("github_base_url"),
        )
        section["github_base_url"] = github_base_url
        inputs["github_base_url"] = github_base_url
    else:
        inputs["github_base_url"] = None

    return section, inputs


def get_config_imports(prev_inputs: Mapping[str, Any]) -> Tuple[Dict[str, str], Mapping[str, Any]]:
    """Gets the imports section of a config file.

    Args:
        prev_inputs (Mapping[str, Any]): Previously used input values.

    Returns:
        Tuple[Dict[str, Any], Mapping[str, Any]]: A tuple containing the new section and the
            supplied inputs.
    """

    use_custom_components = choose_yes_or_no("Would you like to use custom component modules?")
    if not use_custom_components:
        return {}, {}

    section: Dict[str, str] = {}
    inputs: Dict[str, Any] = {}

    custom_components = input_string(
        "Enter a comma separated list of custom components:",
        "custom components",
        previous=prev_inputs.get("import_components"),
    )
    section["components"] = custom_components
    inputs["import_components"] = custom_components

    return section, inputs


def get_config_runner(prev_inputs: Mapping[str, Any]) -> Tuple[Dict[str, Any], Mapping[str, Any]]:
    """Gets the runner section of a config file.

    Args:
        prev_inputs (Mapping[str, Any]): Previously used input values.

    Returns:
        Tuple[Dict[str, Any], Mapping[str, Any]]: A tuple containing the new section and the
            supplied inputs.
    """

    section = {}
    inputs: Dict[str, Any] = {}

    # Get local runner
    local_runner = input_string(
        "Enter a JSON encoded runner for local runs:",
        "local runner",
        previous=prev_inputs.get("runner_local"),
        default=json.dumps(LocalRunner({}).bundle()),
    )
    section["local"] = local_runner
    inputs["runner_local"] = local_runner

    # Get remote runner
    remote_runner = input_string(
        "Enter a JSON encoded runner for remote runs:",
        "remote runner",
        previous=prev_inputs.get("runner_remote"),
        default=json.dumps(
            GithubRunner(
                {
                    "run_workflow": "autotransform_run.yml",
                    "update_workflow": "autotransform_update.yml",
                }
            ).bundle()
        ),
    )
    section["remote"] = remote_runner
    inputs["runner_remote"] = remote_runner

    return section, inputs


def write_config(
    config_path: str, config_name: str, prev_inputs: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Gets all of the inputs required to create a config file and write it.

    Args:
        config_path (str): The path to the config.
        config_name (str): The name of the config: user, repo, or cwd.
        prev_inputs (Mapping[str, Any]): Previously specified values.

    Returns:
        Mapping[str, Any]: The inputs that were obtained when setting up the config.
    """

    info(f"Initializing {config_name} config located at: {config_path}")

    if os.path.exists(config_path):
        reset_config = choose_yes_or_no("An existing config was found, replace it?")
        if not reset_config:
            return {}

    config = ConfigParser()
    config["IMPORTS"] = {}
    config["RUNNER"] = {}
    inputs: Dict[str, Any] = {}

    # Set up credentials configuration
    credentials_section, credentials_inputs = get_config_credentials(
        config_name == "user", prev_inputs
    )
    config["CREDENTIALS"] = credentials_section
    for key, value in credentials_inputs.items():
        inputs[key] = value

    # Set up custom component configuration
    imports_section, imports_inputs = get_config_imports(prev_inputs)
    config["IMPORTS"] = imports_section
    for key, value in imports_inputs.items():
        inputs[key] = value

    # Set up runner configuration
    runner_section, runner_inputs = get_config_runner(prev_inputs)
    config["RUNNER"] = runner_section
    for key, value in runner_inputs.items():
        inputs[key] = value

    with open(config_path, "w", encoding="UTF-8") as config_file:
        config.write(config_file)

    return inputs


def initialize_workflows(repo_dir: str, examples_dir: str, prev_inputs: Mapping[str, Any]) -> None:
    """Set up the workflow files for using Github workflows.

    Args:
        repo_dir (str): The top level directory of the repo.
        examples_dir (str): Where example files are located.
        prev_inputs (Mapping[str, Any]): Previous inputs from configuration.
    """

    bot_email = get_str("Enter the email of the account used for automation:")
    bot_name = get_str("Enter the name of the account used for automation:")
    custom_components = prev_inputs.get("import_components")
    workflows = [
        "autotransform_manage.yml",
        "autotransform_run.yml",
        "autotransform_schedule.yml",
        "autotransform_update.yml",
    ]
    for workflow in workflows:
        with open(f"{examples_dir}/workflows/{workflow}", "r", encoding="UTF-8") as workflow_file:
            workflow_text = workflow_file.read()
        workflow_text = workflow_text.replace("<BOT EMAIL>", bot_email)
        workflow_text = workflow_text.replace("<BOT NAME>", bot_name)
        if custom_components is not None:
            workflow_text = workflow_text.replace("<CUSTOM COMPONENTS>", custom_components)
        else:
            workflow_text = "\n".join(
                [line for line in workflow_text.split("\n") if "<CUSTOM COMPONENTS>" not in line]
            )
        with open(
            f"{repo_dir}/.github/workflows/{workflow}", "w", encoding="UTF-8"
        ) as workflow_file:
            workflow_file.write(workflow_text)
            workflow_file.flush()


def get_manage_bundle(
    use_github_actions: bool, repo: Repo, prev_inputs: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Get the bundle needed to create the manage.json file.

    Args:
        use_github_actions (bool): Whether the repo uses Github Actions.
        repo (Repo): The repo being managed.
        prev_inputs (Mapping[str, Any]): Previous inputs from configuration.

    Returns:
        Mapping[str, Any]: The manage bundle.
    """

    if use_github_actions:
        remote_runner: Any = GithubRunner(
            {
                "run_workflow": "autotransform_run.yml",
                "update_workflow": "autotransform_update.yml",
            }
        ).bundle()
    else:
        remote_runner = prev_inputs.get("runner_remote")
        if remote_runner is None:
            remote_runner = get_str("Enter a JSON encoded runner for remote runs:")
        remote_runner = json.loads(remote_runner)
    steps: List[Step] = []

    # Merge approved changes
    if choose_yes_or_no("Automatically merge approved changes?"):
        steps.append(
            ConditionalStep(
                {
                    "condition": ChangeStateCondition(
                        {"comparison": ComparisonType.EQUAL, "state": ChangeState.APPROVED}
                    ),
                    "action_type": ActionType.MERGE,
                }
            )
        )

    # Abandon rejected changes
    if choose_yes_or_no("Automatically abandon rejected changes?"):
        steps.append(
            ConditionalStep(
                {
                    "condition": ChangeStateCondition(
                        {"comparison": ComparisonType.EQUAL, "state": ChangeState.CHANGES_REQUESTED}
                    ),
                    "action_type": ActionType.ABANDON,
                }
            )
        )

    # Update stale changes
    if choose_yes_or_no("Automatically update stale changes?"):
        days_stale = input_int("How many days to consider a change stale?", min_val=0, max_val=6)
        steps.append(
            ConditionalStep(
                {
                    "condition": UpdatedAgoCondition(
                        {
                            "comparison": ComparisonType.GREATER_THAN_OR_EQUAL,
                            "time": days_stale * 24 * 60 * 60,
                        }
                    ),
                    "action_type": ActionType.ABANDON,
                }
            )
        )

    return {
        "repo": repo.bundle(),
        "remote_runner": remote_runner,
        "steps": [step.bundle() for step in steps],
    }


def initialize_repo(repo_dir: str, prev_inputs: Mapping[str, Any]) -> None:
    """Set up a repo to work with AutoTransform.

    Args:
        repo_dir (str): The top level directory of the repo.
        prev_inputs (Mapping[str, Any]): Previous inputs from configuration.
    """

    package_dir = str(pathlib.Path(__file__).parent.parent.parent.resolve()).replace("\\", "/")
    examples_dir = f"{package_dir}/examples"

    use_github = prev_inputs.get("use_github")
    if use_github is None:
        use_github = choose_yes_or_no("Do you want to configure AutoTransform to use Github?")

    # Set up workflow files
    use_github_actions = choose_yes_or_no("Use Github Actions for AutoTransform?")
    if use_github and use_github_actions:
        initialize_workflows(repo_dir, examples_dir, prev_inputs)

    # Get the repo
    base_branch_name = get_str("Enter the name of the base branch for the repo(i.e. main,master):")
    if use_github:
        github_name = get_str("Enter the fully qualified name of the github repo(owner/repo):")
        repo: Repo = GithubRepo(
            {"base_branch_name": base_branch_name, "full_github_name": github_name}
        )
    else:
        repo = GitRepo({"base_branch_name": base_branch_name})

    # Set up the sample schema
    use_sample_schema = choose_yes_or_no("Would you like to include the sample schema?")
    if use_sample_schema:
        with open(
            f"{examples_dir}/schemas/black_format.json", "r", encoding="UTF-8"
        ) as schema_file:
            schema = AutoTransformSchema.from_json(schema_file.read())
        schema._repo = repo  # pylint: disable=protected-access
        with open(
            f"{repo_dir}/autotransform/schemas/black_format.json", "w", encoding="UTF-8"
        ) as schema_file:
            schema_file.write(schema.to_json(pretty=True))
            schema_file.flush()

        # Get requirements
        with open(f"{examples_dir}/requirements.txt", "r", encoding="UTF-8") as requirements_file:
            requirements = requirements_file.read()
    else:
        requirements = ""

    # Set up requirements file
    with open(
        f"{repo_dir}/autotransform/requirements.txt", "w", encoding="UTF-8"
    ) as requirements_file:
        requirements_file.write(requirements)
        requirements_file.flush()

    # Set up manage file
    manage_bundle = get_manage_bundle(use_github_actions, repo, prev_inputs)
    with open(f"{repo_dir}/autotransform/manage.json", "w", encoding="UTF-8") as manage_file:
        manage_file.write(json.dumps(manage_bundle, indent=4))
        manage_file.flush()

    # Set up schedule file
    schedule_bundle = input_schedule_bundle(manage_bundle["runner"], use_sample_schema)
    with open(f"{repo_dir}/autotransform/schedule.json", "w", encoding="UTF-8") as schedule_file:
        schedule_file.write(json.dumps(schedule_bundle, indent=4))
        schedule_file.flush()


def initialize_command_main(_args: Namespace) -> None:
    """The main method for the schedule command, handles the actual execution of scheduling runs.

    Args:
        _args (Namespace): The arguments supplied to the initialize command.
    """

    user_config_path = (
        f"{DefaultConfigFetcher.get_user_config_dir()}/{DefaultConfigFetcher.CONFIG_NAME}"
    )
    inputs = write_config(user_config_path, "user", {})

    # Set up repo
    try:
        dir_cmd = ["git", "rev-parse", "--show-toplevel"]
        repo_dir = subprocess.check_output(dir_cmd, encoding="UTF-8").replace("\\", "/").strip()
        info(f"Repo found at {repo_dir}")
        setup_repo = choose_yes_or_no("Should AutoTransoform set up the repo?")
    except Exception:  # pylint: disable=broad-except
        info("No git repo to set up, run inside a git repo to set it up.")
        repo_dir = ""
        setup_repo = False

    if setup_repo:
        repo_config_path = (
            f"{DefaultConfigFetcher.get_repo_config_dir()}/{DefaultConfigFetcher.CONFIG_NAME}"
        )
        inputs = write_config(repo_config_path, "repo", inputs)
        initialize_repo(repo_dir, inputs)

    if repo_dir == "" and choose_yes_or_no("Set up configuration for current working directory?"):
        cwd_config_path = (
            f"{DefaultConfigFetcher.get_cwd_config_dir()}/{DefaultConfigFetcher.CONFIG_NAME}"
        )
        write_config(cwd_config_path, "current working directory", inputs)
