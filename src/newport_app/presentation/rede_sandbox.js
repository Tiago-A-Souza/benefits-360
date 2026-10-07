(function () {
  "use strict";

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $$(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function readState() {
    var el = $("#newport-rede-state");
    if (!el || !el.textContent) return { v: 1, mode: "edit", excluded: [] };
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return { v: 1, mode: "edit", excluded: [] };
    }
  }

  function writeState(state) {
    var el = $("#newport-rede-state");
    if (el) el.textContent = JSON.stringify(state);
  }

  async function sha256Hex(text) {
    var buf = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(text)
    );
    return Array.from(new Uint8Array(buf))
      .map(function (b) {
        return b.toString(16).padStart(2, "0");
      })
      .join("");
  }

  function rowId(tr) {
    return tr.getAttribute("data-rede-id") || "";
  }

  function isRowIncluded(tr, state) {
    var id = rowId(tr);
    return state.excluded.indexOf(id) < 0;
  }

  function recalcBlock(table, blocoTr) {
    var rows = [];
    var node = blocoTr.nextElementSibling;
    while (node && !node.classList.contains("bloco-rede")) {
      if (node.classList.contains("p-rede") && node.style.display !== "none") {
        if (!node.classList.contains("rede-row-out")) rows.push(node);
      }
      node = node.nextElementSibling;
    }
    var contTr = null;
    node = blocoTr.nextElementSibling;
    while (node && !node.classList.contains("bloco-rede")) {
      if (node.classList.contains("cont-rede")) {
        contTr = node;
        break;
      }
      node = node.nextElementSibling;
    }
    if (!contTr) return;
    var cols = $$("thead th", table).length - 1;
    var tds = $$("td", contTr);
    for (var c = 1; c < tds.length && c <= cols; c++) {
      var n = 0;
      for (var r = 0; r < rows.length; r++) {
        var cells = $$("td", rows[r]);
        if (cells[c] && cells[c].classList.contains("on")) n++;
      }
      tds[c].textContent = String(n);
    }
    var q = $(".q", blocoTr);
    if (q) q.textContent = rows.length + " prestadores";
  }

  function recalcAll(root) {
    $$(".tabela-rede", root).forEach(function (table) {
      $$("tr.bloco-rede", table).forEach(function (bl) {
        recalcBlock(table, bl);
      });
    });
  }

  function updateCounter(root, state) {
    var el = $("#rede-contador-marcados", root);
    if (!el) return;
    var n = 0;
    $$("tr.p-rede", root).forEach(function (tr) {
      if (tr.classList.contains("rede-row-out")) return;
      if (!isRowIncluded(tr, state)) return;
      var cb = $("input[type=checkbox]", tr);
      if (cb && cb.checked) n++;
    });
    el.textContent = n + " prestador(es) marcado(s)";
  }

  function applyExcluded(root, state) {
    $$("tr.p-rede", root).forEach(function (tr) {
      var out = !isRowIncluded(tr, state);
      tr.classList.toggle("rede-row-out", out);
      if (state.mode === "final") {
        tr.style.display = out ? "none" : "";
      }
    });
    recalcAll(root);
    updateCounter(root, state);
  }

  function setModeUi(root, state) {
    var bar = $(".rede-sandbox-bar", root);
    var foot = $(".rede-sandbox-foot", root);
    var btnEdit = $("#rede-btn-editar", root);
    var jsOnly = $$(".rede-sandbox-js-only", root);
    if (state.mode === "final") {
      if (bar) bar.hidden = true;
      jsOnly.forEach(function (el) {
        if (el.classList.contains("rede-sandbox-check")) return;
        if (el === bar || el.closest(".rede-sandbox-bar")) el.hidden = true;
      });
      $$(".rede-sandbox-check", root).forEach(function (td) {
        td.hidden = true;
      });
      $$("th.rede-sandbox-check", root).forEach(function (th) {
        th.hidden = true;
      });
      if (btnEdit) btnEdit.hidden = false;
      root.classList.add("rede-sandbox-final");
    } else {
      if (bar) bar.hidden = false;
      if (btnEdit) btnEdit.hidden = true;
      root.classList.remove("rede-sandbox-final");
      $$(".rede-sandbox-check", root).forEach(function (td) {
        td.hidden = false;
      });
      $$("th.rede-sandbox-check", root).forEach(function (th) {
        th.hidden = false;
      });
    }
  }

  function applyFilters(root) {
    var zona = ($("#rede-filtro-zona", root) || {}).value || "";
    var mun = ($("#rede-filtro-mun", root) || {}).value || "";
    var nome = (($("#rede-filtro-nome", root) || {}).value || "").toLowerCase();
    $$("tr.p-rede", root).forEach(function (tr) {
      if (tr.classList.contains("rede-row-out")) return;
      var z = tr.getAttribute("data-zona") || "";
      var m = tr.getAttribute("data-municipio") || "";
      var p = tr.getAttribute("data-nome") || "";
      var ok =
        (!zona || z === zona) &&
        (!mun || m === mun) &&
        (!nome || p.indexOf(nome) >= 0);
      tr.classList.toggle("rede-filter-hide", !ok);
      tr.style.display = ok ? "" : "none";
    });
    recalcAll(root);
    updateCounter(root, readState());
  }

  function fillFilterOptions(root) {
    var zonas = new Set();
    var muns = new Set();
    $$("tr.p-rede", root).forEach(function (tr) {
      var z = tr.getAttribute("data-zona");
      var m = tr.getAttribute("data-municipio");
      if (z) zonas.add(z);
      if (m) muns.add(m);
    });
    var selZ = $("#rede-filtro-zona", root);
    var selM = $("#rede-filtro-mun", root);
    if (selZ) {
      Array.from(zonas)
        .sort()
        .forEach(function (z) {
          var o = document.createElement("option");
          o.value = z;
          o.textContent = z;
          selZ.appendChild(o);
        });
    }
    if (selM) {
      Array.from(muns)
        .sort()
        .forEach(function (m) {
          var o = document.createElement("option");
          o.value = m;
          o.textContent = m;
          selM.appendChild(o);
        });
    }
  }

  function collectExcluded(root) {
    var ex = [];
    $$("tr.p-rede", root).forEach(function (tr) {
      var cb = $("input[type=checkbox]", tr);
      if (cb && !cb.checked) ex.push(rowId(tr));
    });
    return ex;
  }

  function clientDownloadName(root) {
    var nome =
      root.getAttribute("data-arquivo-cliente") ||
      root.getAttribute("data-arquivo-origem") ||
      "apresentacao_completo_para_cliente.html";
    return nome.replace(/^.*[/\\]/, "");
  }

  function showDownloadNotice(root, fileName) {
    var aviso = $("#rede-aviso-download", root);
    if (!aviso) return;
    aviso.innerHTML =
      "<strong>Envie ao cliente o arquivo que acabou de ser baixado:</strong> " +
      "<code>" +
      fileName +
      "</code>. " +
      "Não envie o arquivo que você estava editando nesta aba do navegador.";
    aviso.hidden = false;
  }

  function ajustarColspanAposRemoverIncl(root) {
    root.querySelectorAll("tr.bloco-rede td[colspan]").forEach(function (td) {
      var n = parseInt(td.getAttribute("colspan") || "1", 10);
      if (n > 1) td.setAttribute("colspan", String(n - 1));
    });
    // Cobertos: colspan 2 = Incl. + prestador; sem Incl. o rótulo ocupa só prestador.
    root.querySelectorAll("tr.cont-rede").forEach(function (tr) {
      var first = tr.querySelector("td");
      if (first) first.setAttribute("colspan", "1");
    });
  }

  function prepareDocumentoCliente(docEl, state) {
    var st = docEl.querySelector("#newport-rede-state");
    if (st) st.textContent = JSON.stringify(state);
    var root = docEl.querySelector(".rede-sandbox");
    if (!root) return;
    root.classList.add("rede-sandbox-no-js", "rede-sandbox-cliente");
    root.classList.remove("rede-sandbox-final");
    root.querySelectorAll(".rede-sandbox-bar, .rede-sandbox-foot").forEach(
      function (el) {
        el.remove();
      }
    );
    var aviso = $("#rede-aviso-download", root);
    if (aviso) aviso.remove();
    root.querySelectorAll("script").forEach(function (s) {
      if (s.getAttribute("type") === "application/json") return;
      s.remove();
    });
    root.querySelectorAll("th.rede-sandbox-check, td.rede-sandbox-check").forEach(
      function (el) {
        el.remove();
      }
    );
    root.querySelectorAll("button.rede-marcar-bloco").forEach(function (el) {
      el.remove();
    });
    ajustarColspanAposRemoverIncl(root);
    var excluded = state.excluded || [];
    $$("tr.p-rede", root).forEach(function (tr) {
      tr.classList.remove("rede-filter-hide");
      tr.style.display = "";
      if (excluded.indexOf(rowId(tr)) >= 0) tr.remove();
    });
  }

  function downloadHtml(root, state) {
    writeState(state);
    var docEl = document.documentElement.cloneNode(true);
    prepareDocumentoCliente(docEl, state);
    var html = "<!DOCTYPE html>\n" + docEl.outerHTML;
    var blob = new Blob([html], { type: "text/html;charset=utf-8" });
    var fileName = clientDownloadName(root);
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
    }, 500);
    showDownloadNotice(root, fileName);
  }

  function wireBlockToggle(root) {
    $$("button.rede-marcar-bloco", root).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var on = btn.getAttribute("data-checked") !== "1";
        btn.setAttribute("data-checked", on ? "1" : "0");
        btn.textContent = on ? "Desmarcar bloco" : "Marcar bloco";
        var tr = btn.closest("tr");
        var table = btn.closest("table");
        if (!tr || !table) return;
        var node = tr.nextElementSibling;
        while (node && !node.classList.contains("bloco-rede")) {
          if (node.classList.contains("p-rede") && !node.classList.contains("rede-row-out")) {
            var cb = $("input[type=checkbox]", node);
            if (cb) cb.checked = on;
          }
          node = node.nextElementSibling;
        }
        updateCounter(root, readState());
      });
    });
  }

  function init() {
    var root = $(".rede-sandbox");
    if (!root) return;
    root.classList.remove("rede-sandbox-no-js");
    var state = readState();
    fillFilterOptions(root);
    wireBlockToggle(root);
    applyExcluded(root, state);
    setModeUi(root, state);

    $$("tr.p-rede input[type=checkbox]", root).forEach(function (cb) {
      cb.addEventListener("change", function () {
        updateCounter(root, readState());
      });
    });

    var fz = $("#rede-filtro-zona", root);
    var fm = $("#rede-filtro-mun", root);
    var fn = $("#rede-filtro-nome", root);
    if (fz) fz.addEventListener("change", function () {
      applyFilters(root);
    });
    if (fm) fm.addEventListener("change", function () {
      applyFilters(root);
    });
    if (fn) fn.addEventListener("input", function () {
      applyFilters(root);
    });

    var btnOk = $("#rede-btn-confirmar", root);
    if (btnOk) {
      btnOk.addEventListener("click", function () {
        state.mode = "final";
        state.excluded = collectExcluded(root);
        applyExcluded(root, state);
        setModeUi(root, state);
        $$("tr.p-rede", root).forEach(function (tr) {
          if (tr.classList.contains("rede-filter-hide")) {
            tr.classList.remove("rede-filter-hide");
          }
        });
        applyExcluded(root, state);
        downloadHtml(root, state);
      });
    }

    var btnEdit = $("#rede-btn-editar", root);
    if (btnEdit) {
      btnEdit.addEventListener("click", async function () {
        var typed = window.prompt("Informe o ID do estudo:");
        if (typed === null) return;
        var expect = root.getAttribute("data-unlock") || "";
        var got = await sha256Hex(typed.trim());
        if (got !== expect) {
          window.alert("ID incorreto.");
          return;
        }
        state.mode = "edit";
        writeState(state);
        setModeUi(root, state);
        applyExcluded(root, state);
        applyFilters(root);
      });
    }

    updateCounter(root, state);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
