"""Teste de fumaça para app.py — usa streamlit.testing para garantir que a UI carrega sem exceções."""

from streamlit.testing.v1 import AppTest

import config


def test_app_carrega_sem_excecoes_e_mostra_titulo():
    if not config.ffmpeg_disponivel():
        import pytest

        pytest.skip("FFmpeg não está disponível no PATH desta sessão de testes.")

    app = AppTest.from_file("app.py")
    app.run(timeout=30)

    assert not app.exception
    assert any("Zap2Task Audio Engine" in titulo.value for titulo in app.title)


def test_app_botao_processar_desabilitado_sem_upload():
    if not config.ffmpeg_disponivel():
        import pytest

        pytest.skip("FFmpeg não está disponível no PATH desta sessão de testes.")

    app = AppTest.from_file("app.py")
    app.run(timeout=30)

    botao_processar = next(botao for botao in app.button if botao.label == "Processar")
    assert botao_processar.disabled is True
