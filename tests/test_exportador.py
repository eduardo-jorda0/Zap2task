"""Testes unitários para modules/exportador.py."""

import json
from datetime import datetime

from docx import Document as DocxDocument

from models.tipos import (
    DuplicataRemovida,
    Falha,
    Metadados,
    RelatorioFinal,
    TimelineItem,
    TipoItemTimeline,
)
from modules.exportador import exportar_docx, exportar_json, exportar_txt


def _relatorio_de_teste() -> RelatorioFinal:
    metadados = Metadados(
        processado_em=datetime(2026, 7, 6, 14, 30),
        total_mensagens_texto=2,
        total_audios_transcritos=2,
        duplicatas_removidas=1,
        modelo_whisper_usado="base",
    )
    timeline = [
        TimelineItem(
            timestamp=datetime(2026, 7, 3, 9, 15),
            remetente="João",
            tipo=TipoItemTimeline.TEXTO,
            conteudo="Bom dia! Vamos revisar o contrato hoje?",
        ),
        TimelineItem(
            timestamp=datetime(2026, 7, 3, 9, 17),
            remetente="Você",
            tipo=TipoItemTimeline.AUDIO,
            conteudo="Bom dia João, pode ser sim,\nvou separar o material e te mando até meio dia.",
            confianca=0.92,
            arquivo_origem="PTT-20260703-WA0001.mp3",
        ),
        TimelineItem(
            timestamp=datetime(2026, 7, 3, 12, 3),
            remetente="Você",
            tipo=TipoItemTimeline.AUDIO,
            conteudo="oi joão desculpa a demora consegui...",
            confianca=0.78,
            arquivo_origem="PTT-20260703-WA0002.mp3",
        ),
    ]
    return RelatorioFinal(
        metadados=metadados,
        timeline=timeline,
        duplicatas_removidas=[DuplicataRemovida(arquivo_removido="dup.opus", duplicata_de="original.opus")],
        falhas_conversao=[Falha(arquivo="corrompido.opus", motivo="FFmpeg falhou")],
        falhas_transcricao=[],
    )


def test_exportar_txt_gera_cabecalho_e_marca_baixa_confianca(tmp_path):
    caminho = exportar_txt(_relatorio_de_teste(), tmp_path)

    assert caminho.exists()
    assert caminho.name.startswith("conversa_20260706_143000")

    conteudo = caminho.read_text(encoding="utf-8")
    assert "Total de mensagens de texto: 2" in conteudo
    assert "Duplicatas removidas: 1" in conteudo
    assert "[03/07/2026 09:15] João (texto):" in conteudo
    assert "confiança 92%" in conteudo
    assert "[transcrição de baixa confiança — revisar manualmente] oi joão" in conteudo
    assert "    vou separar o material" in conteudo  # continuação indentada


def test_exportar_json_estrutura_completa(tmp_path):
    caminho = exportar_json(_relatorio_de_teste(), tmp_path)

    dados = json.loads(caminho.read_text(encoding="utf-8"))

    assert dados["metadados"]["total_mensagens_texto"] == 2
    assert dados["metadados"]["modelo_whisper_usado"] == "base"
    assert len(dados["timeline"]) == 3
    assert dados["timeline"][1]["tipo"] == "audio"
    assert dados["timeline"][1]["confianca"] == 0.92
    assert dados["duplicatas_removidas"] == [{"arquivo": "dup.opus", "duplicata_de": "original.opus"}]
    assert dados["falhas_conversao"] == [{"arquivo": "corrompido.opus", "motivo": "FFmpeg falhou"}]
    assert dados["falhas_transcricao"] == []


def test_exportar_docx_gera_documento_valido_com_paragrafos(tmp_path):
    caminho = exportar_docx(_relatorio_de_teste(), tmp_path)

    assert caminho.exists()
    documento = DocxDocument(str(caminho))
    texto_completo = "\n".join(paragrafo.text for paragrafo in documento.paragraphs)

    assert "Zap2Task Audio Engine" in texto_completo
    assert "Total de mensagens de texto: 2" in texto_completo
    assert "Bom dia! Vamos revisar o contrato hoje?" in texto_completo
