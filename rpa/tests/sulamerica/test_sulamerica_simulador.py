"""Testes de ponta a ponta: robô de verdade (Playwright) contra o simulador local.

Validam a LÓGICA (fluxo, filtros, paginação, cópia de cotação, registro que
impede reemissão, recuperação de PDF). Não validam os seletores do portal real:
isso é a calibragem com --ensaio --mapear.
"""
from __future__ import annotations

import json
import logging

import pytest
import yaml
from openpyxl import Workbook, load_workbook

from operadoras.sulamerica.simulador.servidor import Simulador

FAIXAS = ["0_18", "19_23", "24_28", "29_33", "34_38", "39_43", "44_48", "49_53", "54_58", "59_mais"]
COLUNAS = (["id", "cnpj", "vendedor", "cuidado_360", "seguro_novo", "congenere_atual", "tipo_contratacao",
            "vigencia_meses", "coparticipacao"] + [f"vidas_{f}" for f in FAIXAS]
           + ["idades_0_18", "idades_59_mais", "planos", "pasta_destino"])


@pytest.fixture()
def sim():
    s = Simulador().iniciar()
    yield s
    s.parar()


@pytest.fixture(autouse=True)
def login_falso():
    """O robô entra no simulador sozinho, com o login FALSO dele, guardado num cofre só de memória."""
    from nucleo.credenciais import Cofre, CofreMemoria
    CofreMemoria.esvaziar()
    Cofre("sulamerica", memoria=True).guardar(Simulador.CPF, Simulador.EMAIL, Simulador.SENHA)
    yield
    CofreMemoria.esvaziar()


def _pedido(**campos):
    base = {c: "" for c in COLUNAS}
    base.update({f"vidas_{f}": 0 for f in FAIXAS})
    base.update(campos)
    return [base[c] for c in COLUNAS]


def _preparar(tmp_path, sim, linhas, monkeypatch, **extra):
    monkeypatch.chdir(tmp_path)
    cfg = {
        "urls": {"login": sim.url_login},
        "execucao": {"modo_visual": False, "lentidao_ms": 0, "timeout_login_ms": 20000,
                     "login_reentrada_ms": 300, "login_liberacao_ms": 2500,
                     "timeout_tela_ms": 15000, "timeout_emissao_ms": 30000, "timeout_download_ms": 8000,
                     "pausa_entre_pedidos_s": 0},
        "saida": {"pasta": "saida", "nomes_arquivo": {"Executivo R1": "EXECUTIVO"}},
        "teste": {"cofre": "memoria"},
        **extra,
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    wb = Workbook()
    ws = wb.active
    ws.append(COLUNAS)
    for l in linhas:
        ws.append(l)
    wb.save(tmp_path / "cotacoes.xlsx")


def _rodar(*extra):
    import main
    return main.main(["--config", "config.yaml", "--planilha", "cotacoes.xlsx", *extra])


def _resultados(tmp_path, aba="cotacoes"):
    ws = load_workbook(tmp_path / "saida" / "resultados.xlsx")[aba]
    linhas = list(ws.iter_rows(values_only=True))
    return [dict(zip(linhas[0], l)) for l in linhas[1:]]


PEDIDO_VIDEO = dict(id="V1", cnpj="11.222.333/0001-81", cuidado_360="sim", seguro_novo="nao",
                    congenere_atual="NOTREDAME", vigencia_meses=24, coparticipacao="com",
                    vidas_0_18=1, vidas_34_38=2, idades_0_18="0",
                    planos="Especial Mais | Apartamento; Executivo R1 | Apartamento")


def test_ensaio_percorre_tudo_e_nao_emite(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio", "--mapear") == 0
    assert sim.emissoes == 0
    [r] = _resultados(tmp_path)
    assert (r["status"], r["plano"], r["acomodacao"]) == ("ENSAIO_OK", "Especial Mais", "Apartamento")
    # Mesmos números do vídeo: 521,90 + 2 x 960,78 = 2.443,46; IOF 58,16; total 2.501,62
    assert (r["total_sem_iof"], r["iof"], r["total_com_iof"]) == (2443.46, 58.16, 2501.62)
    assert r["valor_vida_0_18"] == 521.90 and r["valor_vida_34_38"] == 960.78
    assert len(_resultados(tmp_path, "precos_planos")) == 14          # leu as 2 páginas
    mapas = list((tmp_path / "saida" / "mapa").rglob("*.aria.txt"))
    assert len(mapas) >= 8                                            # uma árvore por tela


def test_tela_travada_no_cuidado_360_recarrega_e_retoma_o_pedido_desde_o_comeco(tmp_path, sim, monkeypatch):
    """15/11 (portal novo): a troca para o Cuidado 360° mudava a URL e a barra mas deixava o corpo da tela da empresa para
    sempre, sem nada pendente; o F5 voltava ao começo com o assistente vazio e o robô desistia. Agora recarrega uma vez e
    retoma o pedido de lá. Ensaio: nada é emitido."""
    sim.travar_troca_cuidado = True
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio") == 0
    assert sim.emissoes == 0
    [r] = _resultados(tmp_path)
    assert (r["status"], r["plano"]) == ("ENSAIO_OK", "Especial Mais")
    assert (r["total_sem_iof"], r["iof"], r["total_com_iof"]) == (2443.46, 58.16, 2501.62)
    log = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "saida" / "logs").glob("*.log"))
    assert "recarregando a página uma vez" in log and "retomando o pedido desde a tela da empresa" in log


