import keyword
import logging
from copy import deepcopy
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, List, Optional, Type, Union

import yaml as _yaml
from camel_converter import to_snake as _to_snake
from munch import Munch as _Munch
from munch import munchify as _munchify
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator


logging.basicConfig(format='%(asctime)-15s \t%(levelname)-8s \t%(name)-8s \t%(message)s')
logger = logging.getLogger(__name__)


ConfigType = Dict[str, Any]


class PyyaConfig(_Munch): ...


class PyyaError(RuntimeError): ...


def init_config(
    config: Union[str, Path] = 'config.yaml',
    default_config: Union[str, Path] = 'default.config.yaml',
    *,
    convert_keys_to_snake_case: bool = False,
    add_underscore_prefix_to_keywords: bool = False,
    raise_error_non_identifiers: bool = False,
    merge_configs: bool = True,
    sections_ignored_on_merge: Optional[List[str]] = None,
    validate_data_types: bool = True,
    allow_extra_sections: bool = True,
    warn_extra_sections: bool = True,
) -> PyyaConfig:
    """Initialize attribute-stylish configuration from YAML file.

    Args:
        config: path to production config file
        default_config: path to default config file
        convert_keys_to_snake_case: convert config section names to snake case
        add_underscore_prefix_to_keywords: add underscore prefix to Python keywords
        raise_error_non_identifiers: raise error if config section name is not a valid identifier
        merge_configs: merge default config with production config (setting to `False` disables flags below)
        sections_ignored_on_merge: list of sections to ignore when merging configs
        validate_data_types: raise error if data types in production config are not the same as default
        allow_extra_sections: raise error on any extra sections in production config
        warn_extra_sections: if extra sections are allowed, warn about extra keys and values
    """

    def _merge_configs(
        _raw_data: ConfigType, _default_raw_data: ConfigType, sections: Optional[List[str]] = None
    ) -> None:
        if sections is None:
            sections = []  # for logging
        for section, entry in _default_raw_data.items():
            sections.append(section)
            if sections_ignored_on_merge:
                if section in sections_ignored_on_merge:
                    logger.debug(f'section `{section}` ignored on merge')
                    continue
                elif isinstance(entry, Dict):
                    # is it fine to proccess already poped dicts on recursion?
                    entry = _pop_ignored_keys(entry)
            if section not in _raw_data or _raw_data[section] is None:
                if section not in _raw_data:
                    _raw_data[section] = entry
                    logger.debug(f'section `{".".join(sections)}` with value `{entry}` taken from {default_config}')
                else:
                    logger.debug(f'section `{".".join(sections)}` already exists in {config}, skipping')
            elif isinstance(entry, Dict):
                _merge_configs(_raw_data[section], entry, sections)
            # TODO: add support for merging lists
            else:
                if section not in _raw_data:
                    _raw_data[section] = _raw_data.pop(section, None)
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

    def _sanitize_keys(data: ConfigType) -> ConfigType:
        for key in data.copy():
            entry = data.pop(key, None)
            key = _sanitize_section(key)
            if isinstance(entry, Dict):
                data[key] = _sanitize_keys(entry)
            else:
                data[key] = entry
        return data

    def _pop_nested(d: Dict[str, Any], dotted_key: str, default: Any = None) -> Any:
        keys = dotted_key.split('.')
        current = d

        for k in keys[:-1]:
            if not isinstance(current, Dict) or k not in current:
                return default
            current = current[k]

        return current.pop(keys[-1], default)

    # https://stackoverflow.com/questions/73958753/return-all-extra-passed-to-pydantic-model
    class ExtraBase(BaseModel):
        model_config = ConfigDict(strict=True, extra='allow' if allow_extra_sections else 'forbid')
        extra: Dict[str, Any] = Field(default={}, exclude=True)

        @model_validator(mode='before')
        @classmethod
        def validator(cls, values: Any) -> Any:
            if cls.model_config.get('extra') == 'allow':
                extra, valid = {}, {}
                for key, value in values.items():
                    if key in cls.model_fields:
                        valid[key] = value
                    else:
                        extra[key] = value
                valid['extra'] = extra
                return valid
            return values

        @property
        def extra_flat(self) -> Any:
            extra_flat = {**self.extra}
            for name, value in self:
                if isinstance(value, ExtraBase):
                    data = {f'{name}.{k}': v for k, v in value.extra_flat.items()}
                    extra_flat.update(data)
            return extra_flat

    def _model_from_dict(name: str, data: Dict[str, Any]) -> Type[BaseModel]:
        fields: Dict[Any, Any] = {}
        for section, entry in data.items():
            if isinstance(entry, Dict):
                nested_model = _model_from_dict(section, entry)
                fields[section] = (nested_model, entry)
            elif isinstance(entry, list) and entry:
                first_item = entry[0]
                if isinstance(first_item, Dict):
                    nested_model = _model_from_dict(f'{section.capitalize()}Item', first_item)
                    fields[section] = (List[nested_model], entry)  # type: ignore
                else:
                    fields[section] = (List[type(first_item)], entry)  # type: ignore
            elif isinstance(entry, list):
                fields[section] = (List[Any], entry)
            else:
                fields[section] = (type(entry), entry)
        return create_model(name, **fields, __base__=ExtraBase)

    try:
        with open(Path(config)) as fstream:
            _raw_data: ConfigType = _yaml.safe_load(fstream) or {}
            _raw_data = _sanitize_keys(_raw_data)
    except _yaml.YAMLError as e:
        err_msg = f'{config} file is corrupted: {e}'
        logger.error(err_msg)
        raise PyyaError(err_msg) from None
    except FileNotFoundError:
        logger.warning(f'{config} file not found, using {default_config}')
        _raw_data = {}

    if merge_configs:
        if sections_ignored_on_merge is None:
            sections_ignored_on_merge = []
        try:
            sections_ignored_on_merge = [_sanitize_section(s) for s in sections_ignored_on_merge]
        except Exception as e:
            err_msg = f'Failed parsing `sections_ignored_on_merge`: {e!r}'
            logger.error(err_msg)
            raise PyyaError(err_msg) from None
        try:
            try:
                with open(Path(default_config)) as fstream:
                    _default_raw_data: Optional[ConfigType] = _yaml.safe_load(fstream)
                    _default_raw_data = _sanitize_keys(_default_raw_data)
            except _yaml.YAMLError as e:
                err_msg = f'{default_config} file is corrupted: {e}'
                logger.error(err_msg)
                raise PyyaError(err_msg) from None
            if _default_raw_data is None:
                raise FileNotFoundError()
        except FileNotFoundError as e:
            logger.error(e)
            raise PyyaError(f'{default_config} file is missing or empty') from None
        # create copy for logging (only overwritten fields)
        _raw_data_copy = deepcopy(_raw_data)
        _merge_configs(_raw_data, _default_raw_data)
        logger.debug(f'Resulting config after merge:\n{pformat(_raw_data)}')
        if validate_data_types:
            ConfigModel = _model_from_dict('ConfigModel', _default_raw_data)
            try:
                validated_raw_data = ConfigModel.model_validate(_raw_data)
                if extra_sections := validated_raw_data.extra_flat:  # type: ignore
                    if warn_extra_sections:
                        logger.warning(f'The following extra sections will be ignored:\n{pformat(extra_sections)}')
                    # remove extra sections from resulting config
                    for k in extra_sections:
                        _pop_nested(_raw_data_copy, k)
                        _pop_nested(_raw_data, k)
            except Exception as e:
                err_msg = f'Failed validating config file: {e!r}'
                logger.error(err_msg)
                raise PyyaError(err_msg) from None
        if _raw_data_copy:
            logger.info(f'The following sections were overwritten:\n{pformat(_raw_data_copy)}')
    try:
        logger.debug(f'Resulting config:\n{pformat(_raw_data)}')
        return _munchify(_raw_data)
    except Exception as e:
        err_msg = f'Failed parsing config file: {e!r}'
        logger.error(err_msg)
        raise PyyaError(err_msg) from None
