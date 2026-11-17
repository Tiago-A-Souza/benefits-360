"""Robô da Amil (Playwright) contra o simulador local: a LÓGICA de uma oportunidade por empresa e uma cotação por plano,
do registro que impede criar de novo, da recuperação do PDF depois de uma queda e do código de login pedido ao corretor. Os
seletores do portal real são a calibragem (ensaio com prints)."""
from __future__ import annotations

import json

import pytest
import yaml
from openpyxl import Workbook, load_workbook

from operadoras.amil.simulador.servidor import Simulador

FAIXAS = ["0_18", "19_23", "24_28", "29_33", "34_38", "39_43", "44_48", "49_53", "54_58", "59_mais"]
COLUNAS = ["id", "cnpj", "apelido", "dental"] + [f"vidas_{f}" for f in FAIXAS] + ["planos", "pasta_destino"]
PEDIDO_VIDEO = dict(id="A1", cnpj="11.222.333/0001-81", apelido="PADARIA", vidas_0_18=1, vidas_34_38=2, vidas_59_mais=1,
                    planos="PLATINUM R1 COPART")
TRES_PLANOS = "PLATINUM R1 COPART; AMIL BLACK I R1 COPART; AMIL S2500 R1 QP COPART"


@pytest.fixture()
def sim():
    s = Simulador().iniciar()
    yield s
    s.parar()


@pytest.fixture(autouse=True)
def login_falso():
    """O robô entra no simulador com o login FALSO dele, num cofre só de memória."""
    from nucleo.credenciais import Cofre, CofreMemoria
    CofreMemoria.esvaziar()
    Cofre("amil", memoria=True).guardar(usuario=Simulador.USUARIO, senha=Simulador.SENHA)
    yield
    CofreMemoria.esvaziar()


def _pedido(**campos):
    base = {c: "" for c in COLUNAS}
    base.update({f"vidas_{f}": 0 for f in FAIXAS})
    base.update(campos)
    return [base[c] for c in COLUNAS]


def _preparar(tmp_path, sim, linhas, monkeypatch, liberada=True, **extra):
    monkeypatch.chdir(tmp_path)
    secao = {"urls": {"login": sim.url_login, "home": sim.url_home},
             "tempos": {"timeout_login_ms": 20000, "timeout_tela_ms": 15000, "timeout_emissao_ms": 20000,
                        "timeout_download_ms": 15000},
             "emissao_liberada": liberada}
    secao.update(extra)
    cfg = {"geral": {"pasta_saida": "saida", "modo_visual": False, "lentidao_ms": 0, "pausa_entre_pedidos_s": 0},
           "teste": {"cofre": "memoria"}, "operadoras": {"amil": secao}}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    wb = Workbook()
    ws = wb.active
    ws.append(COLUNAS)
    for linha in linhas:
        ws.append(linha)
    wb.save(tmp_path / "cotacoes.xlsx")


def _rodar(*extra):
    import main
    return main.main(["--config", "config.yaml", "--operadora", "amil", "--planilha", "cotacoes.xlsx", *extra])


def _resultados(tmp_path, aba="cotacoes"):
    ws = load_workbook(tmp_path / "saida" / "amil" / "resultados.xlsx")[aba]
    linhas = list(ws.iter_rows(values_only=True))
    return [dict(zip(linhas[0], linha)) for linha in linhas[1:]]


def _estado(tmp_path):
    return json.loads((tmp_path / "saida" / "amil" / "estado.json").read_text(encoding="utf-8"))


def _logs(tmp_path) -> str:
    return "".join(p.read_text(encoding="utf-8") for p in sorted((tmp_path / "saida" / "amil" / "logs").glob("*.log")))


def _nada_proibido(sim):
    """O robô NUNCA clica em Criar Proposta, + Incluir Plano Médico nem Enviar por E-mail."""
    assert (sim.criar_proposta_cliques, sim.incluir_plano_medico_cliques, sim.enviar_email_cliques) == (0, 0, 0)


