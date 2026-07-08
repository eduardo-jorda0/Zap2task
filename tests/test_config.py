"""Testes unitários para config.py."""

import config
from utils.exceptions import FFmpegNaoEncontradoError


def test_ensure_directories_creates_expected_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")

    config.ensure_directories()

    assert (tmp_path / "temp").is_dir()
    assert (tmp_path / "outputs").is_dir()
    assert (tmp_path / "logs").is_dir()


def test_ffmpeg_disponivel_returns_bool():
    assert isinstance(config.ffmpeg_disponivel(), bool)


def test_validar_ambiente_raises_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(config, "ffmpeg_disponivel", lambda: False)

    try:
        config.validar_ambiente()
        assert False, "deveria ter levantado FFmpegNaoEncontradoError"
    except FFmpegNaoEncontradoError:
        pass


def test_validar_ambiente_passes_when_ffmpeg_present(monkeypatch):
    monkeypatch.setattr(config, "ffmpeg_disponivel", lambda: True)
    config.validar_ambiente()
