/** Fixture de GET /api/operadoras — espelho da SulAmérica, sem PII. */

export const OPERADORA_SULAMERICA = {
  id: "sulamerica",
  nome: "SulAmérica",
  produto: "Cotação PME (3 a 29 vidas)",
  cor: "#E8651D",
  marcada: true,
  min_vidas: 3,
  max_vidas: 29,
  faixas_idade_exata: ["0 - 18", "59+"],
  etapas: [
    { id: "login", nome: "Login" },
    { id: "modulos", nome: "Módulo PME" },
    { id: "dados_empresa", nome: "Empresa" },
    { id: "cuidado_360", nome: "Cuidado 360°" },
    { id: "congenere", nome: "Operadora atual" },
    { id: "vidas", nome: "Vidas" },
    { id: "idades", nome: "Idades" },
    { id: "planos", nome: "Planos" },
    { id: "comparacao", nome: "Comparação" },
    { id: "resumo", nome: "Resumo" },
    { id: "emitida", nome: "PDF" },
  ],
  campos: [
    {
      chave: "seguro_novo",
      titulo: "Plano atual",
      rotulo: "A empresa não tem plano de saúde hoje",
      tipo: "sim_nao",
      padrao: "nao",
      empresa: true,
    },
    {
      chave: "congenere_atual",
      rotulo: "Operadora atual",
      tipo: "sugestoes",
      opcoes: ["NOTREDAME"],
      visivel_se: { seguro_novo: "nao" },
      empresa: true,
      ajuda: "Como aparece na lista do portal (ex.: NOTREDAME).",
    },
    {
      chave: "cuidado_360",
      titulo: "Cuidado 360°",
      rotulo: "Incluir na cotação",
      tipo: "sim_nao",
      padrao: "sim",
      robo: true,
      ajuda: "Odonto e vida sem custo adicional. Incluído, o robô aceita os termos do Cuidado 360° no portal.",
    },
    {
      chave: "tipo_contratacao",
      rotulo: "Tipo de contratação",
      tipo: "escolha",
      robo: true,
      opcoes: [
        ["cbo", "CBO"],
        ["compulsoria", "Compulsória"],
        ["flex", "Flex"],
      ],
      padrao: "compulsoria",
    },
    {
      chave: "vigencia_meses",
      rotulo: "Vigência contratual",
      tipo: "escolha",
      robo: true,
      opcoes: [
        ["12", "12 meses"],
        ["24", "24 meses"],
      ],
      padrao: "24",
    },
    {
      chave: "coparticipacao",
      rotulo: "Coparticipação",
      tipo: "escolha",
      robo: true,
      opcoes: [
        ["sem", "Sem coparticipação"],
        ["com", "Com coparticipação"],
        ["as_duas", "Com e sem", "com e sem coparticipação (2 cotações por plano)"],
      ],
      padrao: "as_duas",
      multiplica: { as_duas: 2 },
      ajuda: "Com e sem: duas cotações por plano, cada uma com o seu protocolo e o seu PDF.",
    },
  ],
  planos: [
    { nome: "Direto Nacional", acomodacao: "Enfermaria", visto_no_portal: true },
    { nome: "Especial Mais", acomodacao: "Apartamento", visto_no_portal: true },
  ],
  versoes: { com: "com coparticipação", sem: "sem coparticipação" },
  textos: {
    nome_pdf: "SULAMERICA <PLANO>.pdf",
    planos:
      "Cada plano vira uma cotação e um PDF (com “Com e sem” coparticipação, duas). A lista cresce sozinha com os planos que o robô encontrar no portal.",
    aguardando_portal: "O portal ainda tem uma sessão aberta para este CPF (outro navegador ou uma janela fechada). ",
  },
  menor_preco_padrao: 1,
  planos_modo_padrao: "lista",
  produto_portal: "557 - AHO",
  planos_padrao: ["Especial Mais | Apartamento"],
  conexao: "desconectado",
  login: { guardadas: true, recusadas: false },
};

export const OPERADORAS = [OPERADORA_SULAMERICA];

/** CNPJ válido de teste (dígitos verificadores ok, sem empresa real). */
export const CNPJ_OK = "11444777000161";