def _sessao(tmp_path, pw, ensaio=False, parar=None, avisar=None, reemitir=(), pedir_codigo=None):
    import operadoras
    from nucleo.estado import Estado
    from nucleo.navegador import Mapeador, abrir
    from nucleo.registro import carregar_config, configurar_log

    op = operadoras.obter("amil")
    cfg = op.config(carregar_config(tmp_path / "config.yaml"))
    pasta = tmp_path / "saida" / "amil"
    log = configurar_log(pasta / "logs")
    contexto, page = abrir(pw, cfg)
    s = op.nova_sessao(cfg, log, contexto, page, Estado(pasta / "estado.json"),
                       op.resultados(pasta / "resultados.xlsx", log), Mapeador(pasta, False, log), ensaio,
                       avisar=avisar, parar=parar, pedir_codigo=pedir_codigo, reemitir=reemitir)
    pedidos, _ = op.ler_planilha(tmp_path / "cotacoes.xlsx", cfg)
    return op, s, contexto, pedidos


# ------------------------------------------------------------------------------------------------ ensaio

def test_ensaio_cria_a_oportunidade_e_a_cotacao_e_para_em_revisar(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--ensaio") == 0
    [o] = sim.oportunidades.values()
    [c] = sim.cotacoes.values()
    assert (o["opp"], c["cot"], c["status"], c["etapa"]) == ("OPP-5147302", "COT-5185118", "Em Digitação", "revisar")
    assert sim.cotacoes_concluidas == [] and sim.downloads == 0
    [r] = _resultados(tmp_path)
    assert (r["plano"], r["status"], r["protocolo"]) == ("PLATINUM R1 COPART", "ENSAIO_OK", "COT-5185118")
    # valores do vídeo: 4 vidas, Platinum (a tela mostra o valor por mês a partir da 3ª parcela; o resto vai no log)
    assert (r["preco_mensal"], r["total_sem_iof"], r["total_com_iof"]) == (4769.0, None, 4769.0)
    assert "1ª e 2ª parcelas 2384.50 (50%), após 12 meses 4827.00" in _logs(tmp_path)
    assert "já foram criadas no portal" in r["erro"]
    logs = _logs(tmp_path)
    assert "ENSAIO na Amil" in logs and "Grade conferida: 4 vida(s), Valor Total 4769.00" in logs
    # o registro guarda a OPP (conhecida) e a COT em digitação (não bloqueia)
    status = {i["plano"]: (i["status"], i["protocolo"]) for i in _estado(tmp_path)["itens"].values()}
    assert status == {"Oportunidade": ("pdf_ok", "OPP-5147302"), "PLATINUM R1 COPART": ("digitando", "COT-5185118")}
    _nada_proibido(sim)


# ------------------------------------------------------------------------------------------------ 3 planos, 1 oportunidade

def test_tres_planos_na_mesma_oportunidade_com_pdf_e_valores_do_video(tmp_path, sim, monkeypatch):
    cliente = tmp_path / "cliente"
    cliente.mkdir()
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, planos=TRES_PLANOS, pasta_destino=str(cliente)))], monkeypatch)
    assert _rodar("--confirmar") == 0
    assert len(sim.oportunidades) == 1 and len(sim.cotacoes) == 3 and len(sim.cotacoes_concluidas) == 3
    assert sim.downloads == 3
    rs = _resultados(tmp_path)
    assert [(r["plano"], r["status"]) for r in rs] == [("PLATINUM R1 COPART", "OK"), ("AMIL BLACK I R1 COPART", "OK"),
                                                       ("AMIL S2500 R1 QP COPART", "OK")]
    # Seção 3 do mapa: o valor por mês de cada plano (o Total Geral da 1ª e 2ª parcelas e o total após 12 meses estão no log)
    assert [r["total_com_iof"] for r in rs] == [4769.0, 8453.1, 8847.02]
    logs = _logs(tmp_path)
    for esperado in ("1ª e 2ª parcelas 2384.50 (50%), após 12 meses 4827.00", "1ª e 2ª parcelas 4226.55 (50%), após 12 meses 8511.10",
                     "Total Geral 8847.02, após 12 meses 8905.02"):
        assert esperado in logs
    assert sorted(p.name for p in cliente.glob("*.pdf")) == ["AMIL BLACK PADARIA.pdf", "AMIL PLATINUM PADARIA.pdf",
                                                             "AMIL S2500 PADARIA.pdf"]
    mortos = sorted(p.name for p in (tmp_path / "saida" / "amil" / "pdfs").glob("*.pdf"))
    assert mortos == [f"AMIL_11222333000181_{c['cot']}.pdf" for c in sorted(sim.cotacoes.values(), key=lambda c: c["cot"])]
    assert all(p.read_bytes().startswith(b"%PDF") for p in cliente.glob("*.pdf"))
    status = {i["plano"]: i["status"] for i in _estado(tmp_path)["itens"].values()}
    assert set(status.values()) == {"pdf_ok"} and len(status) == 4
    _nada_proibido(sim)


