"""Conversão de áudio para `.mp3` e deduplicação por hash (RF2 + RF3).

Conversão e deduplicação são duas responsabilidades relacionadas, mas a
deduplicação sempre ocorre sobre o `.mp3` já convertido e antes da transcrição
(RF3.4) — do contrário, o pipeline gastaria tempo de CPU/GPU transcrevendo o
mesmo áudio duas vezes.
"""

from datetime import datetime
from pathlib import Path

from models.tipos import Audio, DuplicataRemovida, Falha, ResultadoConversaoDedup
from utils.exceptions import ConversaoAudioError
from utils.ffmpeg import converter_para_mp3
from utils.hash_utils import calcular_hash_arquivo
from utils.logger import get_logger

logger = get_logger(__name__)


def converter_e_deduplicar(audios: list[Audio], destino_conversao: Path) -> ResultadoConversaoDedup:
    """Converte cada áudio para `.mp3` (pulando os que já são) e remove duplicatas por hash.

    Args:
        audios: áudios encontrados pelo ingestor, na extensão original.
        destino_conversao: diretório onde os `.mp3` convertidos serão gravados.

    Returns:
        Áudios únicos, relatório de duplicatas removidas e relatório de falhas
        de conversão. Uma falha em um único arquivo nunca interrompe o
        processamento dos demais (RNF3).
    """
    logger.info("Iniciando conversão e deduplicação de %d áudio(s)", len(audios))
    inicio = datetime.now()
    destino_conversao.mkdir(parents=True, exist_ok=True)

    convertidos: list[Audio] = []
    falhas: list[Falha] = []

    for audio in sorted(audios, key=lambda item: item.data_criacao):
        try:
            audio_mp3 = _obter_ou_converter_mp3(audio, destino_conversao)
        except ConversaoAudioError as erro:
            logger.error("Falha ao converter '%s': %s", audio.nome, erro)
            falhas.append(Falha(arquivo=audio.nome, motivo=str(erro)))
            continue

        audio_mp3.hash = calcular_hash_arquivo(audio_mp3.caminho)
        convertidos.append(audio_mp3)

    audios_unicos, duplicatas_removidas = _remover_duplicatas(convertidos)

    duracao = (datetime.now() - inicio).total_seconds()
    logger.info(
        "Conversão e dedup concluídas em %.2fs — %d único(s), %d duplicata(s), %d falha(s)",
        duracao,
        len(audios_unicos),
        len(duplicatas_removidas),
        len(falhas),
    )

    return ResultadoConversaoDedup(
        audios_unicos=audios_unicos,
        duplicatas_removidas=duplicatas_removidas,
        falhas_conversao=falhas,
    )


def _obter_ou_converter_mp3(audio: Audio, destino: Path) -> Audio:
    """Retorna o `Audio` apontando para o `.mp3`, convertendo apenas se necessário (RF2.4)."""
    if audio.caminho.suffix.lower() == ".mp3":
        return Audio(
            nome=audio.nome,
            caminho=audio.caminho,
            tamanho_bytes=audio.tamanho_bytes,
            data_criacao=audio.data_criacao,
            remetente=audio.remetente,
        )

    caminho_mp3 = destino / f"{audio.caminho.stem}.mp3"
    if not caminho_mp3.exists():
        converter_para_mp3(audio.caminho, caminho_mp3)

    estatisticas = caminho_mp3.stat()
    return Audio(
        nome=caminho_mp3.name,
        caminho=caminho_mp3,
        tamanho_bytes=estatisticas.st_size,
        data_criacao=audio.data_criacao,
        remetente=audio.remetente,
    )


def _remover_duplicatas(audios: list[Audio]) -> tuple[list[Audio], list[DuplicataRemovida]]:
    """Mantém apenas o primeiro áudio de cada hash.

    Como `audios` já chega ordenado do mais antigo para o mais novo (RF3.2),
    o primeiro áudio visto para cada hash é sempre o mais antigo.
    """
    caminho_original_por_hash: dict[str, str] = {}
    unicos: list[Audio] = []
    duplicatas: list[DuplicataRemovida] = []

    for audio in audios:
        original = caminho_original_por_hash.get(audio.hash)
        if original is None:
            caminho_original_por_hash[audio.hash] = audio.nome
            unicos.append(audio)
        else:
            duplicatas.append(DuplicataRemovida(arquivo_removido=audio.nome, duplicata_de=original))

    return unicos, duplicatas
