/**
 * Noms de pays en français pour les codes ISO 3166-1 alpha-2 les plus
 * fréquents (le backend ne renvoie que le code — voir apps/logs/views.py).
 * Fallback : le code brut si absent de la table.
 */
export const COUNTRY_NAMES: Record<string, string> = {
  FR: "France", US: "États-Unis", GB: "Royaume-Uni", DE: "Allemagne",
  CN: "Chine", RU: "Russie", IN: "Inde", BR: "Brésil", JP: "Japon",
  KR: "Corée du Sud", AU: "Australie", CA: "Canada", NL: "Pays-Bas",
  IT: "Italie", ES: "Espagne", SE: "Suède", NO: "Norvège", CH: "Suisse",
  PL: "Pologne", UA: "Ukraine", NG: "Nigeria", ZA: "Afrique du Sud",
  EG: "Égypte", CI: "Côte d'Ivoire", TH: "Thaïlande", SG: "Singapour",
  ID: "Indonésie", MY: "Malaisie", MX: "Mexique", AR: "Argentine",
  TR: "Turquie", SA: "Arabie Saoudite", AE: "Émirats Arabes Unis",
  IL: "Israël", PK: "Pakistan", BD: "Bangladesh", IR: "Iran",
  IQ: "Irak", VN: "Vietnam", PH: "Philippines", BE: "Belgique",
  PT: "Portugal", GR: "Grèce", IE: "Irlande", AT: "Autriche",
  DK: "Danemark", FI: "Finlande", CZ: "Tchéquie", RO: "Roumanie",
  HU: "Hongrie", SN: "Sénégal", MA: "Maroc", DZ: "Algérie",
  TN: "Tunisie", KE: "Kenya", GH: "Ghana", HK: "Hong Kong",
  TW: "Taïwan", NZ: "Nouvelle-Zélande", CO: "Colombie", CL: "Chili",
  PE: "Pérou", VE: "Venezuela", BG: "Bulgarie", HR: "Croatie",
  RS: "Serbie", LT: "Lituanie", LV: "Lettonie", EE: "Estonie",
  IS: "Islande", LU: "Luxembourg", CY: "Chypre", MT: "Malte",
};

export function countryName(code: string | null | undefined): string {
  if (!code) return "Inconnu";
  return COUNTRY_NAMES[code.toUpperCase()] ?? code.toUpperCase();
}
