"""Encapsula chamadas ao FFmpeg via subprocess.

Isola toda a interação com o binário externo neste módulo, para que o resto
do pipeline nunca precise lidar com `subprocess.CalledProcessError`, timeouts
ou parsing de stderr diretamente — apenas com `ConversaoAudioError`.
"""

import shutil
import subprocess
from pathlib import Path

import config
from utils.exceptions import ConversaoAudioError
from utils.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT_SEGUNDOS = 300


def converter_para_mp3(origem: Path, destino: Path) -> None:
    """Converte um arquivo de áudio para `.mp3` em 16kHz mono, otimizado para fala.

    Args:
        origem: caminho do arquivo de áudio original (ex.: `.opus`).
        destino: caminho onde o `.mp3` resultante será gravado.

    Raises:
        ConversaoAudioError: se o FFmpeg não estiver no PATH, retornar erro,
            ou travar além do timeout.
    """
    caminho_ffmpeg = shutil.which("ffmpeg")
    if caminho_ffmpeg is None:
        raise ConversaoAudioError("FFmpeg não encontrado no PATH ao tentar converter '{}'.".format(origem.name))

    comando = [
        caminho_ffmpeg,
        "-y",
        "-i", str(origem),
        "-ar", str(config.FFMPEG_SAMPLE_RATE_HZ),
        "-ac", str(config.FFMPEG_CHANNELS),
        str(destino),
    ]

    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            timeout=_TIMEOUT_SEGUNDOS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as erro:
        raise ConversaoAudioError(f"Falha ao executar FFmpeg para '{origem.name}': {erro}") from erro

    if resultado.returncode != 0:
        stderr = resultado.stderr.decode("utf-8", errors="replace").strip()
        raise ConversaoAudioError(
            f"FFmpeg falhou para '{origem.name}' (código {resultado.returncode}): {stderr[-500:]}"
        )

    logger.info("Convertido: %s -> %s", origem.name, destino.name)
