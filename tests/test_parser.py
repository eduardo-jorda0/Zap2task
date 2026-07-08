"""Testes unitários para utils/parser.py."""

from datetime import datetime

from utils.parser import parsear_chat, parsear_linha


def test_parsear_linha_formato_ios():
    mensagem = parsear_linha("[03/07/2026, 09:15:32] João: Bom dia! Vamos revisar o contrato hoje?")
    assert mensagem is not None
    assert mensagem.remetente == "João"
    assert mensagem.texto == "Bom dia! Vamos revisar o contrato hoje?"
    assert mensagem.timestamp == datetime(2026, 7, 3, 9, 15, 32)


def test_parsear_linha_formato_android_24h():
    mensagem = parsear_linha("03/07/2026 09:15 - João: Perfeito, aguardo.")
    assert mensagem is not None
    assert mensagem.remetente == "João"
    assert mensagem.timestamp == datetime(2026, 7, 3, 9, 15)


def test_parsear_linha_formato_android_12h_am_pm():
    mensagem = parsear_linha("03/07/2026 9:15 PM - João: Boa noite")
    assert mensagem is not None
    assert mensagem.timestamp == datetime(2026, 7, 3, 21, 15)


def test_parsear_linha_notificacao_de_sistema_sem_remetente():
    mensagem = parsear_linha("03/07/2026 09:20 - Chamada de voz perdida.")
    assert mensagem is not None
    assert mensagem.remetente == "Sistema"
    assert mensagem.texto == "Chamada de voz perdida."


def test_parsear_linha_nao_reconhecida_retorna_none():
    assert parsear_linha("isso não é uma linha de chat válida") is None


def test_parsear_chat_mensagem_multilinha_e_anexada_a_anterior():
    conteudo = "\n".join(
        [
            "03/07/2026 09:15 - João: primeira linha",
            "segunda linha da mesma mensagem",
            "03/07/2026 09:17 - Você: outra mensagem",
        ]
    )
    mensagens = parsear_chat(conteudo)
    assert len(mensagens) == 2
    assert mensagens[0].texto == "primeira linha\nsegunda linha da mesma mensagem"


def test_parsear_chat_linha_nao_reconhecida_sem_mensagem_anterior_e_descartada():
    conteudo = "linha de lixo sem timestamp\n03/07/2026 09:15 - João: mensagem válida"
    mensagens = parsear_chat(conteudo)
    assert len(mensagens) == 1
    assert mensagens[0].texto == "mensagem válida"


def test_parsear_chat_remove_bom_e_marcadores_invisiveis():
    conteudo = "﻿‎[03/07/2026, 09:15:00] João: mensagem com bom"
    mensagens = parsear_chat(conteudo)
    assert len(mensagens) == 1
    assert mensagens[0].remetente == "João"
