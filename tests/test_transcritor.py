"""Testes unitários/integração para modules/transcritor.py.

Os testes de transcrição real usam o modelo "tiny" do Whisper (o menor e mais
rápido) sobre áudios sintéticos gerados pelo próprio FFmpeg, para validar o
pipeline de ponta a ponta sem depender de arquivos de voz reais.
"""

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

import config
from models.tipos import Audio
from modules.transcritor import _calcular_confianca, transcrever_lote


def _whisper_disponivel() -> bool:
    try:
        import whisper  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _whisper_disponivel(), reason="openai-whisper não está instalado neste ambiente."
)


def _gerar_audio_de_teste(caminho: Path, duracao_segundos: float = 1.0) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duracao_segundos}",
            "-ar", str(config.FFMPEG_SAMPLE_RATE_HZ), "-ac", "1",
            str(caminho),
        ],
        capture_output=True,
        check=True,
    )


def test_calcular_confianca_sem_segmentos_retorna_zero():
    assert _calcular_confianca([]) == 0.0


def test_calcular_confianca_deriva_valor_entre_zero_e_um():
    segmentos = [{"avg_logprob": -0.2}, {"avg_logprob": -0.4}]
    confianca = _calcular_confianca(segmentos)
    assert 0.0 < confianca <= 1.0


def test_transcrever_lote_lista_vazia_retorna_resultado_vazio():
    resultado = transcrever_lote([])
    assert resultado.transcricoes == []
    assert resultado.falhas == []


@pytest.mark.skipif(not config.ffmpeg_disponivel(), reason="FFmpeg indisponível para gerar áudio de teste.")
def test_transcrever_lote_processa_audio_valido_e_reporta_progresso(tmp_path):
    caminho_audio = tmp_path / "tom.mp3"
    _gerar_audio_de_teste(caminho_audio)
    audio = Audio(
        nome="tom.mp3", caminho=caminho_audio, tamanho_bytes=1, data_criacao=datetime.now(), remetente="João"
    )

    chamadas_progresso: list[tuple[int, int]] = []

    resultado = transcrever_lote(
        [audio],
        tamanho_modelo="tiny",
        max_workers=1,
        callback_progresso=lambda concluidos, total: chamadas_progresso.append((concluidos, total)),
    )

    assert len(resultado.transcricoes) == 1
    assert resultado.falhas == []
    assert resultado.transcricoes[0].remetente == "João"
    assert 0.0 <= resultado.transcricoes[0].confianca <= 1.0
    assert chamadas_progresso == [(1, 1)]


@pytest.mark.skipif(not config.ffmpeg_disponivel(), reason="FFmpeg indisponível para gerar áudio de teste.")
def test_transcrever_lote_com_varias_threads_nao_corrompe_estado_entre_audios(tmp_path):
    """Regressão: modelo compartilhado entre threads corrompia o KV-cache do Whisper
    (RuntimeError de reshape para tensor de 0 elementos). Cada thread deve ter seu
    próprio modelo (`_obter_modelo_da_thread`), então rodar vários áudios em paralelo
    não pode gerar falhas nem misturar resultados entre eles.
    """
    audios = []
    for indice in range(6):
        caminho_audio = tmp_path / f"tom_{indice}.mp3"
        _gerar_audio_de_teste(caminho_audio, duracao_segundos=0.5)
        audios.append(
            Audio(
                nome=f"tom_{indice}.mp3",
                caminho=caminho_audio,
                tamanho_bytes=1,
                data_criacao=datetime.now(),
                remetente=f"Pessoa {indice}",
            )
        )

    resultado = transcrever_lote(audios, tamanho_modelo="tiny", max_workers=4)

    assert resultado.falhas == []
    assert len(resultado.transcricoes) == 6
    assert {transcricao.nome_arquivo for transcricao in resultado.transcricoes} == {
        f"tom_{i}.mp3" for i in range(6)
    }


def test_transcrever_lote_audio_corrompido_vira_falha_sem_interromper_lote(tmp_path):
    caminho_corrompido = tmp_path / "corrompido.mp3"
    caminho_corrompido.write_bytes(b"nao-e-audio-de-verdade")
    audio_corrompido = Audio(
        nome="corrompido.mp3", caminho=caminho_corrompido, tamanho_bytes=4, data_criacao=datetime.now()
    )

    resultado = transcrever_lote([audio_corrompido], tamanho_modelo="tiny", max_workers=1)

    assert resultado.transcricoes == []
    assert len(resultado.falhas) == 1
    assert resultado.falhas[0].arquivo == "corrompido.mp3"
