/** Normaliza respostas da API/robô para o render nunca receber null no lugar de lista. */

export function asArray(valor) {
  if (Array.isArray(valor)) return valor;
  if (valor && typeof valor === "object") {
    if (Array.isArray(valor.estudos)) return valor.estudos;
    if (Array.isArray(valor.itens)) return valor.itens;
    if (Array.isArray(valor.operadoras)) return valor.operadoras;
    if (Array.isArray(valor.pendencias)) return valor.pendencias;
    if (Array.isArray(valor.extracoes)) return valor.extracoes;
    if (Array.isArray(valor.telas)) return valor.telas;
    if (Array.isArray(valor.planos)) return valor.planos;
  }
  return [];
}

export function asObject(valor) {
  if (valor && typeof valor === "object" && !Array.isArray(valor)) return valor;
  return {};
}

export function camposDaOperadora(op) {
  return asArray(op && op.campos);
}

export function etapasDaOperadora(op) {
  return asArray(op && op.etapas);
}