def test_emite_dois_planos_copiando_e_nao_reemite(tmp_path, sim, monkeypatch):
    destino = tmp_path / "CLIENTE" / "SAUDE" / "COTACOES"
    destino.mkdir(parents=True)
    pedido_b = dict(id="N1", cnpj="45.723.174/0001-10", vendedor="Maria Corretora", cuidado_360="nao",
                    seguro_novo="sim", tipo_contratacao="cbo", vigencia_meses=12, coparticipacao="sem",
                    vidas_24_28=2, vidas_44_48=1, vidas_59_mais=1, idades_59_mais="62",
                    planos="menor_preco")
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO, pasta_destino=str(destino)), _pedido(**pedido_b)],
              monkeypatch)
    assert _rodar("--confirmar") == 0
    assert sim.emissoes == 3
    assert sim.visitas_contratacao == 0                               # nunca clicou em contratação
    rs = _resultados(tmp_path)
    assert [(r["pedido_id"], r["plano"], r["status"]) for r in rs] == [
        ("V1", "Especial Mais", "OK"), ("V1", "Executivo R1", "OK"), ("N1", "Direto Nacional", "OK")]
    assert rs[1]["total_sem_iof"] == 4592.88 and rs[1]["iof"] == 109.31   # Executivo R1 do vídeo
    assert sorted(p.name for p in destino.iterdir()) == ["SULAMERICA ESPECIAL MAIS.pdf", "SULAMERICA EXECUTIVO.pdf"]
    assert len(list((tmp_path / "saida" / "pdfs").glob("*.pdf"))) == 3
    # o pedido N1 foi cotado com os filtros pedidos (CBO, 12 meses, sem coparticipação)
    cot_n1 = [c for c in sim.cotacoes.values() if c["cnpj"] == "45723174000110"][0]["estado"]
    assert cot_n1["filtros"] == {"tipo": "CBO", "vig": {"12": True, "24": False}, "copart": {"sem": True, "com": False}}
    assert cot_n1["vendedor"] == "Maria Corretora" and cot_n1["idades"] == [{"idade": 62, "qtd": 1}]
    estado = json.loads((tmp_path / "saida" / "estado.json").read_text(encoding="utf-8"))
    assert {i["status"] for i in estado["itens"].values()} == {"pdf_ok"}

    # Segunda execução com a mesma planilha: nada é emitido de novo.
    assert _rodar("--confirmar") == 0
    assert sim.emissoes == 3
    assert [r["status"] for r in _resultados(tmp_path)[3:]] == ["PULADO", "PULADO", "PULADO"]


def test_falha_no_download_recupera_sem_reemitir(tmp_path, sim, monkeypatch):
    """Com a recuperação automática ligada (só depois de confirmada no portal real)."""
    pedido = dict(PEDIDO_VIDEO, planos="Especial Mais | Apartamento")
    _preparar(tmp_path, sim, [_pedido(**pedido)], monkeypatch, recuperar_pdf_automatico=True)
    sim.falhar_download.add(str(sim.proximo))      # o 1º download desta cotação vai falhar
    assert _rodar("--confirmar") == 3
    assert sim.emissoes == 1
    assert _resultados(tmp_path)[-1]["status"] == "VERIFICAR"
    estado = json.loads((tmp_path / "saida" / "estado.json").read_text(encoding="utf-8"))
    assert [i["status"] for i in estado["itens"].values()] == ["emitida"]

    assert _rodar("--confirmar") == 0              # nova execução: recupera o PDF pela página da emissão
    assert sim.emissoes == 1                       # sem nova emissão
    estado = json.loads((tmp_path / "saida" / "estado.json").read_text(encoding="utf-8"))
    assert [i["status"] for i in estado["itens"].values()] == ["pdf_ok"]


def test_plano_inexistente_nao_trava_os_outros(tmp_path, sim, monkeypatch):
    pedido = dict(PEDIDO_VIDEO, id="F1", planos="Plano Fantasma | Apartamento; Especial Vital | Apartamento")
    _preparar(tmp_path, sim, [_pedido(**pedido)], monkeypatch)
    assert _rodar("--confirmar") == 3
    rs = _resultados(tmp_path)
    assert [(r["plano"], r["status"]) for r in rs] == [("Plano Fantasma", "ERRO"), ("Especial Vital", "OK")]
    assert "Disponíveis" in rs[0]["erro"]
    assert sim.emissoes == 1
    # "Especial Vital" não pode ter sido confundido com "Especial Vital R1"
    assert list(sim.cotacoes.values())[0]["plano"] == "Especial Vital"


# ---------- cenários da revisão independente: a mesma cotação nunca sai duas vezes ----------

OUTRA = dict(PEDIDO_VIDEO, cnpj="45.723.174/0001-10")


def _emitidos(sim):
    return [(c["cnpj"], c["plano"], c["acomodacao"]) for c in sim.cotacoes.values()]


def test_mesmo_plano_com_duas_grafias_na_mesma_linha(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, id="A1",
                                             planos="Especial Mais; Especial Mais | Apartamento"))], monkeypatch)
    _rodar("--confirmar")
    assert sim.emissoes == 1
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "PULADO"]


def test_regrafia_entre_execucoes_nao_reemite(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, id="B1", planos="Especial Mais"))], monkeypatch)
    _rodar("--confirmar")
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, id="OUTRO-ID",
                                             planos="Especial Mais | Apartamento"))], monkeypatch)
    assert _rodar("--confirmar") == 0
    assert sim.emissoes == 1
    assert _resultados(tmp_path)[-1]["status"] == "PULADO"


