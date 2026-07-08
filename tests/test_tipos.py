"""Testes unitários para models/tipos.py."""

from datetime import datetime
from pathlib import Path

from models.tipos import Audio, Documento, Mensagem


def test_mensagem_criacao():
    mensagem = Mensagem(remetente="João", timestamp=datetime(2026, 7, 3, 9, 15), texto="Bom dia!")
    assert mensagem.remetente == "João"
    assert mensagem.texto == "Bom dia!"


def test_audio_criacao_com_remetente_opcional():
    audio = Audio(
        nome="PTT-20260703-WA0001.opus",
        caminho=Path("temp/PTT-20260703-WA0001.opus"),
        tamanho_bytes=1024,
        data_criacao=datetime(2026, 7, 3, 9, 17),
    )
    assert audio.remetente is None
    assert audio.hash is None

    audio.remetente = "João"
    assert audio.remetente == "João"


def test_documento_criacao():
    documento = Documento(nome="foto.jpg", caminho=Path("temp/foto.jpg"), tipo="imagem")
    assert documento.tipo == "imagem"
