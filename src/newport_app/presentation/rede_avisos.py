"""Textos de aviso — aba Rede quando falta localização na base importada."""

AVISO_REDE_SEM_LOCALIZACAO = (
    "A base importada não traz UF e cidade dos beneficiários. "
    "O recorte da rede credenciada depende dessa localização. "
    "Reimporte a posição cadastral com as colunas UF e CIDADE e gere o documento de novo."
)

AVISO_REDE_SECAO_SEM_LOCALIZACAO = (
    "Nenhum prestador neste grupo — falta UF e cidade dos beneficiários na base importada. "
    "Reimporte a posição cadastral com as colunas UF e CIDADE e gere o documento de novo."
)