def test_linha_que_muda_de_lugar_sem_id_nao_reemite(tmp_path, sim, monkeypatch):
    sem_id = dict(PEDIDO_VIDEO, planos="Especial Mais | Apartamento")
    sem_id.pop("id")
    _preparar(tmp_path, sim, [_pedido(**sem_id)], monkeypatch)
    _rodar("--confirmar")
    # empresa nova inserida ACIMA: a já cotada vai da linha 2 para a 3
    outra = dict(OUTRA, planos="Especial Mais | Apartamento")
    outra.pop("id")
    _preparar(tmp_path, sim, [_pedido(**outra), _pedido(**sem_id)], monkeypatch)
    assert _rodar("--confirmar") == 0
    emitidos = _emitidos(sim)
    assert emitidos.count(("11222333000181", "Especial Mais", "Apartamento")) == 1
    assert emitidos.count(("45723174000110", "Especial Mais", "Apartamento")) == 1


def test_emitir_de_novo_so_o_protocolo_que_o_corretor_confirmou(tmp_path, sim, monkeypatch):
    """"Emitir de novo mesmo assim" (tela): só o protocolo confirmado, uma vez; o resto continua bloqueado."""
    from playwright.sync_api import sync_playwright

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--confirmar") == 0
    assert sim.emissoes == 2
    caminho = tmp_path / "saida" / "estado.json"
    itens = json.loads(caminho.read_text(encoding="utf-8"))["itens"]
    [(chave, item)] = [(k, v) for k, v in itens.items() if v["plano"] == "Especial Mais"]
    antigo = item["protocolo"]

    with sync_playwright() as pw:
        op, s, pedido = _sessao_direta(tmp_path, sim, monkeypatch, pw, mapear=False, ensaio=False,
                                       reemitir={antigo, "999999"})
        try:
            op.login(s)
            op.processar(s, pedido)
            assert sim.emissoes == 3                  # só o Especial Mais saiu de novo; o Executivo R1 pulou
            op.processar(s, pedido)                   # o mesmo pedido outra vez na mesma sessão: nada sai
            assert sim.emissoes == 3
        finally:
            s.contexto.close()
    assert sim.visitas_contratacao == 0
    depois = json.loads(caminho.read_text(encoding="utf-8"))
    novo = depois["itens"][chave]
    assert novo["status"] == "pdf_ok" and novo["protocolo"] != antigo and novo["reemissao_de"] == antigo
    assert [r["item"]["protocolo"] for r in depois["reemitidos"]] == [antigo]
    assert len(list((tmp_path / "saida" / "pdfs").glob("*.pdf"))) == 3   # o PDF de antes continua
    assert _rodar("--confirmar") == 0                # sem o pedido do corretor, tudo volta a ser bloqueado
    assert sim.emissoes == 3


# ---------- "Com e sem" coparticipação: duas cotações por plano ----------

COM_E_SEM = dict(PEDIDO_VIDEO, id="CS1", coparticipacao="as_duas", planos="Especial Mais | Apartamento")


def _coparts(sim):
    return [(c["plano"], "com" if c["estado"]["filtros"]["copart"]["com"] else "sem",
             bool(c["estado"].get("copiaDe"))) for c in sim.cotacoes.values()]


def test_com_e_sem_coparticipacao_duas_cotacoes_por_plano(tmp_path, sim, monkeypatch):
    destino = tmp_path / "CLIENTE"
    destino.mkdir()
    _preparar(tmp_path, sim, [_pedido(**dict(COM_E_SEM, pasta_destino=str(destino)))], monkeypatch)
    assert _rodar("--confirmar") == 0
    # como no vídeo: a 2ª pela "Copiar cotação", trocando só a coparticipação no filtro da tela Planos, sem
    # sair do portal (nenhum login a mais, nenhuma saída)
    assert _coparts(sim) == [("Especial Mais", "com", False), ("Especial Mais", "sem", True)]
    assert sim.tentativas_login == 1 and sim.saidas == 1        # a única saída é a do fim da fila
    assert sim.visitas_contratacao == 0
    rs = _resultados(tmp_path)
    assert [(r["plano"], r["coparticipacao"], r["status"]) for r in rs] == [
        ("Especial Mais", "com", "OK"), ("Especial Mais", "sem", "OK")]
    assert rs[0]["total_com_iof"] < rs[1]["total_com_iof"]          # sem coparticipação é mais caro
    assert sorted(p.name for p in destino.iterdir()) == [
        "SULAMERICA ESPECIAL MAIS COM COPARTICIPACAO.pdf", "SULAMERICA ESPECIAL MAIS SEM COPARTICIPACAO.pdf"]
    assert len(list((tmp_path / "saida" / "pdfs").glob("*.pdf"))) == 2
    # pedir de novo: nada é reemitido
    assert _rodar("--confirmar") == 0
    assert sim.emissoes == 2
    assert [(r["coparticipacao"], r["status"]) for r in _resultados(tmp_path)[2:]] == [("com", "PULADO"), ("sem", "PULADO")]