def test_oportunidade_conhecida_e_reaberta_nao_recriada(tmp_path, sim, monkeypatch):
    """Outro plano da mesma empresa, em outro pedido: a oportunidade do registro é reaberta, só a cotação nova é criada."""
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--confirmar") == 0
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, planos="AMIL BLACK I R1 COPART"))], monkeypatch)
    assert _rodar("--confirmar") == 0
    assert len(sim.oportunidades) == 1 and len(sim.cotacoes) == 2 and sim.downloads == 2
    assert "Abrindo a oportunidade OPP-5147302 (já existe no registro)" in _logs(tmp_path)
    _nada_proibido(sim)


# ------------------------------------------------------------------------------------------------ pedir de novo

def test_pedir_de_novo_nao_duplica_e_emitir_de_novo_cria_so_uma_cotacao_nova(tmp_path, sim, monkeypatch):
    from playwright.sync_api import sync_playwright

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    assert _rodar("--confirmar") == 0
    assert _rodar("--confirmar") == 0                                   # a mesma planilha: nada é criado
    assert len(sim.oportunidades) == 1 and len(sim.cotacoes) == 1 and sim.downloads == 1
    assert [r["status"] for r in _resultados(tmp_path)] == ["OK", "PULADO"]
    # "Emitir de novo mesmo assim" (o corretor viu o COT no aviso): uma COT nova na MESMA oportunidade
    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, reemitir=["COT-5185118"])
        try:
            op.login(s)
            op.processar(s, p)
        finally:
            contexto.close()
    assert len(sim.oportunidades) == 1 and len(sim.cotacoes) == 2 and len(sim.cotacoes_concluidas) == 2
    estado = _estado(tmp_path)
    assert [x["item"]["protocolo"] for x in estado["reemitidos"]] == ["COT-5185118"]
    assert sorted(i["protocolo"] for i in estado["itens"].values() if i["plano"] != "Oportunidade") == ["COT-5185125"]
    _nada_proibido(sim)


# ------------------------------------------------------------------------------------------------ queda depois de concluir

