import keyword
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Type, Union

import yaml
from camel_converter import to_snake as _to_snake
from munch import Munch as _Munch
from munch import munchify as _munchify
from pydantic import BaseModel, ConfigDict, create_model


logging.basicConfig(format='%(asctime)-15s \t%(levelname)-8s \t%(name)-8s \t%(message)s')
logger = logging.getLogger(__name__)


ConfigType = Dict[str, Any]


class PyyaConfig(_Munch): ...


class PyyaError(RuntimeError): ...


def init_config(
    config: Union[str, Path] = 'config.yaml',
    default_config: Union[str, Path] = 'default.config.yaml',
    *,
    merge_configs: bool = True,
    sections_ignored_on_merge: Optional[List[str]] = None,
    convert_keys_to_snake_case: bool = False,
    add_underscore_prefix_to_keywords: bool = False,
    raise_error_non_identifiers: bool = False,
    validate_data_types: bool = True,
    allow_extra_sections: bool = True,
) -> PyyaConfig:
    """Initialize attribute-stylish configuration from YAML file.

    Args:
        config: path to config file
        default_config: path to default config file
        merge_configs: merge default config with config (setting to `False` disables other flags)
        sections_ignored_on_merge: list of sections to ignore when merging configs
        convert_keys_to_snake_case: convert config section names to snake case
        add_underscore_prefix_to_keywords: add underscore prefix to Python keywords
        raise_error_non_identifiers: raise error if config section name is not a valid identifier
        validate_data_types: raise error if data types in config are not the same as default (makes sense only if merge is enabled)
        allow_extra_sections: raise error if there are extra sections in config (may break if section name formatting is enabled)
    """

    def _merge_configs(
        _raw_data: ConfigType, _default_raw_data: ConfigType, sections: Optional[List[str]] = None
    ) -> None:
        if sections is None:
            sections = []  # for logging
        for section, entry in _default_raw_data.items():
            if sections_ignored_on_merge:
                if section in sections_ignored_on_merge:
                    logger.debug(f'section `{section}` ignored on merge')
                    continue
                elif isinstance(entry, Dict):
                    # is it fine to proccess already poped dicts on recursion?
                    entry = _pop_ignored_keys(entry)
            if section not in _raw_data or _raw_data[section] is None:
                f_section = _sanitize_section(section)
                sections.append(f_section)
                if f_section not in _raw_data:
                    _raw_data[f_section] = entry
                    logger.info(f'section `{".".join(sections)}` with value `{entry}` taken from {default_config}')
                else:
                    logger.debug(f'section `{".".join(sections)}` already exists in {config}, skipping')
            elif isinstance(entry, Dict):
                sections.append(section)
                _merge_configs(_raw_data[section], entry, sections)
            # TODO: add support for merging lists
            else:
                f_section = _sanitize_section(section)
                sections.append(f_section)
                if f_section not in _raw_data:
                    _raw_data[f_section] = _raw_data.pop(section, None)
                else:
                    logger.debug(f'section `{".".join(sections)}` already exists in {config}, skipping')
            sections.pop()

    def _sanitize_section(section: str) -> str:
        if convert_keys_to_snake_case:
            logger.debug(f'converting section `{section}` to snake case')
            section = _to_snake(section)
        if raise_error_non_identifiers and not section.isidentifier():
            err_msg = f'section `{section}` is not a valid identifier, aborting'
            logger.error(err_msg)
            raise PyyaError(err_msg)
        if add_underscore_prefix_to_keywords and keyword.iskeyword(section):
            logger.info(f'section `{section}` is a keyword, renaming to `_{section}`')
            section = f'_{section}'
        return section

    def _pop_ignored_keys(data: ConfigType) -> ConfigType:
        for key, entry in data.copy().items():
            if key in sections_ignored_on_merge:
                data.pop(key)
                logger.debug(f'section `{key}` ignored on merge')
            elif isinstance(entry, Dict):
                _pop_ignored_keys(entry)
        return data

    def _model_from_dict(name: str, data: Dict[str, Any], extra: bool) -> Type[BaseModel]:
        fields: Dict[Any, Any] = {}
        for section, entry in data.items():
            if isinstance(entry, Dict):
                nested_model = _model_from_dict(section, entry, extra)
                fields[section] = (nested_model, entry)
            elif isinstance(entry, list) and entry:
                first_item = entry[0]
                if isinstance(first_item, Dict):
                    nested_model = _model_from_dict(f'{section.capitalize()}Item', first_item, extra)
                    fields[section] = (List[nested_model], entry)  # type: ignore
                else:
                    fields[section] = (List[type(first_item)], entry)  # type: ignore
            elif isinstance(entry, list):
                fields[section] = (List[Any], entry)
            else:
                fields[section] = (type(entry), entry)
        extra_value: Literal['allow', 'forbid'] = 'allow' if extra else 'forbid'
        return create_model(name, **fields, __config__=ConfigDict(strict=True, extra=extra_value))

    try:
        with open(Path(config)) as fstream:
            _raw_data: ConfigType = yaml.safe_load(fstream) or {}
    except yaml.YAMLError as e:
        err_msg = f'{config} file is corrupted: {e}'
        logger.error(err_msg)
        raise PyyaError(err_msg) from None
    except FileNotFoundError:
        logger.info(f'{config} file not found, using {default_config}')
        _raw_data = {}

    if merge_configs:
        try:
            try:
                with open(Path(default_config)) as fstream:
                    _default_raw_data: Optional[ConfigType] = yaml.safe_load(fstream)
            except yaml.YAMLError as e:
                err_msg = f'{default_config} file is corrupted: {e}'
                logger.error(err_msg)
                raise PyyaError(err_msg) from None
            if _default_raw_data is None:
                raise FileNotFoundError()
        except FileNotFoundError as e:
            logger.error(e)
            raise PyyaError(f'{default_config} file is missing or empty') from None
        _merge_configs(_raw_data, _default_raw_data)
        if validate_data_types:
            ConfigModel = _model_from_dict('ConfigModel', _default_raw_data, allow_extra_sections)
            try:
                ConfigModel.model_validate(_raw_data)
            except Exception as e:
                err_msg = f'Failed validating config file: {e!r}'
                logger.error(err_msg)
                raise PyyaError(err_msg) from None
    try:
        return _munchify(_raw_data)
    except Exception as e:
        err_msg = f'Failed parsing config file: {e!r}'
        logger.error(err_msg)
        raise PyyaError(err_msg) from None
