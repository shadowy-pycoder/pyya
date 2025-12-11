from pathlib import Path

import pytest

import pyya


config_path = Path(__file__).parent / 'testdata/config.yaml'
default_config_path = Path(__file__).parent / 'testdata/default.config.yaml'


def test_default_setup() -> None:
    config = pyya.init_config(config=config_path, default_config=default_config_path, validate_data_types=False)
    assert config.app.name == 'myapp_changed'
    assert config.database.user == 'myuser_changed'
    assert config.database.password == 'mypass_changed'
    assert config.database.name == 'mydb_changed'
    assert len(config.database.replicas) == 2
    assert config.logging.level == 'debug'
    assert len(config.cache.servers) == 1
    assert len(config.admins) == 1
    assert config.cache.ttlSeconds == 500
    assert config.errors[1] == 'error 1'
    assert config.environments['prod-env'][1] == 'test'
    assert config.logging.handlers.console['class'] == 'logging.StreamHandler'


def test_convert_snake_case() -> None:
    config = pyya.init_config(
        config=config_path,
        default_config=default_config_path,
        convert_keys_to_snake_case=True,
        validate_data_types=False,
    )
    assert config.cache.ttl_seconds == 500


def test_add_prefix_to_keywords() -> None:
    config = pyya.init_config(
        config=config_path,
        default_config=default_config_path,
        add_underscore_prefix_to_keywords=True,
        validate_data_types=False,
    )
    assert config.app._class is True


def test_raise_err_non_identifier() -> None:
    with pytest.raises(pyya.PyyaError, match=r'section `prod-env` is not a valid identifier, aborting'):
        _ = pyya.init_config(
            config=config_path,
            default_config=default_config_path,
            raise_error_non_identifiers=True,
            validate_data_types=False,
        )


def test_replace_dashes_with_underscores() -> None:
    config = pyya.init_config(
        config=config_path,
        default_config=default_config_path,
        replace_dashes_with_underscores=True,
        validate_data_types=False,
    )
    assert config.environments.prod_env.logging.level == 'warn'


def test_sections_ignored_on_merge() -> None:
    with pytest.raises(AttributeError, match=r'environments'):
        config = pyya.init_config(
            config=config_path,
            default_config=default_config_path,
            sections_ignored_on_merge=['environments'],
            validate_data_types=False,
        )
        _ = config.environments


def test_validate_data_types() -> None:
    with pytest.raises(pyya.PyyaError, match=r'logging.rotate.enabled'):
        _ = pyya.init_config(config=config_path, default_config=default_config_path)
