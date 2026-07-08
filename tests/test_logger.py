"""Testes unitários para utils/logger.py."""

import config
from utils.logger import get_logger


def test_get_logger_returns_same_instance_for_same_name():
    logger_a = get_logger("teste_singleton")
    logger_b = get_logger("teste_singleton")
    assert logger_a is logger_b


def test_get_logger_writes_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)

    logger = get_logger("teste_arquivo_unico")
    logger.info("mensagem de teste")

    log_file = tmp_path / "zap2task.log"
    assert log_file.exists()
    assert "mensagem de teste" in log_file.read_text(encoding="utf-8")
