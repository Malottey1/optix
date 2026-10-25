// Interface strings added in the final UI run (en / es / fr), merged into STRINGS by i18n.ts.
// Same rules as i18n.ts: no digits, observational wording only. es/fr are listed for a
// native-speaker review in docs/i18n-review.md.
export const FINAL_EN = {
  tech_details: "Technical details",
  tech_details_sub: "Rules, contracts, limits",
  kits_note: "Kits and club artwork are illustrative, for fictional clubs.",
};

export type FinalKey = keyof typeof FINAL_EN;

export const FINAL_ES: Record<FinalKey, string> = {
  tech_details: "Detalles técnicos",
  tech_details_sub: "Reglas, contratos, límites",
  kits_note: "Las equipaciones y los escudos son ilustraciones de clubes ficticios.",
};

export const FINAL_FR: Record<FinalKey, string> = {
  tech_details: "Détails techniques",
  tech_details_sub: "Règles, contrats, limites",
  kits_note: "Les maillots et les écussons sont des illustrations de clubs fictifs.",
};