def test_queda_depois_de_concluir_cotacao_recupera_o_pdf_sem_criar_outra(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.cair_depois_de_concluir = True
    assert _rodar("--confirmar") == 3
    [r] = _resultados(tmp_path)
    assert r["status"] == "VERIFICAR" and "reabre" in r["erro"]
    assert len(sim.cotacoes) == 1 and len(sim.cotacoes_concluidas) == 1 and sim.downloads == 0
    status = {i["plano"]: i["status"] for i in _estado(tmp_path)["itens"].values()}
    assert status["PLATINUM R1 COPART"] == "emitindo"
    sim.cair_depois_de_concluir = False
    assert _rodar("--confirmar") == 0                                   # reabre a COT e baixa o PDF
    assert len(sim.oportunidades) == 1 and len(sim.cotacoes) == 1 and sim.downloads == 1
    ultimo = _resultados(tmp_path)[-1]
    assert (ultimo["status"], ultimo["protocolo"]) == ("OK", "COT-5185118")
    assert (tmp_path / "saida" / "amil" / "pdfs" / "AMIL_11222333000181_COT-5185118.pdf").read_bytes().startswith(b"%PDF")
    assert "Recuperando a cotação COT-5185118" in _logs(tmp_path)
    assert {i["status"] for i in _estado(tmp_path)["itens"].values()} == {"pdf_ok"}
    _nada_proibido(sim)


# ------------------------------------------------------------------------------------------------ código de verificação

def test_codigo_de_login_e_pedido_pela_nossa_tela_e_a_sessao_fica_no_perfil(tmp_path, sim, monkeypatch):
    from playwright.sync_api import sync_playwright

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.exigir_codigo = True
    perguntas = []

    def pedir(texto=""):
        perguntas.append(texto)
        return sim.CODIGO

    monkeypatch.setattr("builtins.input", pedir)
    assert _rodar("--ensaio") == 0                                      # a linha de comando pergunta no terminal
    assert len(perguntas) == 1 and sim.codigos_digitados == [sim.CODIGO]
    logs = _logs(tmp_path)
    assert "pedindo na tela do Newport" in logs and "Login feito (com código de verificação)" in logs
    assert sim.CODIGO not in logs and sim.SENHA not in logs and sim.USUARIO not in logs      # nada digitado no log
    portal = json.loads((tmp_path / "saida" / "amil" / "portal.json").read_text(encoding="utf-8"))
    assert portal["sessao_login_em"] and portal["sessao_viva_em"]
    assert sim.CODIGO not in json.dumps(portal) and sim.SENHA not in json.dumps(portal)
    # A linha de comando sai do portal no fim (o portal esquece a sessão): o próximo login pede outro código, e o log diz
    # quanto a sessão anterior durou.
    assert _rodar("--ensaio") == 0
    assert len(perguntas) == 2 and "A sessão anterior durou de" in _logs(tmp_path)
    # Sem sair (a tela fica logada entre pedidos): a sessão fica no perfil do navegador e o portal não pede código de novo.
    codigos = []

    def codigo_da_tela():
        codigos.append(1)
        return sim.CODIGO

    for _ in range(2):
        with sync_playwright() as pw:
            op, s, contexto, _pedidos = _sessao(tmp_path, pw, ensaio=True, pedir_codigo=codigo_da_tela)
            try:
                op.login(s)
            finally:
                contexto.close()                                        # fecha o navegador sem sair do portal
    assert len(codigos) == 1                                            # só o 1º login (a sessão expirou ao sair) pediu código
    assert "Sessão do portal aberta: não precisa entrar de novo (login feito há" in _logs(tmp_path)
    # a sessão cai no portal (expira): novo login e novo código; a duração medida fica no portal.json
    sim.expirar()
    with sync_playwright() as pw:
        op, s, contexto, _pedidos = _sessao(tmp_path, pw, ensaio=True, pedir_codigo=codigo_da_tela)
        try:
            op.login(s)
        finally:
            contexto.close()
    assert len(codigos) == 2
    duracoes = json.loads((tmp_path / "saida" / "amil" / "portal.json").read_text(encoding="utf-8"))["sessao_duracoes_min"]
    assert len(duracoes) >= 2


def test_codigo_nao_digitado_para_o_login_com_frase_fixa(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.exigir_codigo = True
    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert _rodar("--ensaio") != 0
    assert sim.oportunidades == {} and sim.codigos_digitados == []


# ------------------------------------------------------------------------------------------------ parar e continuar

def test_parar_entre_telas_e_continuar_a_mesma_cotacao(tmp_path, sim, monkeypatch):
    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Parado

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    pedir = {"parar": False}

    def avisar(tipo, **dados):
        if tipo == "etapa" and dados.get("etapa") == "planos":
            pedir["parar"] = True                                       # o corretor clica em Parar na tela dos planos

    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, parar=lambda: pedir["parar"], avisar=avisar)
        try:
            op.login(s)
            with pytest.raises(Parado):
                op.processar(s, p)
        finally:
            contexto.close()
    assert len(sim.oportunidades) == 1 and len(sim.cotacoes) == 1 and sim.cotacoes_concluidas == []
    assert [r["status"] for r in _resultados(tmp_path)] == ["PARADO"]
    status = {i["plano"]: i["status"] for i in _estado(tmp_path)["itens"].values()}
    assert status == {"Oportunidade": "pdf_ok", "PLATINUM R1 COPART": "digitando"}
    assert _rodar("--confirmar") == 0                                   # continuar: reabre a oportunidade e a MESMA cotação
    assert len(sim.oportunidades) == 1 and len(sim.cotacoes) == 1 and sim.downloads == 1
    assert _resultados(tmp_path)[-1]["status"] == "OK"
    assert "Continuando a cotação COT-5185118" in _logs(tmp_path)
    _nada_proibido(sim)


def test_parar_durante_gerando_pdf_vale_depois_de_3_s_e_a_proxima_execucao_baixa_o_pdf(tmp_path, sim, monkeypatch):
    """O portal demora a gerar o PDF: Parar vale (depois de 3 s) e deixa a COT "emitindo"; depois o robô reabre e baixa."""
    from playwright.sync_api import sync_playwright

    from nucleo.navegador import Parado

    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.pdf_demora_s = 30
    pedir = {"parar": False}

    def avisar(tipo, **dados):
        if tipo == "etapa" and dados.get("etapa") == "concluir":
            pedir["parar"] = True

    with sync_playwright() as pw:
        op, s, contexto, [p] = _sessao(tmp_path, pw, parar=lambda: pedir["parar"], avisar=avisar)
        try:
            op.login(s)
            with pytest.raises(Parado):
                op.processar(s, p)
        finally:
            contexto.close()
    status = {i["plano"]: i["status"] for i in _estado(tmp_path)["itens"].values()}
    assert status["PLATINUM R1 COPART"] == "emitida" and len(sim.cotacoes) == 1
    sim.pdf_demora_s = 0.5
    assert _rodar("--confirmar") == 0
    assert len(sim.cotacoes) == 1 and sim.downloads == 1 and _resultados(tmp_path)[-1]["status"] == "OK"


# ------------------------------------------------------------------------------------------------ falha fechada

def test_plano_que_nao_esta_na_lista_para_e_mostra_os_nomes_que_viu(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**dict(PEDIDO_VIDEO, planos="PLANO QUE NAO EXISTE"))], monkeypatch)
    assert _rodar("--confirmar") != 0
    [r] = _resultados(tmp_path)
    assert r["status"] == "ERRO" and "PLATINUM R1 COPART" in r["erro"] and "Nomes que o robô viu" in r["erro"]
    assert sim.cotacoes_concluidas == []
    _nada_proibido(sim)


