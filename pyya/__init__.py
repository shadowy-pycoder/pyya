import keyword
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from camel_converter import to_snake
from munch import Munch, munchify


logging.basicConfig(format='%(asctime)-15s \t%(levelname)-8s \t%(name)-8s \t%(message)s')
logger = logging.getLogger(__name__)


ConfigType = Dict[str, Any]


class PyyaError(RuntimeError): ...


def init_config(
    config: Union[str, Path] = 'config.yaml',
    default_config: Union[str, Path] = 'default.config.yaml',
    *,
    convert_keys_to_snake_case: bool = False,
    add_underscore_prefix_to_keywords: bool = False,
    raise_error_non_identifiers: bool = False,
) -> Munch:
    def _merge_configs(_raw_data: ConfigType, _default_raw_data: ConfigType) -> None:
        for section, entry in _default_raw_data.items():
            if section not in _raw_data or _raw_data[section] is None:
                f_section = _sanitize_section(section)
                if f_section not in _raw_data:
                    _raw_data[f_section] = entry
                    logger.warning(f'section `{f_section}` with value `{entry}` taken from {default_config}')
                else:
                    logger.debug(f'section `{f_section}` already exists in {config}, skipping')
            elif isinstance(entry, dict):
                _merge_configs(_raw_data[section], entry)
            # TODO: add support for merging lists
            else:
                f_section = _sanitize_section(section)
                if f_section not in _raw_data:
                    _raw_data[f_section] = _raw_data.pop(section, None)
                else:
                    logger.debug(f'section `{f_section}` already exists in {config}, skipping')

    def _sanitize_section(section: str) -> str:
        if convert_keys_to_snake_case:
            logger.debug(f'converting section `{section}` to snake case')
            section = to_snake(section)
        if raise_error_non_identifiers and not section.isidentifier():
            err_msg = f'section `{section}` is not a valid identifier, aborting'
            logger.error(err_msg)
            raise PyyaError(err_msg)
        if add_underscore_prefix_to_keywords and keyword.iskeyword(section):
            logger.warning(f'section `{section}` is a keyword, renaming to `_{section}`')
            section = f'_{section}'
        return section

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
    try:
        with open(Path(config)) as fstream:
            _raw_data: ConfigType = yaml.safe_load(fstream) or {}
    except yaml.YAMLError as e:
        err_msg = f'{config} file is corrupted: {e}'
        logger.error(err_msg)
        raise PyyaError(err_msg) from None
    except FileNotFoundError:
        logger.warning(f'{config} file not found, using {default_config}')
        _raw_data = {}
    _merge_configs(_raw_data, _default_raw_data)
    try:
        return munchify(_raw_data)
    except Exception as e:
        err_msg = f'Failed parsing config file: {e}'
        logger.error(err_msg)
        raise PyyaError(err_msg) from None
