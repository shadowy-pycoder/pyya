from pathlib import Path

import pytest

import pyya


config_path = Path(__file__).parent / 'testdata/config.toml'
default_config_path = Path(__file__).parent / 'testdata/default.config.toml'


def test_default_setup() -> None:
    config = pyya.init_config(config=config_path, default_config=default_config_path, validate_data_types=False)
    assert config.app.name == 'myapp_changed'
    assert config.app.debug is True
    assert config.app.port == 9091
    assert config.database.password == 'secret_changed'
    assert len(config.database.replicas) == 1
    assert config.logging.level == 'debug'
    assert config.logging.rotate.enabled is False
    assert len(config.cache.servers) == 1


def test_replace_dashes_with_underscores() -> None:
    config = pyya.init_config(
        config=config_path,
        default_config=default_config_path,
        replace_dashes_with_underscores=True,
        validate_data_types=False,
    )
    assert config.logging.rotate.keep_files == 3


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
    with pytest.raises(pyya.PyyaError, match=r'cache.enabled'):
        _ = pyya.init_config(config=config_path, default_config=default_config_path)
