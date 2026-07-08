"""Testes unitários para modules/audio_processor.py."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

import config
from models.tipos import Audio
from modules.audio_processor import converter_e_deduplicar


@pytest.fixture(autouse=True)
def _pular_se_ffmpeg_indisponivel():
    if not config.ffmpeg_disponivel():
        pytest.skip("FFmpeg não está disponível no PATH desta sessão de testes.")


def _criar_audio_mp3(tmp_path: Path, nome: str, conteudo: bytes, data_criacao: datetime) -> Audio:
    caminho = tmp_path / nome
    caminho.write_bytes(conteudo)
    return Audio(nome=nome, caminho=caminho, tamanho_bytes=len(conteudo), data_criacao=data_criacao, remetente="João")


def test_converter_e_deduplicar_remove_duplicata_mantendo_o_mais_antigo(tmp_path):
    agora = datetime.now()
    mais_antigo = _criar_audio_mp3(tmp_path, "antigo.mp3", b"conteudo-identico", agora - timedelta(minutes=10))
    mais_novo = _criar_audio_mp3(tmp_path, "novo.mp3", b"conteudo-identico", agora)

    resultado = converter_e_deduplicar([mais_novo, mais_antigo], tmp_path / "convertidos")

    assert len(resultado.audios_unicos) == 1
    assert resultado.audios_unicos[0].nome == "antigo.mp3"
    assert len(resultado.duplicatas_removidas) == 1
    assert resultado.duplicatas_removidas[0].arquivo_removido == "novo.mp3"
    assert resultado.duplicatas_removidas[0].duplicata_de == "antigo.mp3"


def test_converter_e_deduplicar_conteudos_diferentes_nao_sao_duplicatas(tmp_path):
    agora = datetime.now()
    audio_a = _criar_audio_mp3(tmp_path, "a.mp3", b"conteudo-a", agora)
    audio_b = _criar_audio_mp3(tmp_path, "b.mp3", b"conteudo-b", agora)

    resultado = converter_e_deduplicar([audio_a, audio_b], tmp_path / "convertidos")

    assert len(resultado.audios_unicos) == 2
    assert resultado.duplicatas_removidas == []


def test_converter_e_deduplicar_falha_de_conversao_nao_interrompe_o_lote(tmp_path):
    agora = datetime.now()
    caminho_corrompido = tmp_path / "corrompido.opus"
    caminho_corrompido.write_bytes(b"nao-e-audio-de-verdade")
    audio_corrompido = Audio(
        nome="corrompido.opus", caminho=caminho_corrompido, tamanho_bytes=4, data_criacao=agora
    )
    audio_valido = _criar_audio_mp3(tmp_path, "valido.mp3", b"conteudo-valido", agora)

    resultado = converter_e_deduplicar([audio_corrompido, audio_valido], tmp_path / "convertidos")

    assert len(resultado.falhas_conversao) == 1
    assert resultado.falhas_conversao[0].arquivo == "corrompido.opus"
    assert len(resultado.audios_unicos) == 1
    assert resultado.audios_unicos[0].nome == "valido.mp3"


def test_converter_e_deduplicar_pula_conversao_se_ja_e_mp3(tmp_path):
    agora = datetime.now()
    audio = _criar_audio_mp3(tmp_path, "ja_convertido.mp3", b"conteudo-mp3", agora)
    destino_conversao = tmp_path / "convertidos"

    resultado = converter_e_deduplicar([audio], destino_conversao)

    assert len(resultado.audios_unicos) == 1
    assert resultado.audios_unicos[0].caminho == audio.caminho
    assert not any(destino_conversao.iterdir())
