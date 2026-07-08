"""Transcrição de áudio com Whisper, em paralelo (RF4).

Cada thread do `ThreadPoolExecutor` carrega e mantém sua PRÓPRIA instância do
modelo Whisper (via `threading.local`), em vez de compartilhar uma única
instância entre threads. Isso não é sobre o GIL — é porque o `openai-whisper`
guarda o cache de atenção (KV-cache) da decodificação como estado mutável
dentro do próprio objeto `nn.Module`, usando hooks do PyTorch. Se duas threads
chamarem `.transcribe()` ao mesmo tempo no mesmo objeto, esse estado se
corrompe: o sintoma típico é um erro de reshape para um tensor de 0 elementos
no meio da decodificação, e em casos mais graves isso deixa o processo Python
inteiro instável. Cada thread com seu próprio modelo elimina o
compartilhamento de estado e resolve o problema pela raiz.

Em GPU, chamadas concorrentes de várias threads sobre o mesmo contexto CUDA
também não são seguras nem trazem ganho — por isso o número de workers é
forçado a 1 quando uma GPU é detectada.
"""

import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Optional

import torch
import whisper

import config
from models.tipos import Audio, Falha, ResultadoTranscricao, Transcricao
from utils.exceptions import TranscricaoError
from utils.logger import get_logger

logger = get_logger(__name__)

CallbackProgresso = Callable[[int, int], None]

_estado_da_thread = threading.local()


def _obter_modelo_da_thread(tamanho_modelo: str) -> "whisper.Whisper":
    """Retorna o modelo Whisper da thread atual, carregando-o na primeira chamada.

    Cada thread do pool carrega seu próprio modelo uma única vez e o reutiliza
    nas chamadas seguintes que caírem na mesma thread — evita tanto o
    compartilhamento inseguro de estado quanto o custo de recarregar o modelo
    a cada áudio.
    """
    modelo_atual = getattr(_estado_da_thread, "modelo", None)
    if modelo_atual is None or getattr(_estado_da_thread, "tamanho_modelo", None) != tamanho_modelo:
        modelo_atual = whisper.load_model(tamanho_modelo)
        _estado_da_thread.modelo = modelo_atual
        _estado_da_thread.tamanho_modelo = tamanho_modelo
    return modelo_atual


def transcrever_lote(
    audios: list[Audio],
    tamanho_modelo: str = config.DEFAULT_WHISPER_MODEL,
    idioma: str = config.DEFAULT_LANGUAGE,
    max_workers: int = config.DEFAULT_THREADS,
    callback_progresso: Optional[CallbackProgresso] = None,
) -> ResultadoTranscricao:
    """Transcreve todos os áudios únicos (pós-deduplicação) em paralelo.

    Args:
        audios: áudios já convertidos e deduplicados.
        tamanho_modelo: um de `config.WHISPER_MODEL_OPTIONS` ("tiny".."medium").
        idioma: código de idioma para o Whisper (ex.: "pt").
        max_workers: número de threads (1 a `config.MAX_THREADS`); forçado a 1
            se uma GPU for detectada (ver docstring do módulo).
        callback_progresso: chamado como `callback(concluidos, total)` após
            cada áudio, para alimentar a barra de progresso da UI (RF4.7).

    Returns:
        Transcrições bem-sucedidas e relatório de falhas. Uma falha em um
        único áudio nunca interrompe o restante do lote (RF4.6, RNF3).
    """
    if not audios:
        return ResultadoTranscricao()

    workers_efetivos = _calcular_workers_efetivos(max_workers)
    logger.info(
        "Iniciando transcrição de %d áudio(s) — modelo=%s, idioma=%s, workers=%d",
        len(audios), tamanho_modelo, idioma, workers_efetivos,
    )
    inicio = datetime.now()

    transcricoes: list[Transcricao] = []
    falhas: list[Falha] = []
    concluidos = 0

    with ThreadPoolExecutor(max_workers=workers_efetivos) as executor:
        futuros = {
            executor.submit(_transcrever_um, tamanho_modelo, audio, idioma): audio for audio in audios
        }

        for futuro in as_completed(futuros):
            audio = futuros[futuro]
            concluidos += 1

            try:
                transcricoes.append(futuro.result())
            except TranscricaoError as erro:
                logger.error("Falha ao transcrever '%s': %s", audio.nome, erro)
                falhas.append(Falha(arquivo=audio.nome, motivo=str(erro)))

            if callback_progresso is not None:
                callback_progresso(concluidos, len(audios))

    duracao = (datetime.now() - inicio).total_seconds()
    logger.info(
        "Transcrição concluída em %.2fs — %d sucesso(s), %d falha(s)",
        duracao, len(transcricoes), len(falhas),
    )

    return ResultadoTranscricao(transcricoes=transcricoes, falhas=falhas)


def _calcular_workers_efetivos(max_workers: int) -> int:
    """Aplica os limites de RNF5 e força 1 worker se uma GPU for detectada.

    Chamadas concorrentes de múltiplas threads Python sobre o mesmo contexto
    CUDA não são seguras nem trazem ganho real de performance — o Whisper em
    GPU já processa cada áudio rapidamente sozinho, então paralelizar por
    thread arriscaria contenção ou erros na GPU sem benefício real.
    """
    workers = max(config.MIN_THREADS, min(max_workers, config.MAX_THREADS))
    if torch.cuda.is_available() and workers > 1:
        logger.warning(
            "GPU detectada — forçando max_workers=1 (era %d) para evitar concorrência insegura na GPU.",
            workers,
        )
        return 1
    return workers


def _transcrever_um(tamanho_modelo: str, audio: Audio, idioma: str) -> Transcricao:
    """Transcreve um único áudio e deriva uma métrica de confiança.

    Usa o modelo Whisper da thread atual (`_obter_modelo_da_thread`), nunca
    uma instância compartilhada entre threads — ver docstring do módulo.

    Raises:
        TranscricaoError: se o Whisper falhar (arquivo corrompido, formato não
            suportado, etc.) — capturado pelo chamador por item (RF4.6).
    """
    try:
        modelo = _obter_modelo_da_thread(tamanho_modelo)
        resultado = modelo.transcribe(str(audio.caminho), language=idioma, fp16=torch.cuda.is_available())
    except Exception as erro:  # noqa: BLE001 — Whisper não documenta exceções específicas
        raise TranscricaoError(f"Whisper falhou para '{audio.nome}': {erro}") from erro

    return Transcricao(
        nome_arquivo=audio.nome,
        texto=resultado.get("text", "").strip(),
        confianca=_calcular_confianca(resultado.get("segments", [])),
        remetente=audio.remetente,
        timestamp=audio.data_criacao,
    )


def _calcular_confianca(segmentos: list[dict]) -> float:
    """Deriva uma confiança 0-1 a partir do `avg_logprob` dos segmentos.

    O `openai-whisper` não expõe um campo `confidence` pronto — apenas
    `avg_logprob` (log-probabilidade média por token, valor negativo) e
    `no_speech_prob` por segmento. `exp(avg_logprob)` é a média geométrica das
    probabilidades por token: uma aproximação razoável de confiança (RF4.5).
    """
    if not segmentos:
        return 0.0

    media_log_prob = sum(segmento["avg_logprob"] for segmento in segmentos) / len(segmentos)
    return round(min(1.0, math.exp(media_log_prob)), 4)