def test_com_e_sem_quando_a_copia_nao_deixa_trocar_usa_nova_cotacao(tmp_path, sim, monkeypatch, caplog):
    """Plano B: a cópia não deixa trocar a coparticipação. O robô sai da cotação (mesma aba, sem login nem
    logout), vai por NOVA COTAÇÃO no painel e faz a versão sem do começo. E guarda isso: no pedido seguinte já
    vai direto pelo "Nova cotação" da tela da emissão, sem tentar a cópia."""
    import json as _json

    sim.copia_trava_copart = True
    sim.sair_da_cotacao_vai_ao_painel = True
    sim.um_acesso_por_cpf = True
    caplog.set_level(logging.INFO, logger="cotacao")
    _preparar(tmp_path, sim, [_pedido(**COM_E_SEM), _pedido(**dict(COM_E_SEM, id="CS2", cnpj=OUTRA["cnpj"]))],
              monkeypatch)
    assert _rodar("--confirmar") == 0
    assert _coparts(sim) == [("Especial Mais", "com", False), ("Especial Mais", "sem", False),
                             ("Especial Mais", "com", False), ("Especial Mais", "sem", False)]
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "OK", "OK", "OK"]
    assert caplog.text.count("não deixou mudar o filtro 'Sem coparticipação'") == 1     # só no 1º pedido
    assert "Painel de cotações: NOVA COTAÇÃO." in caplog.text
    assert "por Nova cotação (neste portal a cópia não deixa trocar a coparticipação)" in caplog.text
    assert sim.tentativas_login == 1 and sim.saidas == 1        # sem login no meio; só a saída do fim da fila
    assert _json.loads((tmp_path / "saida" / "portal.json").read_text(encoding="utf-8"))["copia_trava_copart"]


def test_com_e_sem_parar_entre_as_duas_e_continuar_sem_reemitir(tmp_path, sim, monkeypatch):
    from playwright.sync_api import sync_playwright
    from nucleo.navegador import Parado

    with sync_playwright() as pw:
        op, s, pedido = _sessao_direta(tmp_path, sim, monkeypatch, pw, mapear=False, ensaio=False, pedido=COM_E_SEM,
                                       parar=lambda: sim.emissoes >= 1)   # o corretor clica em Parar depois da 1ª
        try:
            op.login(s)
            with pytest.raises(Parado):
                op.processar(s, pedido)
        finally:
            s.contexto.close()
        assert sim.emissoes == 1
        assert [(r["coparticipacao"], r["status"]) for r in _resultados(tmp_path)] == [("com", "OK"), ("sem", "PARADO")]
        op, s, pedido = _sessao_direta(tmp_path, sim, monkeypatch, pw, mapear=False, ensaio=False, pedido=COM_E_SEM)
        try:
            op.login(s)
            op.processar(s, pedido)                   # continuar: só a "sem" falta
        finally:
            s.contexto.close()
    assert sim.emissoes == 2
    assert _coparts(sim)[1][:2] == ("Especial Mais", "sem")
    assert [(r["coparticipacao"], r["status"]) for r in _resultados(tmp_path)[2:]] == [("com", "PULADO"), ("sem", "OK")]


def test_pasta_destino_inexistente_barra_so_a_linha(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [
        _pedido(**dict(PEDIDO_VIDEO, id="D1", planos="Especial Mais | Apartamento",
                       pasta_destino=str(tmp_path / "NAO_EXISTE"))),
        _pedido(**dict(OUTRA, id="D2", planos="Especial Mais | Apartamento"))], monkeypatch)
    _rodar("--confirmar")
    assert _emitidos(sim) == [("45723174000110", "Especial Mais", "Apartamento")]
    erros = _resultados(tmp_path, "erros_planilha")
    assert erros[0]["pedido_id"] == "D1" and "pasta_destino" in erros[0]["erro"]


# ---------- login automático (cofre de memória com o login FALSO do simulador) ----------


def _sessao_direta(tmp_path, sim, monkeypatch, pw, mapear=True, ensaio=True, reemitir=(), pedido=None,
                   parar=None):
    """Robô aberto direto (sem main.py): config do teste, navegador, sessão e mapa."""
    import operadoras
    from nucleo.estado import Estado
    from nucleo.navegador import Mapeador, abrir
    from nucleo.registro import carregar_config_com_ajustes, configurar_log, migrar_legado

    _preparar(tmp_path, sim, [_pedido(**(pedido or PEDIDO_VIDEO))], monkeypatch)
    op = operadoras.obter("sulamerica")
    total = carregar_config_com_ajustes("config.yaml")
    migrar_legado(total)
    cfg = op.config(total)
    cfg["execucao"]["mapear"] = mapear
    [pedido], _ = op.ler_planilha("cotacoes.xlsx", cfg)
    pasta = tmp_path / "saida"
    log = configurar_log(pasta / "logs")
    contexto, page = abrir(pw, cfg)
    s = op.nova_sessao(cfg, log, contexto, page, Estado(pasta / "estado.json"),
                       op.resultados(pasta / "resultados.xlsx", log),
                       Mapeador(pasta, mapear, log, url_login=cfg["urls"]["login"]), ensaio, reemitir=reemitir,
                       parar=parar)
    return op, s, pedido


def _arquivos_com_login(pasta) -> list[str]:
    """Arquivos de `pasta` em que aparece o CPF, o e-mail ou a senha falsos (texto ou UTF-16)."""
    valores = [Simulador.CPF, "529.982.247-25", Simulador.EMAIL, Simulador.SENHA]
    padroes = [v.encode(cod) for v in valores for cod in ("utf-8", "utf-16-le")]
    return [str(a) for a in pasta.rglob("*") if a.is_file() and any(p in a.read_bytes() for p in padroes)]


