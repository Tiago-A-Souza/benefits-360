import { Component } from "react";
import TelaErro from "./TelaErro";
import { registrarErro } from "./registrarErro";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { quebrado: false };
  }

  static getDerivedStateFromError() {
    return { quebrado: true };
  }

  componentDidCatch(erro) {
    registrarErro(erro, {
      rota: this.props.rota,
      componente: this.props.contexto || this.props.componente || "ErrorBoundary",
    });
  }

  componentDidUpdate(prev) {
    if (this.state.quebrado && prev.resetKey !== this.props.resetKey) {
      this.setState({ quebrado: false });
    }
  }

  tentar = () => {
    this.setState({ quebrado: false });
    this.props.onTentar?.();
  };

  voltar = () => {
    this.setState({ quebrado: false });
    if (this.props.onVoltarEstudos) this.props.onVoltarEstudos();
    else if (typeof window !== "undefined") window.location.assign(window.location.pathname || "/");
  };

  render() {
    if (!this.state.quebrado) return this.props.children;
    return (
      <TelaErro
        modo={this.props.modo || "pagina"}
        contexto={this.props.contexto}
        onTentar={this.tentar}
        onVoltarEstudos={this.voltar}
        onSair={this.props.onSair}
      />
    );
  }
}
