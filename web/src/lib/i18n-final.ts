// Interface strings added in the final UI run (en / es / fr), merged into STRINGS by i18n.ts.
// Same rules as i18n.ts: no digits, observational wording only. es/fr are listed for a
// native-speaker review in docs/i18n-review.md.
export const FINAL_EN = {
  tech_details: "Technical details",
  tech_details_sub: "Rules, contracts, limits",
  kits_note: "Kits and club artwork are illustrative, for fictional clubs.",
  hub_lineups: "Lineups",
  panel_title: "Insights and patterns",
  panel_insights: "Insights",
  panel_patterns: "Patterns",
  panel_family: "Pattern family",
  panel_all: "All",
  panel_pages: "Pages",
  panel_prev: "Previous",
  panel_next: "Next",
  panel_page: "Page {k} of {n}",
  panel_per_page: "Cards per page",
  lu_xi: "Starting XI",
  lu_off: "Off",
  lu_on: "On",
  lu_note: "Starting XIs by listed position. Not a tracked shape.",
};

export type FinalKey = keyof typeof FINAL_EN;

export const FINAL_ES: Record<FinalKey, string> = {
  tech_details: "Detalles técnicos",
  tech_details_sub: "Reglas, contratos, límites",
  kits_note: "Las equipaciones y los escudos son ilustraciones de clubes ficticios.",
  hub_lineups: "Alineaciones",
  panel_title: "Datos y patrones",
  panel_insights: "Datos",
  panel_patterns: "Patrones",
  panel_family: "Familia de patrón",
  panel_all: "Todos",
  panel_pages: "Páginas",
  panel_prev: "Anterior",
  panel_next: "Siguiente",
  panel_page: "Página {k} de {n}",
  panel_per_page: "Tarjetas por página",
  lu_xi: "Once inicial",
  lu_off: "Sale",
  lu_on: "Entra",
  lu_note: "Onces iniciales por posición listada. No es una forma medida.",
};

export const FINAL_FR: Record<FinalKey, string> = {
  tech_details: "Détails techniques",
  tech_details_sub: "Règles, contrats, limites",
  kits_note: "Les maillots et les écussons sont des illustrations de clubs fictifs.",
  hub_lineups: "Compositions",
  panel_title: "Analyses et motifs",
  panel_insights: "Analyses",
  panel_patterns: "Motifs",
  panel_family: "Famille de motif",
  panel_all: "Tous",
  panel_pages: "Pages",
  panel_prev: "Précédent",
  panel_next: "Suivant",
  panel_page: "Page {k} sur {n}",
  panel_per_page: "Cartes par page",
  lu_xi: "Onze de départ",
  lu_off: "Sort",
  lu_on: "Entre",
  lu_note: "Onze de départ par poste listé. Pas une forme mesurée.",
};