def test_login_automatico_ok(tmp_path, sim, monkeypatch):
    """O robô entra sozinho; o mapa só tem o login com os campos vazios; com a sessão ativa não digita de novo.
    Como no portal real (05/11): com a sessão viva, recarregar o login mostra o formulário e um segundo login
    seria recusado ("acesso ativo"); o robô não pode recarregar."""
    from playwright.sync_api import sync_playwright

    sim.um_acesso_por_cpf = True
    with sync_playwright() as pw:
        op, s, _ = _sessao_direta(tmp_path, sim, monkeypatch, pw)
        try:
            op.login(s)
            assert op.conectado(s.page)
            op.login(s)                                   # sessão ainda ativa: não digita de novo
        finally:
            s.contexto.close()
    assert sim.tentativas_login == 1
    mapas = sorted(p.name for p in (tmp_path / "saida" / "mapa").rglob("*.*"))
    assert mapas == ["01_login.aria.txt", "01_login.html", "01_login.png"]   # antes de digitar
    assert _arquivos_com_login(tmp_path / "saida") == []


def test_limite_real_da_senha_vai_para_a_configuracao(tmp_path, sim, monkeypatch):
    import json as _json
    from playwright.sync_api import sync_playwright

    sim.senha_maxlength = 20
    with sync_playwright() as pw:
        op, s, _ = _sessao_direta(tmp_path, sim, monkeypatch, pw, mapear=False)
        try:
            op.login(s)
        finally:
            s.contexto.close()
    assert _json.loads((tmp_path / "saida" / "portal.json").read_text(encoding="utf-8")) == {"senha_max": 20}
    assert op.configuracao(s.cfg)[0]["campos"][0]["senha_max"] == 20


def test_sem_credenciais_nao_abre_o_portal(tmp_path, sim, monkeypatch):
    from nucleo.credenciais import CofreMemoria
    CofreMemoria.esvaziar()
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio") == 5
    assert sim.requisicoes == 0                           # nem abriu o portal


def test_senha_errada_para_na_primeira_e_nao_tenta_de_novo(tmp_path, sim, monkeypatch, caplog):
    from playwright.sync_api import sync_playwright

    from nucleo.credenciais import Cofre
    from nucleo.navegador import ErroLogin
    cofre = Cofre("sulamerica", memoria=True)
    cofre.guardar(Simulador.CPF, Simulador.EMAIL, "senha-errada-123")
    caplog.set_level(logging.INFO, logger="cotacao")
    with sync_playwright() as pw:                         # pedido em andamento: o login cai no fluxo
        op, s, pedido = _sessao_direta(tmp_path, sim, monkeypatch, pw)
        try:
            with pytest.raises(ErroLogin) as erro:
                op.processar(s, pedido)
        finally:
            s.contexto.close()
    assert erro.value.motivo == "recusadas"
    assert sim.tentativas_login == 1
    assert cofre.situacao()["recusadas"] is True
    [r] = _resultados(tmp_path)
    assert (r["status"], r["etapa_erro"]) == ("ERRO", "login")
    # mapa: só o login vazio de antes de digitar; o registro do erro (forcar=True) depois de digitar não grava
    assert sorted(p.name for p in (tmp_path / "saida" / "mapa").rglob("*.*")) == [
        "01_login.aria.txt", "01_login.html", "01_login.png"]
    assert "mapa não gravado: tela de login" in caplog.text
    assert "senha-errada-123" not in caplog.text and Simulador.CPF not in caplog.text

    requisicoes = sim.requisicoes
    assert _rodar("--ensaio") == 5                        # recusado: não tenta de novo, nem abre o portal
    assert (sim.tentativas_login, sim.requisicoes) == (1, requisicoes)
    cofre.guardar(Simulador.CPF, Simulador.EMAIL, "")     # guardar sem digitar a senha não libera
    assert cofre.situacao()["recusadas"] is True
    cofre.guardar(Simulador.CPF, Simulador.EMAIL, Simulador.SENHA)   # o corretor guardou a senha outra vez
    assert cofre.situacao()["recusadas"] is False
    assert _rodar("--ensaio") == 0
    assert sim.tentativas_login == 2


@pytest.mark.parametrize("pedido_do_portal, tentativas", [
    ("captcha", 0),              # nem digita
    ("troca_senha", 1),          # bloco "REDEFINIR A SENHA" aparece na própria tela de login
    ("selecao_corretora", 1),    # pede para escolher a corretora (EV/EA/AA) depois do login
    ("validacao", 0),            # o formulário recusou o preenchimento (ex.: campo faltando)
])
def test_o_que_nao_e_senha_errada_para_sem_marcar_recusa(tmp_path, sim, monkeypatch, pedido_do_portal, tentativas):
    from nucleo.credenciais import Cofre
    sim.exigir_captcha = pedido_do_portal == "captcha"
    sim.exigir_troca_senha = pedido_do_portal == "troca_senha"
    sim.exigir_selecao_corretora = pedido_do_portal == "selecao_corretora"
    sim.validacao_forcada = "Campo obrigatório" if pedido_do_portal == "validacao" else ""
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio") == 5
    assert sim.tentativas_login == tentativas
    assert Cofre("sulamerica", memoria=True).situacao()["recusadas"] is False     # a senha não estava errada


