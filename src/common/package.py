from __future__ import annotations
import json
from typing import Any, Dict, List, TypedDict

from batcher.base import Batcher
from batcher.factory import BatcherFactory
from command.base import Command
from command.factory import CommandFactory
from common.cachedfile import CachedFile
from filter.base import Filter
from filter.factory import FilterFactory
from input.base import Input
from input.factory import InputFactory
from transformer.base import Transformer
from transformer.factory import TransformerFactory
from validator.base import ValidationError, ValidationResultLevel, Validator
from validator.factory import ValidatorFactory

class PackageConfiguration:
    allowed_validation_level: ValidationResultLevel
    
    def __init__(self, allowed_validation_level: ValidationResultLevel = ValidationResultLevel.NONE):
        self.allowed_validation_level = allowed_validation_level
        
    def bundle(self):
        return {
            "allowed_validation_level": self.allowed_validation_level,
        }
    
    @classmethod   
    def from_data(cls, data: Dict[str, Any]) -> PackageConfiguration:
        if "allowed_validation_level" in data:
            validation_level = data["allowed_validation_level"]
            if not ValidationResultLevel.has_value(validation_level):
                assert validation_level in ValidationResultLevel._member_names_
                validation_level = ValidationResultLevel._member_map_[validation_level]
        else:
            validation_level = ValidationResultLevel.NONE
        return cls(validation_level)

class AutoTransformPackage:
    input: Input
    batcher: Batcher
    transformer: Transformer
    
    filters: List[Filter]
    validators: List[Validator]
    commands: List[Command]
    
    config: PackageConfiguration
    
    def __init__(
        self,
        input: Input,
        batcher: Batcher,
        transformer: Transformer,
        filters: List[Filter] = [],
        validators: List[Validator] = [],
        commands: List[Command] = [],
        config: PackageConfiguration = PackageConfiguration()
    ):
        self.input = input
        self.batcher = batcher
        self.transformer = transformer
        
        self.filters = filters
        self.validators = validators
        self.commands = commands
        
        self.config = config
        
    def run(self):
        valid_files = []
        for file in self.input.get_files():
            f = CachedFile(file)
            is_valid = True
            for filter in self.filters:
                if not filter.is_valid(f):
                    is_valid = False
                    break
            if is_valid:
                valid_files.append(f)
        batches = self.batcher.batch(valid_files)
        batches = [{"files": [valid_files[file] for file in batch["files"]], "metadata": batch["metadata"]} for batch in batches]
        for batch in batches:
            for file in batch["files"]:
                self.transformer.transform(file)
            for validator in self.validators:
                validation_result = validator.validate(batch)
                if validation_result["level"] > self.config.allowed_validation_level:
                    raise ValidationError(validation_result)
            for command in self.commands:
                command.run(batch)
        
    def to_json(self, pretty: bool = False) -> str:
        package = {
            "input": self.input.bundle(),
            "batcher": self.batcher.bundle(),
            "transformer": self.transformer.bundle(),
            
            "filters": [filter.bundle() for filter in self.filters],
            "validators": [validator.bundle() for validator in self.validators],
            "commands": [command.bundle() for command in self.commands],
            
            "config": self.config.bundle(),
        }
        if pretty:
            return json.dumps(package, indent=4)
        return json.dumps(package)
    
    @staticmethod
    def from_json(json_package: str) -> AutoTransformPackage:
        package = json.loads(json_package)
        
        input = InputFactory.get(package["input"])
        batcher = BatcherFactory.get(package["batcher"])
        transformer = TransformerFactory.get(package["transformer"])
        
        filters = [FilterFactory.get(filter) for filter in package["filters"]]
        validators = [ValidatorFactory.get(validator) for validator in package["validators"]]
        commands = [CommandFactory.get(command) for command in package["commands"]]
        
        config = PackageConfiguration.from_data(package["config"])
        
        return AutoTransformPackage(input, batcher, transformer, filters=filters, validators=validators, commands=commands, config=config)