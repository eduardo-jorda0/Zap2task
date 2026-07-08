"""Testes unitários para modules/ingestor.py."""

import os
import zipfile
from datetime import date, datetime
from pathlib import Path

from modules.ingestor import _extrair_data_do_nome, processar_audios_avulsos, processar_zip

_CONTEUDO_CHAT = "\n".join(
    [
        "03/07/2026 09:15 - João: Bom dia! Vamos revisar o contrato hoje?",
        "03/07/2026 09:17 - Você: PTT-20260703-WA0001.opus (arquivo anexado)",
        "03/07/2026 09:45 - João: Perfeito, aguardo.",
        "03/07/2026 10:00 - João: foto.jpg (arquivo anexado)",
    ]
)


def _criar_zip_de_teste(caminho_zip: Path) -> None:
    with zipfile.ZipFile(caminho_zip, "w") as arquivo_zip:
        arquivo_zip.writestr("_chat.txt", _CONTEUDO_CHAT)
        arquivo_zip.writestr("PTT-20260703-WA0001.opus", b"conteudo-de-audio-fake")
        arquivo_zip.writestr("foto.jpg", b"conteudo-de-imagem-fake")


def test_processar_zip_classifica_mensagens_audios_e_documentos(tmp_path):
    caminho_zip = tmp_path / "conversa.zip"
    destino = tmp_path / "extraido"
    _criar_zip_de_teste(caminho_zip)

    resultado = processar_zip(caminho_zip, destino)

    assert resultado.sucesso is True
    # As duas linhas "(arquivo anexado)" não viram mensagens de texto — só servem
    # para associar o remetente ao áudio/documento correspondente.
    assert len(resultado.mensagens) == 2
    assert all("(arquivo anexado)" not in mensagem.texto for mensagem in resultado.mensagens)
    assert len(resultado.audios) == 1
    assert len(resultado.documentos) == 1

    audio = resultado.audios[0]
    assert audio.nome == "PTT-20260703-WA0001.opus"
    assert audio.remetente == "Você"

    documento = resultado.documentos[0]
    assert documento.nome == "foto.jpg"
    assert documento.tipo == "jpg"


def test_processar_zip_corrompido_retorna_sucesso_falso(tmp_path):
    caminho_zip = tmp_path / "corrompido.zip"
    caminho_zip.write_bytes(b"isso nao e um zip valido")
    destino = tmp_path / "extraido"

    resultado = processar_zip(caminho_zip, destino)

    assert resultado.sucesso is False
    assert resultado.erro is not None


def test_processar_zip_truncado_retorna_sucesso_falso_sem_lancar_excecao(tmp_path):
    """Zip com diretório central válido mas dados locais truncados (ex.: upload cortado no meio)."""
    caminho_zip_original = tmp_path / "original.zip"
    _criar_zip_de_teste(caminho_zip_original)

    bytes_originais = caminho_zip_original.read_bytes()
    caminho_zip_truncado = tmp_path / "truncado.zip"
    caminho_zip_truncado.write_bytes(bytes_originais[: len(bytes_originais) // 2])

    resultado = processar_zip(caminho_zip_truncado, tmp_path / "extraido")

    assert resultado.sucesso is False
    assert resultado.erro is not None


def test_processar_zip_sem_chat_processa_apenas_midia(tmp_path):
    caminho_zip = tmp_path / "sem_chat.zip"
    with zipfile.ZipFile(caminho_zip, "w") as arquivo_zip:
        arquivo_zip.writestr("PTT-20260703-WA0002.mp3", b"audio-sem-chat")
    destino = tmp_path / "extraido"

    resultado = processar_zip(caminho_zip, destino)

    assert resultado.sucesso is True
    assert resultado.mensagens == []
    assert len(resultado.audios) == 1


def test_processar_audios_avulsos_sem_zip(tmp_path):
    caminho_audio = tmp_path / "audio_solto.mp3"
    caminho_audio.write_bytes(b"audio-avulso")

    resultado = processar_audios_avulsos([caminho_audio])

    assert resultado.sucesso is True
    assert resultado.mensagens == []
    assert len(resultado.audios) == 1
    assert resultado.audios[0].nome == "audio_solto.mp3"


def test_extrair_data_do_nome_reconhece_padrao_ptt():
    assert _extrair_data_do_nome("PTT-20260703-WA0001.opus") == date(2026, 7, 3)


def test_extrair_data_do_nome_retorna_none_para_nome_sem_padrao():
    assert _extrair_data_do_nome("a1b2c3d4-uuid-sem-padrao.opus") is None


def test_criar_audio_usa_st_mtime_mesmo_quando_diverge_do_nome(tmp_path):
    caminho_audio = tmp_path / "PTT-20260101-WA0001.mp3"
    caminho_audio.write_bytes(b"audio-avulso")

    data_mtime_esperada = datetime(2026, 7, 3, 9, 17, 0)
    timestamp = data_mtime_esperada.timestamp()
    os.utime(caminho_audio, (timestamp, timestamp))

    resultado = processar_audios_avulsos([caminho_audio])

    assert resultado.audios[0].data_criacao == data_mtime_esperada