def test_acesso_ativo_espera_e_entra_sozinho(tmp_path, sim, monkeypatch):
    """"Já existe um acesso ativo para esse CPF" (outro navegador, janela fechada) não é senha errada: o robô
    espera, entra de novo sozinho e o pedido segue."""
    from nucleo.credenciais import Cofre
    sim.acesso_ativo_por = 2
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio") == 0
    assert sim.tentativas_login == 3
    assert [r["status"] for r in _resultados(tmp_path)] == ["ENSAIO_OK"]
    assert Cofre("sulamerica", memoria=True).situacao()["recusadas"] is False


def test_acesso_ativo_que_nao_libera_para_no_limite(tmp_path, sim, monkeypatch):
    from nucleo.credenciais import Cofre
    sim.acesso_ativo = True
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio") == 5
    assert sim.tentativas_login >= 2                       # tentou de novo, dentro do limite
    assert Cofre("sulamerica", memoria=True).situacao()["recusadas"] is False


def test_senha_maior_que_o_campo_do_portal_nem_e_digitada(tmp_path, sim, monkeypatch, caplog):
    """O campo de senha do portal aceita 16 caracteres: uma maior seria cortada e recusada (e marcada).
    (Guardada direto no cofre: pela tela, a engrenagem já recusa uma senha assim.)"""
    from nucleo.credenciais import Cofre
    cofre = Cofre("sulamerica", memoria=True)
    cofre.guardar(Simulador.CPF, Simulador.EMAIL, "x" * 17)
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    caplog.set_level(logging.INFO, logger="cotacao")
    assert _rodar("--ensaio") == 5
    assert sim.tentativas_login == 0
    assert cofre.situacao()["recusadas"] is False
    assert "a senha guardada tem mais caracteres do que o campo do portal aceita (16)" in caplog.text
    assert "A senha guardada tem mais caracteres do que o portal da SulAmérica aceita" in caplog.text


def test_falha_no_download_fica_para_conferir_sem_tentar_de_novo(tmp_path, sim, monkeypatch):
    """Padrão: a emissão saiu e o PDF não veio. O robô não reabre a página da emissão: fica em
    "Conferir no portal" (baixar à mão), também nas próximas execuções."""
    pedido = dict(PEDIDO_VIDEO, planos="Especial Mais | Apartamento")
    _preparar(tmp_path, sim, [_pedido(**pedido)], monkeypatch)
    sim.falhar_download.add(str(sim.proximo))
    assert _rodar("--confirmar", "--mapear") == 3
    [r] = _resultados(tmp_path)
    assert r["status"] == "VERIFICAR" and "à mão" in r["erro"]
    assert list((tmp_path / "saida" / "mapa").rglob("*ERRO_emitida.aria.txt"))     # o mapa daquela tela
    assert _rodar("--confirmar") == 3
    assert sim.emissoes == 1
    estado = json.loads((tmp_path / "saida" / "estado.json").read_text(encoding="utf-8"))
    assert [i["status"] for i in estado["itens"].values()] == ["emitida"]          # não tentou baixar de novo
    assert _resultados(tmp_path)[-1]["status"] == "VERIFICAR"


def test_cotador_demorado_em_aba_nova_e_saida_pelo_modal(tmp_path, sim, monkeypatch):
    """O cotador abre devagar (página intermediária) numa aba nova; no fim do ensaio, "Sair da cotação"
    pede confirmação num modal que cobre a tela."""
    sim.cotador_em_aba_nova = True
    sim.cotador_lento_ms = 2500
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio", "--mapear") == 0
    [r] = _resultados(tmp_path)
    assert r["status"] == "ENSAIO_OK"
    assert list((tmp_path / "saida" / "mapa").rglob("*modal_sair.aria.txt"))
    assert sim.tentativas_login == 1


def test_sem_conseguir_sair_da_cotacao_nao_volta_ao_login(tmp_path, sim, monkeypatch, caplog):
    """Sem como sair da cotação, o robô não volta à página de login com a sessão viva (o portal recusaria
    o segundo acesso) e o pedido seguinte não começa na tela do anterior."""
    sim.modal_sair_sem_confirmar = True
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO), _pedido(**dict(OUTRA, id="V2"))], monkeypatch)
    caplog.set_level(logging.INFO, logger="cotacao")
    _rodar("--ensaio")
    rs = _resultados(tmp_path)
    assert rs[0]["status"] == "ENSAIO_OK"                       # o ensaio do 1º deu certo
    assert (rs[1]["status"], rs[1]["etapa_erro"]) == ("ERRO", "inicio")   # o 2º nem começou
    assert sim.tentativas_login == 1 and sim.emissoes == 0
    assert "não achei um botão só para confirmar (botões: Cancelar)" in caplog.text
    assert "não volta à página de login" in caplog.text


def test_pdf_em_aba_nova_nao_atrapalha_e_nada_e_fechado(tmp_path, sim, monkeypatch):
    """Portal real (04 e 05/11): a tela da emissão vira mapa (era tomada por tela de código). Se o download abrir
    outra aba, o robô não fecha nada (como o corretor): segue na aba da emissão, copia para o 2º plano e termina
    no painel "Estou em cotações"."""
    from playwright.sync_api import sync_playwright

    sim.pdf_abre_aba = True
    with sync_playwright() as pw:
        op, s, pedido = _sessao_direta(tmp_path, sim, monkeypatch, pw, ensaio=False)
        try:
            op.login(s)
            op.processar(s, pedido)                   # dois planos: o 2º pela "Copiar cotação"
            assert sim.emissoes == 2 and op.conectado(s.page)
            assert len(s.contexto.pages) == 3                  # a aba principal e as 2 do visualizador, abertas
        finally:
            s.contexto.close()
    assert sim.visitas_contratacao == 0
    mapas = sorted(p.name for p in (tmp_path / "saida" / "mapa").rglob("*.aria.txt"))
    assert sum("_emitida." in m for m in mapas) == 2 and sum("_emitida_pdf." in m for m in mapas) == 2
    assert _arquivos_com_login(tmp_path / "saida") == []


