/*
 * Dashboard de la microrred de Amalfi (OT-0006).
 *
 * Alpine.js maneja el estado de la interfaz (pestaña, rango, datos); los gráficos de Chart.js
 * viven fuera de Alpine porque un Proxy reactivo sobre una instancia de Chart la rompe.
 * Un gráfico se crea la primera vez que su pestaña es visible (un canvas dentro de un
 * contenedor oculto mide 0 px) y después sólo se actualiza.
 */
(() => {
  "use strict";

  // Sin Chart.js (CDN inaccesible) no hay nada que dibujar: base.html muestra el aviso y aquí
  // se retira el componente antes de que Alpine lo recorra, para no llenar la consola de
  // errores de expresiones sin componente.
  if (!window.Chart) {
    document.addEventListener("alpine:init", () => {
      document.querySelectorAll("[x-data]").forEach((raiz) => raiz.removeAttribute("x-data"));
    });
    return;
  }

  // ── Tokens de color (CLAUDE.md §3; combinaciones validadas con validate_palette.js) ──────
  const C = {
    generacion: "#059669", // esmeralda
    demanda: "#4f46e5", // índigo
    soc: "#0284c7", // cielo
    irradiancia: "#d97706", // ámbar
    tempAmbiente: "#0284c7",
    tempPanel: "#ea580c",
    prediccion: "#64748b", // pizarra, siempre discontinua: la línea no depende sólo del color
    anomalia: "#dc2626", // rojo: crítico / anomalía
    carga: "#059669",
    descarga: "#4f46e5",
    flujoPositivo: "#059669",
    flujoNegativo: "#64748b",
    acumulado: "#4f46e5",
    segmentos: {
      RESIDENCIAL: "#4f46e5",
      PRODUCTIVO: "#0d9488",
      COMUNITARIO: "#ea580c",
      ALUMBRADO: "#db2777",
    },
    bandaOptimo: "rgba(5, 150, 105, 0.07)",
    bandaAlerta: "rgba(217, 119, 6, 0.10)",
    bandaCritico: "rgba(220, 38, 38, 0.08)",
    reserva: "#dc2626",
    rejilla: "#e2e8f0",
    eje: "#94a3b8",
    tinta: "#64748b",
    tintaFuerte: "#0f172a",
    superficie: "#ffffff",
    fondoRotulo: "rgba(255, 255, 255, 0.85)",
  };
  const SEGMENTOS = ["RESIDENCIAL", "PRODUCTIVO", "COMUNITARIO", "ALUMBRADO"];
  const NOMBRE_SEGMENTO = {
    RESIDENCIAL: "Residencial",
    PRODUCTIVO: "Productivo",
    COMUNITARIO: "Comunitario",
    ALUMBRADO: "Alumbrado público",
  };
  const NOMBRE_ANOMALIA = {
    FALLA_INVERSOR: "Falla de inversor",
    SOMBREADO_PARCIAL: "Sombreado parcial",
    PICO_CONSUMO: "Pico de consumo",
    CONSUMO_NOCTURNO_ATIPICO: "Consumo nocturno atípico",
    GENERACION_ATIPICA: "Generación atípica",
    CAIDA_DEMANDA: "Caída de demanda",
  };
  const ESTADOS = {
    OPTIMO: { texto: "Óptimo", clase: "text-emerald-700", barra: "bg-emerald-500" },
    ALERTA: { texto: "Alerta", clase: "text-amber-700", barra: "bg-amber-400" },
    CRITICO: { texto: "Crítico", clase: "text-red-700", barra: "bg-red-500" },
  };
  const RANGOS = [
    { dias: 1, texto: "24 h" },
    { dias: 7, texto: "7 días" },
    { dias: 30, texto: "30 días" },
  ];
  const DIAS_INICIAL = 7;
  const TECLAS_SIGUIENTE = ["ArrowDown", "ArrowRight"];
  const TECLAS_ANTERIOR = ["ArrowUp", "ArrowLeft"];
  const TIEMPO_MAXIMO_PETICION_MS = 15000;

  // ── Formato es-CO. Las marcas de tiempo llegan como «2026-10-28T14:00:00-05:00» y se leen
  //    del texto, no con Date: así se muestran en hora de Amalfi sea cual sea la zona del equipo.
  const formatos = new Map();
  const formateador = (decimales) => {
    if (!formatos.has(decimales)) {
      formatos.set(
        decimales,
        new Intl.NumberFormat("es-CO", {
          minimumFractionDigits: decimales,
          maximumFractionDigits: decimales,
        }),
      );
    }
    return formatos.get(decimales);
  };
  const formatoCop = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  });
  const vacio = (v) => v === null || v === undefined || Number.isNaN(v);
  const f = {
    num: (v, decimales = 0) => (vacio(v) ? "—" : formateador(decimales).format(v)),
    cop: (v) => (vacio(v) ? "—" : formatoCop.format(v)),
    millones: (v, decimales = 0) => (vacio(v) ? "—" : `${f.num(v / 1e6, decimales)} M`),
    signo: (v) => (vacio(v) ? "—" : `${v > 0 ? "+" : ""}${f.num(v, 1)}`),
    fecha: (ts) => (ts ? `${ts.slice(8, 10)}/${ts.slice(5, 7)}/${ts.slice(0, 4)}` : "—"),
    hora: (ts) => (ts ? ts.slice(11, 16) : "—"),
    fechaHora: (ts) => (ts ? `${ts.slice(8, 10)}/${ts.slice(5, 7)} ${ts.slice(11, 16)}` : "—"),
    tipoAnomalia: (t) => NOMBRE_ANOMALIA[t] || t,
  };
  const conAlfa = (hex, alfa) => {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
  };

  // ── Chart.js: apariencia común (marcas finas, rejilla recesiva, tooltip por índice) ─────
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = C.tinta;
  Chart.defaults.borderColor = C.rejilla;
  // Sin animaciones: con 720 puntos sólo cuestan rendimiento, y una captura o impresión
  // nunca debe salir con un gráfico a medio dibujar (OT-0006 §9).
  Chart.defaults.animation = false;
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.point.radius = 0;
  Chart.defaults.elements.point.hoverRadius = 4;
  Chart.defaults.plugins.legend.align = "start";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.boxHeight = 8;
  Chart.defaults.plugins.legend.labels.color = C.tintaFuerte;
  Chart.defaults.plugins.tooltip.backgroundColor = C.tintaFuerte;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.boxPadding = 4;
  Chart.defaults.plugins.tooltip.usePointStyle = true;

  /** Bandas horizontales de fondo y líneas de umbral (gráfico de SoC). */
  const pluginBandas = {
    id: "bandas",
    // Bandas y líneas de umbral detrás de los datos…
    beforeDatasetsDraw(chart, _args, opciones) {
      if (!opciones.bandas) return;
      const { ctx, chartArea, scales } = chart;
      ctx.save();
      for (const banda of opciones.bandas) {
        const arriba = scales.y.getPixelForValue(banda.hasta);
        const abajo = scales.y.getPixelForValue(banda.desde);
        ctx.fillStyle = banda.color;
        ctx.fillRect(chartArea.left, arriba, chartArea.width, abajo - arriba);
      }
      for (const linea of opciones.lineas || []) {
        const y = scales.y.getPixelForValue(linea.valor);
        ctx.strokeStyle = linea.color;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y);
        ctx.lineTo(chartArea.right, y);
        ctx.stroke();
      }
      ctx.restore();
    },
    // …y sus rótulos encima, con fondo, para que la serie no los tache.
    afterDatasetsDraw(chart, _args, opciones) {
      if (!opciones.bandas) return;
      const { ctx, chartArea, scales } = chart;
      ctx.save();
      ctx.font = "500 11px Inter, system-ui, sans-serif";
      const rotulo = (texto, x, y, alineacion) => {
        const ancho = ctx.measureText(texto).width;
        const izquierda = alineacion === "right" ? x - ancho : x;
        ctx.fillStyle = C.fondoRotulo;
        ctx.fillRect(izquierda - 4, y - 11, ancho + 8, 15);
        ctx.fillStyle = C.tinta;
        ctx.textAlign = alineacion;
        ctx.fillText(texto, x, y);
      };
      for (const banda of opciones.bandas) {
        rotulo(banda.texto, chartArea.right - 8, scales.y.getPixelForValue(banda.hasta) + 14, "right");
      }
      for (const linea of opciones.lineas || []) {
        rotulo(linea.texto, chartArea.left + 8, scales.y.getPixelForValue(linea.valor) - 5, "left");
      }
      ctx.restore();
    },
  };

  /** Línea vertical con etiqueta en una posición del eje X (punto de payback). */
  const pluginMarcaVertical = {
    id: "marcaVertical",
    afterDatasetsDraw(chart, _args, opciones) {
      if (vacio(opciones.x)) return;
      const { ctx, chartArea, scales } = chart;
      const x = scales.x.getPixelForValue(opciones.x);
      ctx.save();
      ctx.strokeStyle = C.tintaFuerte;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top + 18);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = C.tintaFuerte;
      ctx.font = "600 12px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(opciones.texto, x, chartArea.top + 12);
      ctx.restore();
    },
  };
  Chart.register(pluginBandas, pluginMarcaVertical);

  // ── Fábrica de gráficos: crear la primera vez, después sólo actualizar ──────────────────
  const graficos = new Map();
  function dibujar(id, config) {
    for (const ds of config.data.datasets) {
      if (ds.backgroundColor === undefined && ds.borderColor) ds.backgroundColor = ds.borderColor;
    }
    const lienzo = document.getElementById(id);
    if (!lienzo) return;
    const existente = graficos.get(id);
    if (existente) {
      existente.data = config.data;
      existente.options = config.options;
      existente.update("none");
      return;
    }
    graficos.set(id, new Chart(lienzo, config));
  }

  /** Tooltip «Serie: valor unidad» con el formato y la unidad de cada dataset. */
  const etiquetaTooltip = (ctx) => {
    const ds = ctx.dataset;
    return `${ds.label}: ${f.num(ctx.parsed.y, ds.decimales ?? 1)} ${ds.unidad || ""}`.trim();
  };

  function ejeY({ titulo, min, max, derecha = false, apilado = false, formato } = {}) {
    return {
      position: derecha ? "right" : "left",
      min,
      max,
      stacked: apilado,
      beginAtZero: true,
      border: { display: false },
      grid: {
        drawOnChartArea: !derecha,
        color: (ctx) => (ctx.tick && ctx.tick.value === 0 ? C.eje : C.rejilla),
      },
      ticks: { maxTicksLimit: 6, callback: formato || ((v) => f.num(v, 0)) },
      title: { display: Boolean(titulo), text: titulo, color: C.tinta },
    };
  }

  function opciones({ ejes, apiladoX = false, plugins = {}, leyenda = true }) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          stacked: apiladoX,
          grid: { display: false },
          border: { color: C.eje },
          ticks: { autoSkip: true, autoSkipPadding: 24, maxTicksLimit: 8, maxRotation: 0 },
        },
        ...ejes,
      },
      plugins: {
        legend: { display: leyenda },
        tooltip: {
          // Las series de anomalías son null fuera de sus horas: no ocupan línea en el tooltip.
          filter: (item) => !vacio(item.parsed.y),
          callbacks: { label: etiquetaTooltip },
        },
        ...plugins,
      },
    };
  }

  const etiquetasHora = (p) =>
    p.series.timestamps.map((ts) => (p.rango.dias === 1 ? f.hora(ts) : f.fechaHora(ts)));

  /** Serie con valores sólo en las horas anómalas de una variable (el resto, null). */
  function puntosAnomalos(p, variable) {
    const posicion = new Map(p.series.timestamps.map((ts, i) => [ts, i]));
    const puntos = new Array(p.series.timestamps.length).fill(null);
    for (const a of p.analitica.anomalias) {
      if (a.variable === variable && posicion.has(a.timestamp)) {
        puntos[posicion.get(a.timestamp)] = a.real_kwh;
      }
    }
    return puntos;
  }

  const CONSTRUCTORES = {
    "g-balance": (p) => ({
      type: "line",
      data: {
        labels: etiquetasHora(p),
        datasets: [
          {
            label: "Generación FV",
            data: p.series.generacion,
            borderColor: C.generacion,
            backgroundColor: conAlfa(C.generacion, 0.15),
            fill: "origin",
            tension: 0.25,
            unidad: "kWh",
            yAxisID: "y",
          },
          {
            label: "Demanda",
            data: p.series.demanda,
            borderColor: C.demanda,
            tension: 0.25,
            unidad: "kWh",
            yAxisID: "y",
          },
          {
            label: "SoC",
            data: p.series.soc,
            borderColor: C.soc,
            borderDash: [5, 4],
            tension: 0.25,
            unidad: "%",
            yAxisID: "y1",
          },
        ],
      },
      options: opciones({
        ejes: {
          y: ejeY({ titulo: "kWh" }),
          y1: ejeY({ titulo: "SoC (%)", min: 0, max: 100, derecha: true }),
        },
      }),
    }),

    "g-fv": (p) => ({
      type: "bar",
      data: {
        labels: etiquetasHora(p),
        datasets: [
          {
            type: "line",
            label: "Irradiancia",
            data: p.series.irradiancia,
            borderColor: C.irradiancia,
            tension: 0.25,
            unidad: "W/m²",
            decimales: 0,
            yAxisID: "y1",
          },
          {
            label: "Generación FV",
            data: p.series.generacion,
            backgroundColor: C.generacion,
            borderRadius: 2,
            barPercentage: 1,
            categoryPercentage: 0.85,
            unidad: "kWh",
            yAxisID: "y",
          },
        ],
      },
      options: opciones({
        ejes: {
          y: ejeY({ titulo: "Generación (kWh)" }),
          y1: ejeY({ titulo: "Irradiancia (W/m²)", min: 0, max: 1000, derecha: true }),
        },
      }),
    }),

    "g-temperaturas": (p) => ({
      type: "line",
      data: {
        labels: etiquetasHora(p),
        datasets: [
          {
            label: "Panel",
            data: p.series.temp_panel,
            borderColor: C.tempPanel,
            tension: 0.25,
            unidad: "°C",
          },
          {
            label: "Ambiente",
            data: p.series.temp_ambiente,
            borderColor: C.tempAmbiente,
            borderDash: [5, 4], // identidad también por trazo, no sólo por color
            tension: 0.25,
            unidad: "°C",
          },
        ],
      },
      options: (() => {
        const o = opciones({ ejes: { y: ejeY({ titulo: "°C" }) } });
        o.scales.y.beginAtZero = false;
        return o;
      })(),
    }),

    "g-carga": (p) => ({
      type: "line",
      data: {
        labels: etiquetasHora(p),
        datasets: SEGMENTOS.map((s, i) => ({
          label: NOMBRE_SEGMENTO[s],
          data: p.segmentos.series[s],
          borderColor: C.segmentos[s],
          backgroundColor: conAlfa(C.segmentos[s], 0.35),
          borderWidth: 1.5,
          fill: i === 0 ? "origin" : "-1",
          tension: 0.25,
          unidad: "kWh",
          decimales: 2,
        })),
      },
      options: (() => {
        const o = opciones({ ejes: { y: ejeY({ titulo: "kWh", apilado: true }) } });
        o.plugins.tooltip.callbacks.footer = (items) =>
          `Total: ${f.num(
            items.reduce((suma, it) => suma + (it.parsed.y || 0), 0),
            2,
          )} kWh`;
        return o;
      })(),
    }),

    "g-participacion": (p) => ({
      type: "doughnut",
      data: {
        labels: SEGMENTOS.map((s) => NOMBRE_SEGMENTO[s]),
        datasets: [
          {
            data: SEGMENTOS.map((s) => p.segmentos.totales_kwh[s]),
            backgroundColor: SEGMENTOS.map((s) => C.segmentos[s]),
            borderColor: C.superficie,
            borderWidth: 2,
            hoverOffset: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
          legend: { display: false }, // la lista de al lado es la leyenda, con valores
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const s = SEGMENTOS[ctx.dataIndex];
                return `${ctx.label}: ${f.num(ctx.parsed, 0)} kWh (${f.num(
                  p.segmentos.participacion_pct[s],
                  1,
                )} %)`;
              },
            },
          },
        },
      },
    }),

    "g-soc": (p) => {
      const u = p.umbrales_soc;
      return {
        type: "line",
        data: {
          labels: etiquetasHora(p),
          datasets: [
            {
              label: "Estado de carga",
              data: p.series.soc,
              borderColor: C.soc,
              tension: 0.25,
              unidad: "%",
            },
          ],
        },
        options: opciones({
          leyenda: false,
          ejes: { y: ejeY({ titulo: "SoC (%)", min: 0, max: 100 }) },
          plugins: {
            bandas: {
              bandas: [
                { desde: u.optimo, hasta: 100, color: C.bandaOptimo, texto: "Óptimo" },
                { desde: u.alerta, hasta: u.optimo, color: C.bandaAlerta, texto: "Alerta" },
                { desde: 0, hasta: u.alerta, color: C.bandaCritico, texto: "Crítico" },
              ],
              lineas: [
                { valor: u.minimo, color: C.reserva, texto: `Reserva mínima ${u.minimo} %` },
              ],
            },
          },
        }),
      };
    },

    "g-potencia": (p) => ({
      type: "bar",
      data: {
        labels: etiquetasHora(p),
        datasets: [
          {
            label: "Carga",
            data: p.series.potencia_bateria.map((v) => (v > 0 ? v : null)),
            backgroundColor: C.carga,
            borderRadius: 2,
            barPercentage: 1,
            categoryPercentage: 0.85,
            unidad: "kW",
          },
          {
            label: "Descarga",
            data: p.series.potencia_bateria.map((v) => (v < 0 ? v : null)),
            backgroundColor: C.descarga,
            borderRadius: 2,
            barPercentage: 1,
            categoryPercentage: 0.85,
            unidad: "kW",
          },
        ],
      },
      options: (() => {
        const o = opciones({ apiladoX: true, ejes: { y: ejeY({ titulo: "kW", apilado: true }) } });
        o.scales.y.beginAtZero = false;
        return o;
      })(),
    }),

    "g-pred-generacion": (p) => prediccion(p, "generacion", "Generación real", C.generacion),
    "g-pred-demanda": (p) => prediccion(p, "demanda", "Demanda real", C.demanda),

    "g-flujo": (p) => {
      const fin = p.financiero;
      const neto = fin.flujo.map((fila) => fila.flujo_neto_cop);
      return {
        type: "bar",
        data: {
          labels: fin.flujo.map((fila) => `Año ${fila.anio}`),
          datasets: [
            {
              type: "line",
              label: "Flujo acumulado",
              data: fin.flujo.map((fila) => fila.flujo_acumulado_cop),
              borderColor: C.acumulado,
              backgroundColor: C.acumulado,
              pointRadius: 4,
              pointBorderColor: C.superficie,
              pointBorderWidth: 2,
              tension: 0,
            },
            {
              label: "Flujo neto anual",
              data: neto.map((v) => (v >= 0 ? v : null)),
              backgroundColor: C.flujoPositivo,
              borderRadius: 4,
              grouped: false,
            },
            {
              label: "Inversión inicial",
              data: neto.map((v) => (v < 0 ? v : null)),
              backgroundColor: C.flujoNegativo,
              borderRadius: 4,
              grouped: false,
            },
          ],
        },
        options: (() => {
          const o = opciones({
            ejes: {
              y: ejeY({ titulo: "Millones de COP", formato: (v) => f.num(v / 1e6, 0) }),
            },
            plugins: {
              marcaVertical: {
                x: fin.payback_simple_anios,
                texto: `Payback ${f.num(fin.payback_simple_anios, 1)} años`,
              },
            },
          });
          o.plugins.tooltip.callbacks.label = (ctx) =>
            `${ctx.dataset.label}: ${f.millones(ctx.parsed.y, 1)} COP`;
          o.plugins.tooltip.callbacks.afterBody = (items) =>
            items[0] && items[0].dataIndex === fin.anio_reemplazo_baterias
              ? "Incluye el reemplazo del banco de baterías"
              : "";
          return o;
        })(),
      };
    },
  };

  function prediccion(p, variable, etiquetaReal, color) {
    return {
      type: "line",
      data: {
        labels: etiquetasHora(p),
        datasets: [
          {
            label: "Anomalía",
            data: puntosAnomalos(p, variable),
            showLine: false,
            pointRadius: 5,
            pointHoverRadius: 6,
            pointBackgroundColor: C.anomalia,
            pointBorderColor: C.superficie,
            pointBorderWidth: 2,
            borderColor: C.anomalia,
            backgroundColor: C.anomalia,
            unidad: "kWh",
          },
          {
            label: etiquetaReal,
            data: p.series[variable],
            borderColor: color,
            tension: 0.25,
            unidad: "kWh",
          },
          {
            label: "Predicción ML",
            data: p.series[`${variable}_predicha`],
            borderColor: C.prediccion,
            borderDash: [4, 3],
            borderWidth: 1.5,
            tension: 0.25,
            unidad: "kWh",
          },
        ],
      },
      options: opciones({ ejes: { y: ejeY({ titulo: "kWh" }) } }),
    };
  }

  const GRAFICOS_POR_PESTANA = {
    resumen: ["g-balance"],
    fotovoltaico: ["g-fv", "g-temperaturas"],
    demanda: ["g-carga", "g-participacion"],
    almacenamiento: ["g-soc", "g-potencia"],
    analitica: ["g-pred-generacion", "g-pred-demanda"],
    financiero: ["g-flujo"],
  };

  function renderizar(pestana, p) {
    if (!p || p.sin_datos) return;
    for (const id of GRAFICOS_POR_PESTANA[pestana] || []) {
      if (id === "g-flujo" && !p.financiero) continue;
      dibujar(id, CONSTRUCTORES[id](p));
    }
  }

  const refrescarIconos = () => window.lucide && window.lucide.createIcons();

  // ── Componente de Alpine ───────────────────────────────────────────────────────────────
  window.dashboard = function (urlApi) {
    let payload = null; // copia sin Proxy para Chart.js
    let ultimaPeticion = 0;
    const pestanaDelHash = location.hash.slice(1);

    return {
      f,
      rangos: RANGOS,
      dias: DIAS_INICIAL,
      pestana: GRAFICOS_POR_PESTANA[pestanaDelHash] ? pestanaDelHash : "resumen",
      d: null,
      cargando: false,
      error: null,
      verTablaFlujo: false,

      init() {
        // Atrás/adelante del navegador también cambian de pestaña.
        window.addEventListener("hashchange", () => {
          const destino = location.hash.slice(1);
          if (GRAFICOS_POR_PESTANA[destino]) this.pestana = destino;
        });
        this.$watch("pestana", (pestana) => {
          if (location.hash.slice(1) !== pestana) history.pushState(null, "", `#${pestana}`);
          this.$nextTick(() => renderizar(pestana, payload));
        });
        this.$nextTick(refrescarIconos);
        this.cargar();
      },

      async cargar() {
        const peticion = ++ultimaPeticion;
        const diasPedidos = this.dias;
        this.cargando = true;
        this.error = null;
        try {
          const respuesta = await fetch(`${urlApi}?dias=${this.dias}`, {
            headers: { Accept: "application/json" },
            signal: AbortSignal.timeout(TIEMPO_MAXIMO_PETICION_MS),
          });
          const cuerpo = await respuesta.json().catch(() => null);
          if (!respuesta.ok || !cuerpo) {
            const detalle = cuerpo && cuerpo.error ? cuerpo.error : `HTTP ${respuesta.status}`;
            throw new Error(`El servidor respondió con un error (${detalle}).`);
          }
          if (peticion !== ultimaPeticion) return; // llegó tarde: ya se pidió otro rango
          payload = cuerpo;
          this.d = cuerpo;
          this.$nextTick(() => {
            renderizar(this.pestana, payload);
            refrescarIconos();
          });
        } catch (e) {
          if (peticion !== ultimaPeticion) return;
          // Los datos en pantalla siguen siendo del rango anterior: el selector vuelve a él.
          if (this.d && !this.d.sin_datos && this.d.rango.dias && this.d.rango.dias !== diasPedidos) {
            this.dias = this.d.rango.dias;
          }
          this.error =
            e.name === "TimeoutError" ? "El servidor tardó demasiado en responder." : e.message;
        } finally {
          if (peticion === ultimaPeticion) this.cargando = false;
        }
      },

      moverConTeclado(evento) {
        const paso = TECLAS_SIGUIENTE.includes(evento.key)
          ? 1
          : TECLAS_ANTERIOR.includes(evento.key)
            ? -1
            : 0;
        if (!paso) return;
        evento.preventDefault();
        const lista = evento.currentTarget; // tras el evento vale null: se toma ahora
        const ids = Object.keys(GRAFICOS_POR_PESTANA);
        this.pestana = ids[(ids.indexOf(this.pestana) + paso + ids.length) % ids.length];
        this.$nextTick(() => {
          const boton = lista.querySelector(`[data-pestana="${this.pestana}"]`);
          if (boton) boton.focus();
        });
      },

      cambiarRango(dias) {
        if (dias === this.dias) return;
        this.dias = dias;
        this.cargar();
      },

      get k() {
        return this.d && this.d.kpis;
      },
      get par() {
        return this.d && this.d.parametros;
      },
      get fin() {
        return this.d && this.d.financiero;
      },
      get tituloPestana() {
        const tab = document.getElementById(`tab-${this.pestana}`);
        return tab ? tab.textContent.trim() : "";
      },
      get estadoActual() {
        const estado = this.k && ESTADOS[this.k.estado_actual];
        if (!estado) return { texto: "—", detalle: "", clase: "text-slate-500" };
        const u = this.d.umbrales_soc;
        const detalle = {
          OPTIMO: `Batería por encima del ${u.optimo} %: operación normal.`,
          ALERTA: `SoC entre ${u.alerta} % y ${u.optimo} %: priorizar cargas esenciales.`,
          CRITICO: `SoC por debajo del ${u.alerta} %: riesgo de deslastre de carga.`,
        }[this.k.estado_actual];
        return { ...estado, detalle };
      },
      get distribucionEstados() {
        if (!this.d || this.d.sin_datos) return [];
        const total = this.d.rango.n_registros;
        return ["OPTIMO", "ALERTA", "CRITICO"].map((clave) => ({
          clave,
          texto: ESTADOS[clave].texto,
          barra: ESTADOS[clave].barra,
          horas: this.d.estados[clave],
          pct: (this.d.estados[clave] / total) * 100,
        }));
      },
      get resumenFv() {
        if (!this.d || this.d.sin_datos) return [];
        const s = this.d.series;
        const maximo = (serie) => {
          let i = 0;
          serie.forEach((v, j) => {
            if (v > serie[i]) i = j;
          });
          return { valor: serie[i], ts: s.timestamps[i] };
        };
        const irr = maximo(s.irradiancia);
        const gen = maximo(s.generacion);
        const tp = maximo(s.temp_panel);
        return [
          { titulo: "Irradiancia pico", valor: f.num(irr.valor, 0), unidad: "W/m²", detalle: f.fechaHora(irr.ts) },
          { titulo: "Generación horaria máxima", valor: f.num(gen.valor, 1), unidad: "kWh", detalle: f.fechaHora(gen.ts) },
          { titulo: "Temperatura máxima del panel", valor: f.num(tp.valor, 1), unidad: "°C", detalle: f.fechaHora(tp.ts) },
        ];
      },
      get segmentos() {
        if (!this.d || this.d.sin_datos) return [];
        return SEGMENTOS.map((s) => ({
          clave: s,
          texto: NOMBRE_SEGMENTO[s],
          color: C.segmentos[s],
          kwh: this.d.segmentos.totales_kwh[s],
          pct: this.d.segmentos.participacion_pct[s],
        })).sort((a, b) => b.kwh - a.kwh);
      },
      get metricas() {
        if (!this.d || this.d.sin_datos) return [];
        const m = this.d.analitica.metricas;
        return [
          { titulo: "Generación FV", detalle: `Horas con sol · n = ${m.generacion.n}`, ...m.generacion },
          { titulo: "Demanda", detalle: `Todas las horas · n = ${m.demanda.n}`, ...m.demanda },
        ];
      },
      get anomalias() {
        return this.d && !this.d.sin_datos ? this.d.analitica.anomalias : [];
      },
      get tarjetasFinancieras() {
        const fin = this.fin;
        if (!fin) return [];
        const r = fin.resumen;
        const verde = "bg-emerald-50 text-emerald-600";
        const indigo = "bg-indigo-50 text-indigo-600";
        return [
          { titulo: "CAPEX", icono: "landmark", fondo: indigo, valor: `$ ${f.millones(r.capex_cop)}`, completo: f.cop(r.capex_cop), detalle: this.par ? `${f.num(this.par.potencia_pico_kwp, 0)} kWp + ${f.num(this.par.capacidad_bateria_kwh, 0)} kWh + red + logística ZNI` : "" },
          { titulo: "OPEX anual", icono: "receipt", fondo: indigo, valor: `$ ${f.millones(r.opex_anual_cop, 1)}`, completo: f.cop(r.opex_anual_cop), detalle: "Operación y mantenimiento, año 1" },
          { titulo: "VPN", icono: "trending-up", fondo: verde, valor: `$ ${f.millones(r.vpn_cop, 1)}`, completo: f.cop(r.vpn_cop), detalle: `Tasa de descuento ${f.num(fin.tasa_descuento_pct, 0)} % E.A.` },
          { titulo: "TIR", icono: "percent", fondo: verde, valor: `${f.num(r.tir_porcentaje, 2)} %`, completo: "", detalle: `${r.tir_porcentaje > fin.tasa_descuento_pct ? "Supera" : "No alcanza"} la tasa de descuento del ${f.num(fin.tasa_descuento_pct, 0)} %` },
          { titulo: "LCOE", icono: "zap", fondo: verde, valor: `$ ${f.num(r.lcoe_cop_kwh, 0)} /kWh`, completo: "", detalle: `Diésel nivelado: $ ${f.num(fin.costo_nivelado_diesel_cop_kwh, 0)} /kWh` },
          { titulo: "Payback simple", icono: "calendar-clock", fondo: verde, valor: `${f.num(fin.payback_simple_anios, 1)} años`, completo: "", detalle: "Años para recuperar la inversión, sin descontar" },
        ];
      },
    };
  };
})();
