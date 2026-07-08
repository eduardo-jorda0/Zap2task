"""Parsing do `_chat.txt` exportado pelo WhatsApp.

O WhatsApp não tem um formato único de exportação: iOS e Android usam
delimitadores diferentes, e o separador de hora pode ser 24h ou 12h (AM/PM).
Por isso o parsing usa uma cascata de padrões regex em vez de um único padrão
rígido — e linhas não reconhecidas são logadas, nunca descartadas em silêncio.
"""

import re
from datetime import datetime

from models.tipos import Mensagem
from utils.logger import get_logger

logger = get_logger(__name__)

# Mensagem normal, com remetente: "[03/07/2026, 09:15:32] João: texto"
_PADRAO_IOS_COM_REMETENTE = re.compile(
    r"^\[(?P<data>\d{1,2}/\d{1,2}/\d{2,4}), "
    r"(?P<hora>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\] "
    r"(?P<remetente>[^:]+): (?P<texto>.*)$"
)
# Mensagem normal, com remetente: "03/07/2026 09:15 - João: texto"
_PADRAO_ANDROID_COM_REMETENTE = re.compile(
    r"^(?P<data>\d{1,2}/\d{1,2}/\d{2,4}) "
    r"(?P<hora>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?) - "
    r"(?P<remetente>[^:]+): (?P<texto>.*)$"
)
# Notificação de sistema, sem remetente: "[03/07/2026, 09:15] Chamada de voz perdida"
_PADRAO_IOS_SISTEMA = re.compile(
    r"^\[(?P<data>\d{1,2}/\d{1,2}/\d{2,4}), "
    r"(?P<hora>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\] (?P<texto>.*)$"
)
# Notificação de sistema, sem remetente: "03/07/2026 09:15 - Chamada de voz perdida"
_PADRAO_ANDROID_SISTEMA = re.compile(
    r"^(?P<data>\d{1,2}/\d{1,2}/\d{2,4}) "
    r"(?P<hora>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?) - (?P<texto>.*)$"
)

# A ordem importa: padrões com remetente (mais específicos) são tentados antes
# dos padrões de sistema (sem remetente), senão toda linha cairia no de sistema.
_PADROES_CASCATA = (
    _PADRAO_IOS_COM_REMETENTE,
    _PADRAO_ANDROID_COM_REMETENTE,
    _PADRAO_IOS_SISTEMA,
    _PADRAO_ANDROID_SISTEMA,
)

_REMETENTE_SISTEMA = "Sistema"

_FORMATOS_DATA = ("%d/%m/%Y", "%d/%m/%y")
_FORMATOS_HORA = ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M%p")

_CARACTERES_INVISIVEIS = ("﻿", "‎", "‏")


def _limpar_linha(linha: str) -> str:
    """Remove BOM e marcadores de direcionalidade invisíveis que o WhatsApp injeta."""
    for caractere in _CARACTERES_INVISIVEIS:
        linha = linha.replace(caractere, "")
    return linha.rstrip()


def _parsear_timestamp(data: str, hora: str) -> datetime | None:
    """Tenta combinar `data` e `hora` usando os formatos conhecidos do WhatsApp."""
    for formato_data in _FORMATOS_DATA:
        for formato_hora in _FORMATOS_HORA:
            try:
                return datetime.strptime(f"{data} {hora}", f"{formato_data} {formato_hora}")
            except ValueError:
                continue
    return None


def parsear_linha(linha: str) -> Mensagem | None:
    """Tenta reconhecer uma linha do `_chat.txt` usando os padrões em cascata.

    Args:
        linha: uma linha já limpa (sem quebra de linha) do arquivo de chat.

    Returns:
        A `Mensagem` reconhecida, ou `None` se nenhum padrão bateu — o que
        normalmente indica uma linha de continuação de mensagem multi-linha.
    """
    for padrao in _PADROES_CASCATA:
        match = padrao.match(linha)
        if not match:
            continue

        grupos = match.groupdict()
        timestamp = _parsear_timestamp(grupos["data"], grupos["hora"])
        if timestamp is None:
            continue

        remetente = grupos.get("remetente", _REMETENTE_SISTEMA).strip()
        return Mensagem(remetente=remetente, timestamp=timestamp, texto=grupos["texto"].strip())

    return None


def parsear_chat(conteudo: str) -> list[Mensagem]:
    """Parseia o conteúdo completo do `_chat.txt` em uma lista de `Mensagem`.

    Linhas que não batem com nenhum padrão conhecido são tratadas como
    continuação da mensagem anterior (comum em mensagens multi-linha do
    WhatsApp). Se não houver mensagem anterior para anexar, a linha é
    registrada como aviso e descartada — nunca descartada em silêncio.

    Args:
        conteudo: texto bruto do `_chat.txt`.

    Returns:
        Lista de mensagens na ordem em que aparecem no arquivo.
    """
    mensagens: list[Mensagem] = []
    linhas_nao_reconhecidas = 0

    for linha_bruta in conteudo.splitlines():
        linha = _limpar_linha(linha_bruta)
        if not linha:
            continue

        mensagem = parsear_linha(linha)
        if mensagem is not None:
            mensagens.append(mensagem)
            continue

        if mensagens:
            mensagens[-1].texto += f"\n{linha}"
        else:
            linhas_nao_reconhecidas += 1
            logger.warning("Linha do chat não reconhecida e sem mensagem anterior: %r", linha)

    if linhas_nao_reconhecidas:
        logger.warning(
            "%d linha(s) do chat não foram reconhecidas por nenhum padrão conhecido.",
            linhas_nao_reconhecidas,
        )

    logger.info("Chat parseado: %d mensagem(ns) extraída(s).", len(mensagens))
    return mensagens