def test_voltar_para_a_home_vai_ao_painel_e_o_proximo_pedido_segue_sem_novo_login(tmp_path, sim, monkeypatch):
    """Portal real (05/11): "Voltar para a Home" leva ao painel "Estou em cotações" (PainelCotacao.aspx), que o
    robô não conhecia: esperava 60 s e parava. Agora o painel é um começo (NOVA COTAÇÃO abre o cotador) e conta
    como sessão aberta: o robô nunca recarrega o login ali (com um acesso por CPF, o portal recusaria)."""
    sim.um_acesso_por_cpf = True
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, planos="Especial Mais | Apartamento")),
                              _pedido(**dict(OUTRA, id="O1", planos="Especial Mais | Apartamento"))], monkeypatch)
    assert _rodar("--confirmar", "--mapear") == 0
    assert sim.emissoes == 2 and sim.tentativas_login == 1
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "OK"]
    mapas = [p.name for p in (tmp_path / "saida" / "mapa").rglob("*.aria.txt")]
    assert any("_painel." in m for m in mapas)          # o campo de senha escondido não esconde o painel do mapa
    assert _arquivos_com_login(tmp_path / "saida") == []


def test_sem_voltar_para_a_home_usa_nova_cotacao_e_segue(tmp_path, sim, monkeypatch, caplog):
    sim.sem_voltar_home = True
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, planos="Especial Mais | Apartamento")),
                              _pedido(**dict(OUTRA, id="O1", planos="Especial Mais | Apartamento"))], monkeypatch)
    assert _rodar("--confirmar") == 0
    assert sim.emissoes == 2
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "OK"]
    assert "Não achei o botão 'Voltar para a home'" in caplog.text


def test_sessao_expirada_no_meio_refaz_o_login_e_nao_reemite(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.expirar_apos_download = True           # a sessão cai logo depois do 1º PDF, no meio do pedido
    assert _rodar("--confirmar") == 0
    assert sim.tentativas_login == 2           # entrou de novo sozinho
    assert sim.emissoes == 2
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "OK"]
    assert _rodar("--confirmar") == 0
    assert sim.emissoes == 2                   # nada reemitido
    assert [r["status"] for r in _resultados(tmp_path)][2:] == ["PULADO", "PULADO"]


# ---------- LGPD: a tela de login e a de código nunca vão para o mapa depois de digitar ----------


def test_acesso_ativo_no_meio_do_pedido_para_sem_insistir(tmp_path, sim, monkeypatch, caplog):
    """A sessão cai no meio do pedido e, no login de novo, o portal diz "acesso ativo": alguém entrou com o CPF.
    No meio do pedido o robô para na hora (não espera nem tenta de novo) e não marca o login como recusado."""
    from nucleo.credenciais import Cofre

    sim.expirar_apos_download = True
    sim.acesso_ativo_depois_de_expirar = True
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)    # dois planos
    assert _rodar("--confirmar") == 5                                    # parou no login
    assert sim.emissoes == 1 and sim.tentativas_login == 2               # o 2º login não foi repetido
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "ERRO"]
    assert "O robô parou e não tenta de novo" in caplog.text
    assert not Cofre("sulamerica", memoria=True).situacao()["recusadas"]


# ---------- sair do portal (logout): libera o CPF do corretor ----------

def test_sair_do_portal_e_entrar_de_novo_sem_reemitir(tmp_path, sim, monkeypatch):
    """"Sair do Cotador" (menu do portal) a partir do painel "Estou em cotações" (onde "Voltar para a Home"
    leva) e de dentro do cotador. Com um acesso por CPF, o 2º login só passa porque o robô saiu de verdade
    (fechar a janela não bastaria)."""
    from playwright.sync_api import sync_playwright

    sim.um_acesso_por_cpf = True
    um_plano = dict(PEDIDO_VIDEO, planos="Especial Mais | Apartamento")
    with sync_playwright() as pw:
        op, s, pedido = _sessao_direta(tmp_path, sim, monkeypatch, pw, mapear=False, ensaio=False, pedido=um_plano)
        try:
            op.login(s)
            op.processar(s, pedido)
            assert sim.emissoes == 1 and op.conectado(s.page)
            assert s.page.get_by_text("ESTOU EM COTAÇÕES").is_visible()
            assert op.sair(s) is True                          # do painel de cotações
            assert sim.saidas == 1 and not sim.sessoes
        finally:
            s.contexto.close()
        op, s, pedido = _sessao_direta(tmp_path, sim, monkeypatch, pw, mapear=False, ensaio=False, pedido=um_plano)
        try:
            op.login(s)                                        # entra de novo sozinho
            assert sim.tentativas_login == 2
            op.processar(s, pedido)                            # o mesmo pedido: nada reemitido
            assert sim.emissoes == 1
            s.page.get_by_text("Cotação PME", exact=True).click()   # agora de dentro do cotador
            s.page.wait_for_url("**/dados-empresa**")
            assert op.sair(s) is True
            assert sim.saidas == 2 and not sim.sessoes
        finally:
            s.contexto.close()
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "PULADO"]


class _Bus:
    def __init__(self):
        self.eventos = []

    def publicar(self, evento):
        self.eventos.append(evento)


