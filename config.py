"""Configuração central do Zap2Task Audio Engine.

Concentra caminhos, valores padrão e validações de ambiente para que nenhum
módulo do pipeline precise hardcodar diretórios ou limites.
"""

import shutil
from pathlib import Path
from typing import Final

from utils.exceptions import FFmpegNaoEncontradoError

BASE_DIR: Final[Path] = Path(__file__).resolve().parent
TEMP_DIR: Final[Path] = BASE_DIR / "temp"
OUTPUTS_DIR: Final[Path] = BASE_DIR / "outputs"
LOGS_DIR: Final[Path] = BASE_DIR / "logs"

WHISPER_MODEL_OPTIONS: Final[tuple[str, ...]] = ("tiny", "base", "small", "medium")
DEFAULT_WHISPER_MODEL: Final[str] = "base"

MIN_THREADS: Final[int] = 1
MAX_THREADS: Final[int] = 16
DEFAULT_THREADS: Final[int] = 4

DEFAULT_LANGUAGE: Final[str] = "pt"

LIMIAR_CONFIANCA_BAIXA: Final[float] = 0.8

FFMPEG_SAMPLE_RATE_HZ: Final[int] = 16_000
FFMPEG_CHANNELS: Final[int] = 1

MAX_UPLOAD_SIZE_MB: Final[int] = 500
MAX_AUDIO_DURATION_MINUTES: Final[int] = 10

SUPPORTED_AUDIO_EXTENSIONS: Final[tuple[str, ...]] = (".opus", ".mp3", ".m4a", ".wav")


def ensure_directories() -> None:
    """Cria os diretórios de trabalho (temp, outputs, logs) caso não existam."""
    for directory in (TEMP_DIR, OUTPUTS_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def ffmpeg_disponivel() -> bool:
    """Verifica se o executável do FFmpeg está acessível no PATH do sistema."""
    return shutil.which("ffmpeg") is not None


def validar_ambiente() -> None:
    """Valida pré-requisitos de sistema antes de iniciar o pipeline.

    Levanta:
        FFmpegNaoEncontradoError: se o FFmpeg não estiver disponível no PATH.
    """
    if not ffmpeg_disponivel():
        raise FFmpegNaoEncontradoError(
            "FFmpeg não encontrado no PATH. Instale o FFmpeg e garanta que o "
            "comando 'ffmpeg' esteja acessível no terminal antes de executar "
            "o Zap2Task Audio Engine."
        )
