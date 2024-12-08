import keyword
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from camel_converter import to_snake
from munch import Munch, munchify


logging.basicConfig(format='%(asctime)-15s \t%(levelname)-8s \t%(name)-8s \t%(message)s')
logger = logging.getLogger('paya')


ConfigType = Dict[str, Any]


class PayaError(RuntimeError): ...


def init_config(
    config: Union[str, Path] = 'config.yaml',
    default_config: Union[str, Path] = 'default.config.yaml',
    *,
    convert_keys_to_snake_case: bool = False,
    raise_error_non_identifiers: bool = False,
) -> Munch:
    def _merge_configs(_raw_data: ConfigType, _default_raw_data: ConfigType) -> None:
        for section, entry in _default_raw_data.items():
            if section not in _raw_data or _raw_data[section] is None:
                section = _sanitize_section(section)
                _raw_data[section] = entry
                logger.warning(f'section `{section}` with value `{entry}` taken from {default_config}')
            elif isinstance(entry, dict):
                section = _sanitize_section(section)
                _merge_configs(_raw_data[section], entry)

    def _sanitize_section(section: str) -> str:
        if convert_keys_to_snake_case:
            logger.warning(f'converting section `{section}` to snake case')
            section = to_snake(section)
        if raise_error_non_identifiers and not section.isidentifier():
            err_msg = f'section `{section}` is not a valid identifier, aborting'
            logger.error(err_msg)
            raise PayaError(err_msg)
        if keyword.iskeyword(section):
            logger.warning(f'section `{section}` is a keyword, renaming to `_{section}`')
            section = f'_{section}'
        return section

    try:
        with open(Path(default_config)) as fstream:
            _default_raw_data: Optional[ConfigType] = yaml.safe_load(fstream)
        if _default_raw_data is None:
            raise FileNotFoundError()
    except FileNotFoundError as e:
        logger.error(e)
        raise PayaError(f'{default_config} file is missing or empty') from None
    try:
        with open(Path(config)) as fstream:
            _raw_data: ConfigType = yaml.safe_load(fstream) or {}
    except FileNotFoundError:
        logger.warning(f'{config} file not found, using {default_config}')
        _raw_data = {}
    _merge_configs(_raw_data, _default_raw_data)
    try:
        return munchify(_raw_data)
    except Exception as e:
        message = f'{default_config} file is corrupted: {repr(e)}'
        logger.error(message)
        raise PayaError(message) from None