def test_trabalhador_sai_do_portal_so_com_a_fila_vazia(tmp_path, sim, monkeypatch, caplog):
    """Folga sem pedidos (aqui 3 s), nunca no meio da fila, "Sair do portal agora" só com o robô parado, e o
    pedido seguinte entra de novo sozinho sem reemitir."""
    import time as _time

    from app.banco import Banco
    from app.trabalhador import Trabalhador
    from nucleo.registro import carregar_config_com_ajustes

    sim.um_acesso_por_cpf = True        # sem sair de verdade, o 2º login seria recusado ("acesso ativo")
    caplog.set_level(logging.INFO, logger="cotacao")
    _preparar(tmp_path, sim, [], monkeypatch)
    arquivo = tmp_path / "config.yaml"

    def folga(minutos):
        cfg = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
        cfg["execucao"]["sair_do_portal_min"] = minutos
        arquivo.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    folga(0.05)
    banco = Banco(tmp_path / "saida" / "tela.db")
    bus = _Bus()
    robo = Trabalhador(lambda: carregar_config_com_ajustes("config.yaml"), banco, bus)
    robo.start()
    um = dict(PEDIDO_VIDEO, planos="Especial Mais | Apartamento")
    outro = dict(OUTRA, id="O1", planos="Especial Mais | Apartamento")

    def cotar(*pedidos):
        itens = [{"operadora": "sulamerica", "pedidos": [dict(zip(COLUNAS, _pedido(**p))) for p in pedidos]}]
        tid = banco.novo_trabalho("cotar", "emitir", "teste", len(pedidos), len(pedidos), itens)
        robo.enfileirar({"id": tid, "tipo": "cotar", "modo": "emitir", "titulo": "teste", "itens": itens})
        return tid

    def esperar(condicao, segundos):
        fim = _time.monotonic() + segundos
        while not condicao():
            assert _time.monotonic() < fim, "não aconteceu a tempo"
            _time.sleep(0.2)

    try:
        a, b = cotar(um), cotar(outro)                         # dois trabalhos seguidos
        esperar(lambda: banco.trabalho(b)["status"] == "concluido", 180)
        assert banco.trabalho(a)["status"] == "concluido"
        assert sim.emissoes == 2 and sim.tentativas_login == 1 and sim.saidas == 0   # nada de sair no meio
        esperar(lambda: sim.saidas == 1 and "sulamerica" not in robo.navegadores, 30)   # fila vazia há 3 s
        esperar(lambda: any(e["tipo"] == "saiu_do_portal" and e["ok"] for e in bus.eventos), 10)
        assert "Saí do portal (fila vazia há 0.05 min)." in caplog.text

        folga(0)                                               # 0 = não sai sozinho
        c = cotar(um)                                          # o mesmo pedido: entra de novo, nada reemitido
        assert robo.pedir_saida("sulamerica") == "ocupado"     # com trabalho na fila, o botão não vale
        esperar(lambda: banco.trabalho(c)["status"] == "concluido", 120)
        assert sim.tentativas_login == 2 and sim.emissoes == 2
        assert [x["status"] for x in banco.cotacoes(trabalho=c)] == ["PULADO"]
        _time.sleep(6)
        assert sim.saidas == 1                                 # com 0 não saiu sozinho
        assert robo.pedir_saida("sulamerica") == "ok"          # "Sair do portal agora"
        esperar(lambda: sim.saidas == 2 and "sulamerica" not in robo.navegadores, 30)
        assert "Saí do portal (o corretor pediu)." in caplog.text
        assert robo.pedir_saida("sulamerica") == "fora"
    finally:
        robo.encerrar()
        robo.join(20)


def test_mapa_do_login_so_com_campos_vazios(tmp_path):
    """Login (URL de login ou campo de senha, inclusive em iframe): só com os campos vazios e antes de o
    robô digitar. Código de verificação: nunca. Página comum: grava normalmente."""
    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Mapeador

    mapa = Mapeador(tmp_path, True, logging.getLogger("teste_mapa"),
                    url_login="https://os11.sulamerica.com.br/SaudeCotador/LoginGeral.aspx")
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        try:
            page = navegador.new_page()
            page.set_content("<input value='12345678909'><input type='PASSWORD'>")
            assert mapa.registrar(page, "ERRO_x", forcar=True) is None
            assert mapa.registrar(page, "login", login_vazio=True) is None          # campo preenchido
            page.set_content("<iframe srcdoc=\"<input type='password'>\"></iframe>")
            assert mapa.registrar(page, "ERRO_y", forcar=True) is None
            page.set_content("<input placeholder='Código de verificação'>")
            assert mapa.registrar(page, "codigo", forcar=True, login_vazio=True) is None
            page.set_content("<input placeholder='CPF'><input type='password'>")
            assert mapa.registrar(page, "login", login_vazio=True) is not None      # vazio, antes de digitar
            mapa.login_digitado = True
            assert mapa.registrar(page, "login", login_vazio=True) is None          # depois de digitar, nunca
            page.set_content("<h1>Comece por aqui</h1>")
            assert mapa.registrar(page, "dados_empresa") is not None                 # sem senha: grava
        finally:
            navegador.close()
    assert sorted(p.name for p in (tmp_path / "mapa").rglob("*.*")) == [
        "01_login.aria.txt", "01_login.html", "01_login.png",
        "02_dados_empresa.aria.txt", "02_dados_empresa.html", "02_dados_empresa.png"]
