"""Testes unitários para utils/ffmpeg.py — usam o FFmpeg real para validar a conversão."""

import subprocess
from pathlib import Path

import pytest

import config
from utils.exceptions import ConversaoAudioError
from utils.ffmpeg import converter_para_mp3


@pytest.fixture(autouse=True)
def _pular_se_ffmpeg_indisponivel():
    if not config.ffmpeg_disponivel():
        pytest.skip("FFmpeg não está disponível no PATH desta sessão de testes.")


def _gerar_opus_de_teste(caminho: Path, duracao_segundos: float = 1.0) -> None:
    """Gera um áudio sintético (tom senoidal) em .opus usando o próprio FFmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duracao_segundos}",
            "-c:a", "libopus",
            str(caminho),
        ],
        capture_output=True,
        check=True,
    )


def test_converter_para_mp3_gera_arquivo_valido(tmp_path):
    origem = tmp_path / "tom.opus"
    destino = tmp_path / "tom.mp3"
    _gerar_opus_de_teste(origem)

    converter_para_mp3(origem, destino)

    assert destino.exists()
    assert destino.stat().st_size > 0


def test_converter_para_mp3_usa_taxa_de_amostragem_otimizada_para_fala(tmp_path):
    origem = tmp_path / "tom.opus"
    destino = tmp_path / "tom.mp3"
    _gerar_opus_de_teste(origem)

    converter_para_mp3(origem, destino)

    resultado = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels",
            "-of", "csv=p=0", str(destino),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    taxa_amostragem, canais = resultado.stdout.strip().split(",")

    assert int(taxa_amostragem) == config.FFMPEG_SAMPLE_RATE_HZ
    assert int(canais) == config.FFMPEG_CHANNELS


def test_converter_para_mp3_arquivo_origem_invalido_levanta_erro(tmp_path):
    origem = tmp_path / "nao_e_audio.opus"
    origem.write_bytes(b"isto nao e um audio valido")
    destino = tmp_path / "saida.mp3"

    with pytest.raises(ConversaoAudioError):
        converter_para_mp3(origem, destino)
