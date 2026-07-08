"""Ingestão de dados: extrai um `.zip` do WhatsApp ou recebe áudios avulsos.

Responsabilidade única: transformar a entrada bruta do usuário (zip ou lista
de arquivos) em mensagens, áudios e documentos tipados, prontos para os
módulos seguintes do pipeline (RF1).
"""

import os
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

import config
from models.tipos import Audio, Documento, Mensagem, ResultadoIngestao
from utils.exceptions import ZipCorrompidoError
from utils.logger import get_logger
from utils.parser import parsear_chat

logger = get_logger(__name__)

_NOME_ARQUIVO_CHAT = "_chat.txt"
_MARCADORES_ANEXO = ("(arquivo anexado)", "(file attached)")
_PADRAO_NOME_PTT = re.compile(r"PTT-(?P<ano>\d{4})(?P<mes>\d{2})(?P<dia>\d{2})-WA\d+")


def processar_zip(caminho_zip: Path, destino_extracao: Path) -> ResultadoIngestao:
    """Extrai um `.zip` de exportação do WhatsApp e classifica seu conteúdo.

    Args:
        caminho_zip: caminho do arquivo `.zip` enviado pelo usuário.
        destino_extracao: diretório onde os arquivos serão extraídos.

    Returns:
        `ResultadoIngestao` com mensagens, áudios e documentos encontrados.
        Em caso de zip corrompido, `sucesso=False` e `erro` preenchido — o
        restante do pipeline não deve ser executado nesse caso.
    """
    logger.info("Iniciando extração do zip: %s", caminho_zip)
    inicio = datetime.now()

    try:
        _extrair_zip_preservando_mtime(caminho_zip, destino_extracao)
    except ZipCorrompidoError as erro:
        logger.error("Zip corrompido: %s", erro)
        return ResultadoIngestao(sucesso=False, erro=str(erro))

    arquivos_extraidos = [caminho for caminho in destino_extracao.rglob("*") if caminho.is_file()]
    resultado = _classificar_arquivos(arquivos_extraidos)

    duracao = (datetime.now() - inicio).total_seconds()
    logger.info(
        "Extração concluída em %.2fs — %d mensagem(ns), %d áudio(s), %d documento(s)",
        duracao,
        len(resultado.mensagens),
        len(resultado.audios),
        len(resultado.documentos),
    )
    return resultado


def processar_audios_avulsos(caminhos_audio: list[Path]) -> ResultadoIngestao:
    """Classifica uma lista de arquivos de áudio enviados diretamente (sem zip).

    Args:
        caminhos_audio: caminhos de arquivos de áudio já presentes em disco.

    Returns:
        `ResultadoIngestao` sem mensagens de texto — não há `_chat.txt` nesse fluxo.
    """
    logger.info("Processando %d áudio(s) avulso(s)", len(caminhos_audio))
    return _classificar_arquivos(caminhos_audio)


def _extrair_zip_preservando_mtime(caminho_zip: Path, destino: Path) -> None:
    """Extrai todos os arquivos do zip, restaurando a data de modificação original.

    O `zipfile.extractall()` sozinho grava a data/hora da extração (agora) em
    cada arquivo, quebrando o fallback de timestamp por `st_mtime` (RF5.2), que
    depende da data original preservada dentro do zip do WhatsApp.

    Raises:
        ZipCorrompidoError: se o arquivo não for um zip válido ou contiver
            uma entrada corrompida.
    """
    destino.mkdir(parents=True, exist_ok=True)

    try:
        arquivo_zip = zipfile.ZipFile(caminho_zip)
    except zipfile.BadZipFile as erro:
        raise ZipCorrompidoError(f"Arquivo '{caminho_zip.name}' não é um zip válido: {erro}") from erro

    with arquivo_zip:
        try:
            entrada_invalida = arquivo_zip.testzip()
        except OSError as erro:
            # testzip() lê os dados locais de cada entrada e pode levantar OSError
            # genérico (não só BadZipFile) quando o diretório central diverge dos
            # dados locais — ex.: zip truncado no meio de uma transferência.
            raise ZipCorrompidoError(f"Zip corrompido: falha ao validar entradas ({erro})") from erro

        if entrada_invalida is not None:
            raise ZipCorrompidoError(f"Zip corrompido: entrada inválida em '{entrada_invalida}'")

        for info in arquivo_zip.infolist():
            if info.is_dir():
                continue

            try:
                arquivo_zip.extract(info, destino)
            except OSError as erro:
                raise ZipCorrompidoError(f"Zip corrompido: falha ao extrair '{info.filename}' ({erro})") from erro

            caminho_extraido = destino / info.filename

            try:
                timestamp = datetime(*info.date_time).timestamp()
                os.utime(caminho_extraido, (timestamp, timestamp))
            except (ValueError, OSError) as erro:
                logger.warning("Não foi possível preservar a data de '%s': %s", info.filename, erro)


