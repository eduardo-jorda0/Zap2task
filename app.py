"""Interface Streamlit do Zap2Task Audio Engine — orquestra o pipeline completo (RF7).

O Streamlit executa o script inteiro de forma síncrona a cada interação, mas
chamadas a `barra_progresso.progress(...)` e `status.write(...)` são enviadas
ao navegador imediatamente, mesmo no meio de um script em execução — por isso
a barra de progresso atualiza em tempo real durante a conversão/transcrição
(RNF2), sem precisar de subprocess separado ou de threads na UI.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from models.tipos import Metadados, RelatorioFinal
from modules import audio_processor, exportador, ingestor, timeline_builder, transcritor
from utils.exceptions import FFmpegNaoEncontradoError, Zap2TaskError
from utils.logger import get_logger

logger = get_logger(__name__)

st.set_page_config(page_title="Zap2Task Audio Engine", page_icon="🎙️", layout="wide")


def _validar_ambiente_ou_parar() -> None:
    """Impede o uso da UI se o FFmpeg não estiver disponível, com mensagem clara (em vez de erro obscuro depois)."""
    try:
        config.validar_ambiente()
    except FFmpegNaoEncontradoError as erro:
        st.error(str(erro))
        st.stop()


def _renderizar_configuracoes() -> dict:
    """Renderiza os controles de configuração na barra lateral (RF7.2)."""
    st.sidebar.header("Configurações")
    tamanho_modelo = st.sidebar.selectbox(
        "Modelo Whisper",
        config.WHISPER_MODEL_OPTIONS,
        index=config.WHISPER_MODEL_OPTIONS.index(config.DEFAULT_WHISPER_MODEL),
        help="Modelos maiores são mais precisos, porém mais lentos.",
    )
    max_workers = st.sidebar.slider(
        "Threads de transcrição", config.MIN_THREADS, config.MAX_THREADS, config.DEFAULT_THREADS
    )
    idioma = st.sidebar.text_input("Idioma (código Whisper)", value=config.DEFAULT_LANGUAGE)
    gerar_docx = st.sidebar.checkbox("Gerar também .docx", value=False)
    return {
        "tamanho_modelo": tamanho_modelo,
        "max_workers": max_workers,
        "idioma": idioma,
        "gerar_docx": gerar_docx,
    }


def _validar_tamanho_upload(arquivos_enviados: list) -> bool:
    """Impede uploads maiores que o limite configurado (RNF1)."""
    tamanho_total_mb = sum(arquivo.size for arquivo in arquivos_enviados) / (1024 * 1024)
    if tamanho_total_mb > config.MAX_UPLOAD_SIZE_MB:
        st.error(
            f"Tamanho total do upload ({tamanho_total_mb:.0f}MB) excede o limite de "
            f"{config.MAX_UPLOAD_SIZE_MB}MB. Envie uma exportação menor."
        )
        return False
    return True


def _salvar_upload_em_disco(arquivo_streamlit, destino_dir: Path) -> Path:
    destino = destino_dir / arquivo_streamlit.name
    destino.write_bytes(arquivo_streamlit.getvalue())
    return destino


def _ingerir(arquivos_enviados: list, execucao_dir: Path):
    """Decide entre o fluxo de `.zip` (RF1.1) e o de áudios avulsos (RF1.2)."""
    arquivos_zip = [arquivo for arquivo in arquivos_enviados if arquivo.name.lower().endswith(".zip")]
    if arquivos_zip:
        if len(arquivos_zip) > 1:
            logger.warning("Múltiplos .zip enviados — processando apenas o primeiro (%s).", arquivos_zip[0].name)
        caminho_zip = _salvar_upload_em_disco(arquivos_zip[0], execucao_dir)
        return ingestor.processar_zip(caminho_zip, execucao_dir / "extraido")

    entrada_dir = execucao_dir / "audios_avulsos"
    entrada_dir.mkdir(parents=True, exist_ok=True)
    caminhos = [_salvar_upload_em_disco(arquivo, entrada_dir) for arquivo in arquivos_enviados]
    return ingestor.processar_audios_avulsos(caminhos)


def _executar_pipeline(arquivos_enviados: list, configuracoes: dict) -> RelatorioFinal:
    """Executa ingestor → audio_processor → transcritor → timeline_builder, com progresso na UI (RF7.3)."""
    config.ensure_directories()
    execucao_dir = config.TEMP_DIR / datetime.now().strftime("execucao_%Y%m%d_%H%M%S_%f")
    execucao_dir.mkdir(parents=True, exist_ok=True)

    barra_progresso = st.progress(0.0, text="Iniciando...")

    with st.status("Processando conversa...", expanded=True) as status:
        status.write("Etapa 1/4 — Ingestão (extraindo zip / lendo áudios)...")
        resultado_ingestao = _ingerir(arquivos_enviados, execucao_dir)
        if not resultado_ingestao.sucesso:
            status.update(label="Falha na ingestão", state="error")
            raise Zap2TaskError(resultado_ingestao.erro or "Falha desconhecida na ingestão.")
        barra_progresso.progress(0.15, text="Ingestão concluída")
        status.write(
            f"Encontradas {len(resultado_ingestao.mensagens)} mensagem(ns), "
            f"{len(resultado_ingestao.audios)} áudio(s), {len(resultado_ingestao.documentos)} documento(s)."
        )

        status.write("Etapa 2/4 — Convertendo áudios e removendo duplicatas...")
        resultado_conversao = audio_processor.converter_e_deduplicar(
            resultado_ingestao.audios, execucao_dir / "convertidos"
        )
        barra_progresso.progress(0.35, text="Conversão e deduplicação concluídas")
        status.write(
            f"{len(resultado_conversao.audios_unicos)} áudio(s) único(s), "
            f"{len(resultado_conversao.duplicatas_removidas)} duplicata(s) removida(s), "
            f"{len(resultado_conversao.falhas_conversao)} falha(s) de conversão."
        )

        status.write("Etapa 3/4 — Transcrevendo áudios com Whisper...")

        def _callback_progresso(concluidos: int, total: int) -> None:
            fracao = 0.35 + 0.5 * (concluidos / total if total else 1)
            barra_progresso.progress(fracao, text=f"Transcrevendo {concluidos}/{total} áudio(s)...")

        resultado_transcricao = transcritor.transcrever_lote(
            resultado_conversao.audios_unicos,
            tamanho_modelo=configuracoes["tamanho_modelo"],
            idioma=configuracoes["idioma"],
            max_workers=configuracoes["max_workers"],
            callback_progresso=_callback_progresso,
        )
        barra_progresso.progress(0.85, text="Transcrição concluída")
        status.write(
            f"{len(resultado_transcricao.transcricoes)} transcrição(ões), "
            f"{len(resultado_transcricao.falhas)} falha(s) de transcrição."
        )

        status.write("Etapa 4/4 — Montando timeline final...")
        timeline = timeline_builder.construir_timeline(
            resultado_ingestao.mensagens, resultado_transcricao.transcricoes, resultado_ingestao.documentos
        )
        barra_progresso.progress(1.0, text="Concluído")
        status.update(label="Processamento concluído", state="complete")

    metadados = Metadados(
        processado_em=datetime.now(),
        total_mensagens_texto=len(resultado_ingestao.mensagens),
        total_audios_transcritos=len(resultado_transcricao.transcricoes),
        duplicatas_removidas=len(resultado_conversao.duplicatas_removidas),
        modelo_whisper_usado=configuracoes["tamanho_modelo"],
    )
    return RelatorioFinal(
        metadados=metadados,
        timeline=timeline,
        duplicatas_removidas=resultado_conversao.duplicatas_removidas,
        falhas_conversao=resultado_conversao.falhas_conversao,
        falhas_transcricao=resultado_transcricao.falhas,
    )


def _renderizar_preview(relatorio: RelatorioFinal) -> None:
    """Mostra a timeline final antes do download (RF7.4)."""
    st.subheader("Preview da timeline")

    tabela = pd.DataFrame(
        [
            {
                "Data/Hora": item.timestamp.strftime("%d/%m/%Y %H:%M"),
                "Remetente": item.remetente,
                "Tipo": item.tipo.value,
                "Conteúdo": item.conteudo,
                "Confiança": f"{item.confianca:.0%}" if item.confianca is not None else "",
            }
            for item in relatorio.timeline
        ]
    )
    st.dataframe(tabela, use_container_width=True, height=400)

    if relatorio.duplicatas_removidas:
        with st.expander(f"Duplicatas removidas ({len(relatorio.duplicatas_removidas)})"):
            for duplicata in relatorio.duplicatas_removidas:
                st.write(f"- `{duplicata.arquivo_removido}` → duplicata de `{duplicata.duplicata_de}`")

    falhas = relatorio.falhas_conversao + relatorio.falhas_transcricao
    if falhas:
        with st.expander(f"Falhas ({len(falhas)})"):
            for falha in falhas:
                st.write(f"- `{falha.arquivo}`: {falha.motivo}")


def _renderizar_downloads(relatorio: RelatorioFinal, gerar_docx: bool) -> None:
    """Gera os arquivos de saída e expõe os botões de download (RF6, RF7.5)."""
    st.subheader("Download")
    caminho_txt = exportador.exportar_txt(relatorio, config.OUTPUTS_DIR)
    caminho_json = exportador.exportar_json(relatorio, config.OUTPUTS_DIR)

    coluna_txt, coluna_json, coluna_docx = st.columns(3)
    with coluna_txt:
        st.download_button(
            "⬇️ Baixar .txt", data=caminho_txt.read_bytes(), file_name=caminho_txt.name, mime="text/plain"
        )
    with coluna_json:
        st.download_button(
            "⬇️ Baixar .json",
            data=caminho_json.read_bytes(),
            file_name=caminho_json.name,
            mime="application/json",
        )
    with coluna_docx:
        if gerar_docx:
            caminho_docx = exportador.exportar_docx(relatorio, config.OUTPUTS_DIR)
            st.download_button(
                "⬇️ Baixar .docx",
                data=caminho_docx.read_bytes(),
                file_name=caminho_docx.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )


def main() -> None:
    st.title("🎙️ Zap2Task Audio Engine")
    st.caption("Converta áudios do WhatsApp em texto legível e pesquisável — 100% local, sem IA generativa.")

    _validar_ambiente_ou_parar()
    configuracoes = _renderizar_configuracoes()

    arquivos_enviados = st.file_uploader(
        "Envie o .zip exportado do WhatsApp ou arquivos de áudio avulsos",
        type=["zip", "opus", "mp3", "m4a", "wav"],
        accept_multiple_files=True,
    )

    pode_processar = bool(arquivos_enviados) and _validar_tamanho_upload(arquivos_enviados or [])

    if st.button("Processar", type="primary", disabled=not pode_processar):
        try:
            st.session_state["relatorio"] = _executar_pipeline(arquivos_enviados, configuracoes)
            st.session_state["gerar_docx"] = configuracoes["gerar_docx"]
        except Zap2TaskError as erro:
            logger.error("Pipeline interrompido: %s", erro)
            st.error(f"Não foi possível processar: {erro}")

    if "relatorio" in st.session_state:
        _renderizar_preview(st.session_state["relatorio"])
        _renderizar_downloads(st.session_state["relatorio"], st.session_state.get("gerar_docx", False))


if __name__ == "__main__":
    main()
