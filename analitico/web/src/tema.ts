// Paleta categórica validada (8 cores, ordem fixa) e cores de superfície por tema.
import { useEffect, useState } from "react";

export type Tema = "claro" | "escuro";

const SERIES: Record<Tema, string[]> = {
  claro: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
  escuro: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};
const OUTROS: Record<Tema, string> = { claro: "#8a8985", escuro: "#7d7c78" };

export const CORES: Record<Tema, { superficie: string; texto: string; texto2: string; grade: string; eixo: string }> = {
  claro: { superficie: "#fcfcfb", texto: "#0b0b0b", texto2: "#52514e", grade: "#ebeae6", eixo: "#c9c8c3" },
  escuro: { superficie: "#1a1a19", texto: "#f0efec", texto2: "#c3c2b7", grade: "#2c2c2a", eixo: "#4a4a46" },
};

/** Cor fixa por material: segue a posição no cadastro, nunca a ordem em que aparece no gráfico. */
export function corDoMaterial(tema: Tema, ordem: string[], materialId: string): string {
  const i = ordem.indexOf(materialId);
  return i >= 0 && i < SERIES[tema].length ? SERIES[tema][i] : OUTROS[tema];
}

export function useTema(): Tema {
  const consulta = "(prefers-color-scheme: dark)";
  const [tema, setTema] = useState<Tema>(() => (window.matchMedia(consulta).matches ? "escuro" : "claro"));
  useEffect(() => {
    const m = window.matchMedia(consulta);
    const ouvir = () => setTema(m.matches ? "escuro" : "claro");
    m.addEventListener("change", ouvir);
    return () => m.removeEventListener("change", ouvir);
  }, []);
  return tema;
}
