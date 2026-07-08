"""Tipos de domínio compartilhados entre os módulos do pipeline.

Usar dataclasses tipadas em vez de dicts soltos torna os contratos entre
`ingestor`, `audio_processor`, `transcritor`, `timeline_builder` e
`exportador` verificáveis estaticamente e autoexplicativos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


@dataclass
class Mensagem:
    """Uma mensagem de texto extraída do `_chat.txt` do WhatsApp."""

    remetente: str
    timestamp: datetime
    texto: str


@dataclass
class Audio:
    """Um arquivo de áudio de mídia, antes ou depois da conversão/deduplicação.

    O campo `remetente` é preenchido pelo `ingestor` a partir da associação
    already feita pelo WhatsApp no `_chat.txt`, e deve ser propagado sem perdas
    até o `timeline_builder` — é a única fonte confiável de "quem falou".
    """

    nome: str
    caminho: Path
    tamanho_bytes: int
    data_criacao: datetime
    remetente: Optional[str] = None
    hash: Optional[str] = None


@dataclass
class Documento:
    """Um arquivo de mídia não suportado para transcrição (imagem, vídeo, PDF etc.).

    Apenas listado no relatório final, nunca processado (RF1.4).
    """

    nome: str
    caminho: Path
    tipo: str


@dataclass
class DuplicataRemovida:
    """Registro de um áudio descartado por ser duplicata byte-a-byte de outro."""

    arquivo_removido: str
    duplicata_de: str


@dataclass
class Falha:
    """Registro genérico de um arquivo que falhou em alguma etapa do pipeline.

    Reutilizado por conversão e transcrição — o formato do erro (arquivo +
    motivo) é o mesmo, só muda em qual etapa ele ocorreu.
    """

    arquivo: str
    motivo: str


@dataclass
class ResultadoConversaoDedup:
    """Resultado da etapa de conversão + deduplicação (RF2 + RF3)."""

    audios_unicos: list[Audio] = field(default_factory=list)
    duplicatas_removidas: list[DuplicataRemovida] = field(default_factory=list)
    falhas_conversao: list[Falha] = field(default_factory=list)


@dataclass
class Transcricao:
    """Transcrição de um único áudio, com uma métrica de confiança derivada (RF4.5)."""

    nome_arquivo: str
    texto: str
    confianca: float
    remetente: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class ResultadoTranscricao:
    """Resultado da etapa de transcrição em lote (RF4)."""

    transcricoes: list[Transcricao] = field(default_factory=list)
    falhas: list[Falha] = field(default_factory=list)


class TipoItemTimeline(str, Enum):
    """Tipo de um item na timeline final (RF5.4)."""

    TEXTO = "texto"
    AUDIO = "audio"
    DOCUMENTO = "documento"


@dataclass
class TimelineItem:
    """Um item da timeline final, mesclando texto, áudio e documentos em ordem cronológica (RF5)."""

    timestamp: datetime
    remetente: str
    tipo: TipoItemTimeline
    conteudo: str
    confianca: Optional[float] = None
    arquivo_origem: Optional[str] = None


@dataclass
class ResultadoIngestao:
    """Resultado da ingestão de um `.zip` do WhatsApp ou de áudios avulsos.

    `sucesso=False` só ocorre em falhas que impedem qualquer processamento
    (ex.: zip corrompido) — falhas parciais (ex.: `_chat.txt` ausente) ainda
    retornam `sucesso=True` com as listas parcialmente preenchidas.
    """

    sucesso: bool
    mensagens: list[Mensagem] = field(default_factory=list)
    audios: list[Audio] = field(default_factory=list)
    documentos: list[Documento] = field(default_factory=list)
    erro: Optional[str] = None


@dataclass
class Metadados:
    """Metadados de uma execução do pipeline, exibidos no cabeçalho de cada saída (RF6.5)."""

    processado_em: datetime
    total_mensagens_texto: int
    total_audios_transcritos: int
    duplicatas_removidas: int
    modelo_whisper_usado: str


@dataclass
class RelatorioFinal:
    """Pacote completo de dados para exportação (RF6).

    A especificação original tinha `exportar_json` recebendo só a timeline,
    sem `metadados` — mas o próprio exemplo de saída `.json` da spec inclui
    metadados, duplicatas e falhas. Por isso todo exportador recebe este
    mesmo pacote completo, garantindo que `.txt`, `.json` e `.docx` sempre
    tenham as mesmas informações disponíveis.
    """

    metadados: Metadados
    timeline: list[TimelineItem] = field(default_factory=list)
    duplicatas_removidas: list[DuplicataRemovida] = field(default_factory=list)
    falhas_conversao: list[Falha] = field(default_factory=list)
    falhas_transcricao: list[Falha] = field(default_factory=list)
