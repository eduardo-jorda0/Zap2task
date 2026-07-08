"""Merge de mensagens, transcrições e documentos em uma timeline única (RF5).

Responsabilidade única: combinar as três fontes de dados do pipeline em uma
lista ordenada cronologicamente, sem processar ou interpretar conteúdo — é a
última etapa antes da exportação.
"""

from datetime import datetime

from models.tipos import Documento, Mensagem, TimelineItem, TipoItemTimeline, Transcricao
from utils.logger import get_logger

logger = get_logger(__name__)

_REMETENTE_DESCONHECIDO = "Desconhecido"


def construir_timeline(
    mensagens: list[Mensagem],
    transcricoes: list[Transcricao],
    documentos: list[Documento],
) -> list[TimelineItem]:
    """Mescla mensagens de texto, transcrições de áudio e documentos, ordenados por timestamp.

    Args:
        mensagens: mensagens de texto extraídas do `_chat.txt`.
        transcricoes: transcrições de áudio, já com timestamp herdado do `Audio` original.
        documentos: arquivos de mídia não processados (imagens, vídeos etc.) — RF1.4.

    Returns:
        Lista de `TimelineItem` ordenada cronologicamente (RF5.3), cada item
        marcado com seu tipo e remetente quando disponível (RF5.4).
    """
    itens: list[TimelineItem] = [_item_de_mensagem(mensagem) for mensagem in mensagens]
    itens += [_item_de_transcricao(transcricao) for transcricao in transcricoes]
    itens += [_item_de_documento(documento) for documento in documentos]

    itens.sort(key=lambda item: item.timestamp)

    logger.info(
        "Timeline construída com %d item(ns): %d texto, %d áudio, %d documento.",
        len(itens), len(mensagens), len(transcricoes), len(documentos),
    )
    return itens


def _item_de_mensagem(mensagem: Mensagem) -> TimelineItem:
    return TimelineItem(
        timestamp=mensagem.timestamp,
        remetente=mensagem.remetente,
        tipo=TipoItemTimeline.TEXTO,
        conteudo=mensagem.texto,
    )


def _item_de_transcricao(transcricao: Transcricao) -> TimelineItem:
    timestamp = transcricao.timestamp
    if timestamp is None:
        logger.warning(
            "Transcrição de '%s' sem timestamp — usando o mínimo para ordenação.", transcricao.nome_arquivo
        )
        timestamp = datetime.min

    return TimelineItem(
        timestamp=timestamp,
        remetente=transcricao.remetente or _REMETENTE_DESCONHECIDO,
        tipo=TipoItemTimeline.AUDIO,
        conteudo=transcricao.texto,
        confianca=transcricao.confianca,
        arquivo_origem=transcricao.nome_arquivo,
    )


def _item_de_documento(documento: Documento) -> TimelineItem:
    """Cria um item de timeline para um documento não processado (RF1.4).

    O timestamp vem do `st_mtime` do arquivo em disco — não há remetente
    disponível, pois documentos não passam pela associação feita em
    `ingestor._mapear_remetentes_de_midia` (essa só cobre áudios).
    """
    timestamp = datetime.fromtimestamp(documento.caminho.stat().st_mtime)
    return TimelineItem(
        timestamp=timestamp,
        remetente=_REMETENTE_DESCONHECIDO,
        tipo=TipoItemTimeline.DOCUMENTO,
        conteudo=f"[Documento: {documento.nome}]",
        arquivo_origem=documento.nome,
    )
