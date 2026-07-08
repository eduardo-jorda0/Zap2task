"""Testes unitários para modules/timeline_builder.py."""

import os
from datetime import datetime
from pathlib import Path

from models.tipos import Documento, Mensagem, TipoItemTimeline, Transcricao
from modules.timeline_builder import construir_timeline


def test_construir_timeline_mescla_e_ordena_por_timestamp():
    mensagens = [
        Mensagem(remetente="João", timestamp=datetime(2026, 7, 3, 9, 15), texto="Bom dia!"),
        Mensagem(remetente="João", timestamp=datetime(2026, 7, 3, 9, 45), texto="Perfeito, aguardo."),
    ]
    transcricoes = [
        Transcricao(
            nome_arquivo="PTT-20260703-WA0001.mp3",
            texto="Bom dia João, pode ser sim.",
            confianca=0.92,
            remetente="Você",
            timestamp=datetime(2026, 7, 3, 9, 17),
        )
    ]

    timeline = construir_timeline(mensagens, transcricoes, documentos=[])

    assert [item.conteudo for item in timeline] == [
        "Bom dia!",
        "Bom dia João, pode ser sim.",
        "Perfeito, aguardo.",
    ]
    assert timeline[1].tipo == TipoItemTimeline.AUDIO
    assert timeline[1].confianca == 0.92
    assert timeline[1].arquivo_origem == "PTT-20260703-WA0001.mp3"


def test_construir_timeline_inclui_documentos_com_timestamp_do_arquivo(tmp_path):
    caminho_documento = tmp_path / "foto.jpg"
    caminho_documento.write_bytes(b"fake-image")
    timestamp_esperado = datetime(2026, 7, 3, 10, 0, 0)
    ts = timestamp_esperado.timestamp()
    os.utime(caminho_documento, (ts, ts))

    documentos = [Documento(nome="foto.jpg", caminho=caminho_documento, tipo="jpg")]

    timeline = construir_timeline(mensagens=[], transcricoes=[], documentos=documentos)

    assert len(timeline) == 1
    assert timeline[0].tipo == TipoItemTimeline.DOCUMENTO
    assert timeline[0].timestamp == timestamp_esperado
    assert timeline[0].conteudo == "[Documento: foto.jpg]"


def test_construir_timeline_vazia_retorna_lista_vazia():
    assert construir_timeline([], [], []) == []


def test_construir_timeline_transcricao_sem_timestamp_nao_quebra_ordenacao():
    mensagens = [Mensagem(remetente="João", timestamp=datetime(2026, 7, 3, 9, 15), texto="oi")]
    transcricoes = [
        Transcricao(nome_arquivo="sem_timestamp.mp3", texto="transcrição órfã", confianca=0.5, timestamp=None)
    ]

    timeline = construir_timeline(mensagens, transcricoes, documentos=[])

    assert len(timeline) == 2
    assert timeline[0].conteudo == "transcrição órfã"