def _classificar_arquivos(arquivos: list[Path]) -> ResultadoIngestao:
    """Separa arquivos extraídos em mensagens (via `_chat.txt`), áudios e documentos."""
    caminho_chat = next((arquivo for arquivo in arquivos if arquivo.name == _NOME_ARQUIVO_CHAT), None)

    mensagens: list[Mensagem] = []
    if caminho_chat is not None:
        conteudo = caminho_chat.read_text(encoding="utf-8", errors="replace")
        mensagens = parsear_chat(conteudo)
    else:
        logger.warning("Nenhum '%s' encontrado — apenas mídia será processada.", _NOME_ARQUIVO_CHAT)

    remetentes_por_arquivo = _mapear_remetentes_de_midia(mensagens)

    # Uma linha como "João: PTT-0001.opus (arquivo anexado)" não é uma mensagem de
    # texto de verdade — é como o WhatsApp representa o anexo no _chat.txt. Mantê-la
    # na lista de mensagens duplicaria o conteúdo na timeline (a linha crua e, em
    # seguida, a transcrição do mesmo áudio).
    mensagens = [mensagem for mensagem in mensagens if _extrair_nome_arquivo_anexado(mensagem.texto) is None]

    audios: list[Audio] = []
    documentos: list[Documento] = []

    for arquivo in arquivos:
        if arquivo == caminho_chat:
            continue

        if arquivo.suffix.lower() in config.SUPPORTED_AUDIO_EXTENSIONS:
            audios.append(_criar_audio(arquivo, remetentes_por_arquivo.get(arquivo.name)))
        else:
            documentos.append(
                Documento(nome=arquivo.name, caminho=arquivo, tipo=arquivo.suffix.lstrip(".") or "desconhecido")
            )

    return ResultadoIngestao(sucesso=True, mensagens=mensagens, audios=audios, documentos=documentos)


def _criar_audio(caminho: Path, remetente: str | None) -> Audio:
    """Monta um `Audio` a partir de um arquivo em disco e do remetente já associado (se houver).

    A ordenação cronológica (RF5.2) usa `st_mtime` como fonte principal do
    timestamp, e não o padrão de nome `PTT-YYYYMMDD-WAXXXX` — este último só
    carrega a data, sem hora, e usá-lo como prioridade 1 perderia precisão em
    relação ao `st_mtime` (que já preserva a data/hora original do zip, ver
    `_extrair_zip_preservando_mtime`). O nome do arquivo é usado apenas como
    validação cruzada: se a data divergir, é um aviso, não uma substituição.
    """
    estatisticas = caminho.stat()
    data_criacao = datetime.fromtimestamp(estatisticas.st_mtime)

    data_do_nome = _extrair_data_do_nome(caminho.name)
    if data_do_nome is not None and data_do_nome != data_criacao.date():
        logger.warning(
            "Data no nome do arquivo '%s' (%s) diverge da data de modificação (%s) — "
            "mantendo a data de modificação por ser mais precisa (inclui horário).",
            caminho.name,
            data_do_nome,
            data_criacao.date(),
        )

    return Audio(
        nome=caminho.name,
        caminho=caminho,
        tamanho_bytes=estatisticas.st_size,
        data_criacao=data_criacao,
        remetente=remetente,
    )


def _extrair_data_do_nome(nome_arquivo: str) -> date | None:
    """Extrai a data (sem hora) do padrão de nome `PTT-YYYYMMDD-WAXXXX` do WhatsApp, se houver."""
    match = _PADRAO_NOME_PTT.search(nome_arquivo)
    if match is None:
        return None
    try:
        return date(int(match["ano"]), int(match["mes"]), int(match["dia"]))
    except ValueError:
        return None


def _mapear_remetentes_de_midia(mensagens: list[Mensagem]) -> dict[str, str]:
    """Associa nome de arquivo de mídia ao remetente, a partir de menções no `_chat.txt`.

    O WhatsApp registra cada anexo como uma mensagem cujo texto é o próprio
    nome do arquivo (ex.: "PTT-20260703-WA0001.opus (arquivo anexado)"). Essa é
    a única fonte confiável de "quem enviou" — precisa ser preservada até o
    `timeline_builder`, senão a informação se perde (ver Análise Crítica #4).
    """
    mapa: dict[str, str] = {}
    for mensagem in mensagens:
        nome_arquivo = _extrair_nome_arquivo_anexado(mensagem.texto)
        if nome_arquivo is not None:
            mapa[nome_arquivo] = mensagem.remetente
    return mapa


def _extrair_nome_arquivo_anexado(texto: str) -> str | None:
    """Extrai o nome de um arquivo de mídia citado em uma linha de anexo do WhatsApp."""
    texto = texto.strip()
    for marcador in _MARCADORES_ANEXO:
        if marcador in texto:
            return texto.replace(marcador, "").strip()
    return None
