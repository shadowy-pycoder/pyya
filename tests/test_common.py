from pathlib import Path

import pytest

import pyya


config_path = Path(__file__).parent / 'testdata/config.yaml'
default_config_path = Path(__file__).parent / 'testdata/default.config.yaml'
config_wrong_ext = Path(__file__).parent / 'testdata/config.txt'
config_corrupted = Path(__file__).parent / 'testdata/corrupted.yaml'
config_extra = Path(__file__).parent / 'testdata/extra.yaml'
default_config_extra = Path(__file__).parent / 'testdata/default_extra.yaml'
config_stub = Path(__file__).parent / 'testdata/config.pyi'


def test_raise_err_default_file_not_found() -> None:
    with pytest.raises(pyya.PyyaError, match=r'missing.yaml file is missing or empty'):
        _ = pyya.init_config(
            config=config_path,
            default_config='missing.yaml',
        )


def test_raise_err_wrong_ext() -> None:
    with pytest.raises(pyya.PyyaError, match=r'config.txt file format is not supported'):
        _ = pyya.init_config(
            config=config_wrong_ext,
            default_config=default_config_path,
        )


def test_raise_err_default_wrong_ext() -> None:
    with pytest.raises(pyya.PyyaError, match=r'config.txt file format is not supported'):
        _ = pyya.init_config(
            config=config_path,
            default_config=config_wrong_ext,
        )


def test_raise_err_corrupted() -> None:
    with pytest.raises(pyya.PyyaError, match=r'corrupted.yaml file is corrupted'):
        _ = pyya.init_config(
            config=config_corrupted,
            default_config=default_config_path,
        )


def test_raise_err_default_corrupted() -> None:
    with pytest.raises(pyya.PyyaError, match=r'corrupted.yaml file is corrupted'):
        _ = pyya.init_config(
            config=config_path,
            default_config=config_corrupted,
        )


def test_no_error_config_not_found() -> None:
    _ = pyya.init_config(config='missing.yaml', default_config=default_config_path)


def test_raise_err_extra_sections() -> None:
    with pytest.raises(pyya.PyyaError, match=r'Extra inputs are not permitted'):
        _ = pyya.init_config(
            config=config_extra,
            default_config=default_config_extra,
            allow_extra_sections=False,
        )


def test_raise_err_extra_sections_access() -> None:
    with pytest.raises(AttributeError, match=r'garbage'):
        config = pyya.init_config(
            config=config_extra,
            default_config=default_config_extra,
        )
        _ = config.database.garbage


def test_generate_stub() -> None:
    assert not config_stub.exists()
    _ = pyya.init_config(
        config=config_stub,
        default_config=default_config_path,
        _generate_stub=True,  # this private argument is used by CLI tool
    )
    assert config_stub.exists()
    config_stub.unlink()


def test_generate_stub_exist() -> None:
    _ = pyya.init_config(
        config=config_stub,
        default_config=default_config_path,
        _generate_stub=True,
    )
    # NOTE: it would be better to use fixture here
    try:
        _ = pyya.init_config(
            config=config_stub,
            default_config=default_config_path,
            _generate_stub=True,
        )
    except pyya.PyyaError:
        pass
    except Exception:
        pytest.fail(reason='Wrong type of exception')
    else:
        pytest.fail(reason="Exception wasn't raised")
    finally:
        config_stub.unlink(missing_ok=True)
