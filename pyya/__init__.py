import keyword
import logging
from copy import deepcopy
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import toml as _toml
import yaml as _yaml
from camel_converter import to_snake as _to_snake
from munch import munchify as _munchify
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator
from toml import decoder as _toml_decoder


logging.basicConfig(format='%(asctime)-15s \t%(levelname)-8s \t%(name)-8s \t%(message)s')
logger = logging.getLogger(__name__)


ConfigType = Dict[str, Any]


PyyaConfig = Any


class PyyaError(RuntimeError): ...


def init_config(
    config: Union[str, Path] = 'config.yaml',
    default_config: Union[str, Path] = 'default.config.yaml',
    *,
    convert_keys_to_snake_case: bool = False,
    add_underscore_prefix_to_keywords: bool = False,
    raise_error_non_identifiers: bool = False,
    replace_dashes_with_underscores: bool = False,
    merge_configs: bool = True,
    sections_ignored_on_merge: Optional[List[str]] = None,
    validate_data_types: bool = True,
    allow_extra_sections: bool = True,
    warn_extra_sections: bool = True,
    _generate_stub: bool = False,
    _stub_variable_name: str = 'config',
) -> PyyaConfig:
    """Initialize attribute-stylish configuration from YAML/TOML file.

    Args:
        config: path to production config file
        default_config: path to default config file
        convert_keys_to_snake_case: convert config section names to snake case
        add_underscore_prefix_to_keywords: add underscore prefix to Python keywords
        raise_error_non_identifiers: raise error if config section name is not a valid identifier
        replace_dashes_with_underscores: replace dashes with underscores in section names and keys
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
                _raw_data[section] = entry
                logger.debug(f'section `{".".join(sections)}` with value `{entry}` taken from {default_config}')
            elif isinstance(entry, Dict):
                _merge_configs(_raw_data[section], entry, sections)
            # TODO: add support for merging lists
            else:
                logger.debug(f'section `{".".join(sections)}` already exists in {config}, skipping')
            sections.pop()

    def _sanitize_section(section: Any) -> Any:
        if not isinstance(section, str):
            return section
        if convert_keys_to_snake_case:
            logger.debug(f'converting section `{section}` to snake case')
            section = _to_snake(section)
        if raise_error_non_identifiers and not section.isidentifier():
            err_msg = f'section `{section}` is not a valid identifier, aborting'
            logger.error(err_msg)
            raise PyyaError(err_msg)
        if replace_dashes_with_underscores:
            section = section.replace('-', '_')
        if add_underscore_prefix_to_keywords and keyword.iskeyword(section):
            logger.debug(f'section `{section}` is a keyword, renaming to `_{section}`')
            section = f'_{section}'
        return section

    def _pop_ignored_keys(data: ConfigType) -> ConfigType:
        for key, entry in data.copy().items():
            if sections_ignored_on_merge and key in sections_ignored_on_merge:
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
                    if not isinstance(key, str):
                        continue
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

    def is_identifier(data: str) -> bool:
        return not keyword.iskeyword(data) and data.isidentifier()

    def _model_and_stub_from_dict(
        name: str, data: Dict[Any, Any], path: Optional[List[str]] = None
    ) -> Tuple[Type[ExtraBase], str]:
        fields: Dict[Any, Any] = {}
        if path is None:
            path = []
        class_name = ''.join(part.capitalize() if i > 0 else part for i, part in enumerate(path + [name])).replace(
            '-', '_'
        )
        stub_lines = [f'class {class_name}(dict[str, Any]):']
        nested_stubs = []
        py_type: Any
        for section, entry in data.items():
            if not isinstance(section, str):
                continue
            if isinstance(entry, Dict):
                nested_model, nested_stub = _model_and_stub_from_dict(section, entry, path + [name])
                if is_identifier(section):
                    stub_lines.append(f'    {section}: {class_name + section.capitalize()}')
                    nested_stubs.append(nested_stub)
                fields[section] = (nested_model, entry)
            elif isinstance(entry, list) and entry:
                first_item = entry[0]
                if isinstance(first_item, Dict):
                    nested_model, nested_stub = _model_and_stub_from_dict(
                        f'{section.capitalize()}_item', first_item, path + [name]
                    )
                    if is_identifier(section):
                        stub_lines.append(f'    {section}: list[{class_name + section.capitalize()}_item]')
                        nested_stubs.append(nested_stub)
                    fields[section] = (List[nested_model], entry)  # type: ignore
                else:
                    py_type = type(first_item)
                    if is_identifier(section):
                        stub_lines.append(f'    {section}: list[{py_type.__name__}]')
                    fields[section] = (List[py_type], entry)
            elif isinstance(entry, list):
                if is_identifier(section):
                    stub_lines.append(f'    {section}: list[Any]')
                fields[section] = (List[Any], entry)
            else:
                py_type = type(entry)
                if is_identifier(section):
                    stub_lines.append(f'    {section}: {py_type.__name__}')
                fields[section] = (py_type, entry)
        if len(stub_lines) == 1:
            stub_lines = [f'class {class_name}(dict[Any, Any]): ...']
        stub_code = '\n\n'.join(nested_stubs + ['\n'.join(stub_lines)])
        return create_model(name, **fields, __base__=ExtraBase), stub_code

    def _get_default_raw_data() -> ConfigType:
        try:
            try:
                file_path = Path(default_config)
                if (ext := file_path.suffix) not in ('.yaml', '.yml', '.toml'):
                    raise PyyaError(f'{default_config} file format is not supported') from None
                file_handler = _yaml.safe_load if ext in ('.yaml', '.yml') else _toml.load
                with open(Path(default_config)) as fstream:
                    _default_raw_data: Optional[ConfigType] = file_handler(fstream)
            except (_yaml.YAMLError, _toml_decoder.TomlDecodeError) as e:
                raise PyyaError(f'{default_config} file is corrupted: {e}') from None
            if _default_raw_data is None:
                raise FileNotFoundError()
        except FileNotFoundError as e:
            logger.error(e)
            raise PyyaError(f'{default_config} file is missing or empty') from None
        except PyyaError as e:
            logger.error(e)
            raise e from None
        except Exception as e:
            err_msg = f'{default_config} Unknown error: {e}'
            logger.error(err_msg)
            raise PyyaError(err_msg) from None
        _default_raw_data = _sanitize_keys(_default_raw_data)
        return _default_raw_data

    if _generate_stub:
        output_file = Path(config)
        if output_file.exists():
            err_msg = f'{output_file} already exists'
            logger.error(err_msg)
            raise PyyaError(err_msg)
        _default_raw_data = _get_default_raw_data()
        _, stub = _model_and_stub_from_dict('Config', _default_raw_data)
        stub_full = (
            f'# {output_file} was autogenerated from {default_config} with pyya CLI tool, see `pyya -h`\n'
            f'from __future__ import annotations\n\n'
            f'from typing import Any\n\n'
            f'{stub}\n\n'
            '# for type hints to work the variable name created with pyya.init_config\n'
            '# should have the same name (e.g. config = pyya.init_config())\n'
            f'{_stub_variable_name}: Config\n'
        )
        output_file.write_text(stub_full)
        logger.info(f'{output_file} created')
        return None

    try:
        file_path = Path(config)
        if (ext := file_path.suffix) not in ('.yaml', '.yml', '.toml'):
            raise PyyaError(f'{config} file format is not supported') from None
        file_handler = _yaml.safe_load if ext in ('.yaml', '.yml') else _toml.load
        with open(Path(config)) as fstream:
            _raw_data: ConfigType = file_handler(fstream) or {}
            _raw_data = _sanitize_keys(_raw_data)
    except (_yaml.YAMLError, _toml_decoder.TomlDecodeError) as e:
        raise PyyaError(f'{config} file is corrupted: {e}') from None
    except FileNotFoundError:
        logger.warning(f'{config} file not found, using {default_config}')
        _raw_data = {}
    except PyyaError as e:
        logger.error(e)
        raise e from None
    except Exception as e:
        err_msg = f'{config} Unknown error: {e}'
        logger.error(err_msg)
        raise PyyaError(err_msg) from None

    if merge_configs:
        if sections_ignored_on_merge is None:
            sections_ignored_on_merge = []
        try:
            sections_ignored_on_merge = [_sanitize_section(s) for s in sections_ignored_on_merge]
        except Exception as e:
            err_msg = f'Failed parsing `sections_ignored_on_merge`: {e!r}'
            logger.error(err_msg)
            raise PyyaError(err_msg) from None
        _default_raw_data = _get_default_raw_data()
        # create copy for logging (only overwritten fields)
        _raw_data_copy = deepcopy(_raw_data)
        _merge_configs(_raw_data, _default_raw_data)
        logger.debug(f'Resulting config after merge:\n{pformat(_raw_data)}')
        if validate_data_types:
            ConfigModel, _ = _model_and_stub_from_dict('ConfigModel', _default_raw_data)
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


__all__ = ['init_config', 'logger']
