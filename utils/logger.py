"""Logging estruturado do Zap2Task Audio Engine.

Todo o pipeline deve usar `get_logger` em vez de `print()`, para que início de
etapas, tempo gasto, contagens e erros fiquem registrados de forma consistente
em console e em arquivo.
"""

import logging
import sys

import config

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_loggers_configurados: dict[str, logging.Logger] = {}


def get_logger(nome: str) -> logging.Logger:
    """Retorna um logger configurado com saída simultânea em console e arquivo.

    Chamadas repetidas com o mesmo `nome` retornam a mesma instância, evitando
    handlers duplicados (e, portanto, linhas de log duplicadas).

    Args:
        nome: identificador do logger, tipicamente `__name__` do módulo chamador.

    Returns:
        Logger pronto para uso, já configurado.
    """
    if nome in _loggers_configurados:
        return _loggers_configurados[nome]

    config.ensure_directories()

    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(
        config.LOGS_DIR / "zap2task.log", encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _loggers_configurados[nome] = logger
    return logger