def test_valor_que_nao_confere_para_antes_de_concluir_cotacao(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.total_geral_errado = True                                       # o Total Geral da revisão não é a metade
    assert _rodar("--confirmar") != 0
    [r] = _resultados(tmp_path)
    assert r["status"] == "ERRO" and "Total Geral" in r["erro"] and "50%" in r["erro"]
    assert sim.cotacoes_concluidas == [] and sim.downloads == 0
    _nada_proibido(sim)


def test_sem_emissao_liberada_so_o_ensaio_roda_e_nada_e_feito_no_portal(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch, liberada=False)
    assert _rodar("--confirmar") != 0
    assert sim.oportunidades == {} and sim.cotacoes == {}
    assert _resultados(tmp_path)[0]["etapa_erro"] == "calibragem"
    assert _rodar("--ensaio") == 0 and len(sim.cotacoes) == 1


def test_dental_que_o_portal_nao_traz_marcado_e_marcado_e_conferido(tmp_path, sim, monkeypatch):
    _preparar(tmp_path, sim, [_pedido(**PEDIDO_VIDEO)], monkeypatch)
    sim.dental_vem_marcado = False
    assert _rodar("--confirmar") == 0
    [c] = sim.cotacoes.values()
    assert c["dental"] is True and c["totais"]["apos_12"] == 4827
    assert "Dental: desmarcado no portal; pedido: aderir" in _logs(tmp_path)
