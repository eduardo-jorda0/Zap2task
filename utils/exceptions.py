"""Exceções customizadas do Zap2Task Audio Engine.

Usar tipos específicos (em vez de `except Exception` genérico) permite que o
pipeline distinga falhas recuperáveis por item (ex.: um áudio corrompido) de
falhas de ambiente que devem interromper a execução (ex.: FFmpeg ausente).
"""


class Zap2TaskError(Exception):
    """Exceção base para todos os erros conhecidos do Zap2Task Audio Engine."""


class FFmpegNaoEncontradoError(Zap2TaskError):
    """Levantada quando o executável do FFmpeg não está disponível no PATH."""


class ZipCorrompidoError(Zap2TaskError):
    """Levantada quando o arquivo .zip enviado está corrompido ou ilegível."""


class ChatParsingError(Zap2TaskError):
    """Levantada quando nenhum padrão de regex conhecido reconhece uma linha do _chat.txt."""


class ConversaoAudioError(Zap2TaskError):
    """Levantada quando a conversão de um áudio para .mp3 falha."""


class TranscricaoError(Zap2TaskError):
    """Levantada quando a transcrição de um áudio falha."""
