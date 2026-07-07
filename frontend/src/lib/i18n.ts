/**
 * Internationalisation via le service Google Website Translator.
 *
 * L'interface est écrite en français ; la traduction vers les autres langues
 * est déléguée au service en ligne Google Translate, piloté par le cookie
 * `googtrans` (format `/fr/<cible>`). Le widget observe le DOM en continu,
 * ce qui couvre aussi le contenu dynamique (alertes temps réel, tableaux…).
 */

export const SUPPORTED_LANGUAGES = [
  { code: "fr", label: "Français", flag: "fr" },
  { code: "en", label: "English", flag: "gb" },
  { code: "es", label: "Español", flag: "es" },
  { code: "ru", label: "Русский", flag: "ru" },
  { code: "zh-CN", label: "中文", flag: "cn" },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

const COOKIE = "googtrans";

/** Langue active, lue depuis le cookie googtrans (fr si absent). */
export function getCurrentLanguage(): LanguageCode {
  if (typeof document === "undefined") return "fr";
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE}=([^;]*)`));
  if (!match) return "fr";
  const target = decodeURIComponent(match[1]).split("/")[2];
  const known = SUPPORTED_LANGUAGES.find((l) => l.code === target);
  return known ? known.code : "fr";
}

/**
 * Change la langue de l'interface : pose (ou supprime) le cookie googtrans
 * sur toutes les variantes de domaine que le widget consulte, puis recharge
 * la page pour que le service retraduise proprement tout le document.
 */
export function setLanguage(code: LanguageCode): void {
  if (typeof document === "undefined") return;

  const host = window.location.hostname;
  const domains = ["", host, `.${host}`];

  if (code === "fr") {
    for (const d of domains) {
      document.cookie = `${COOKIE}=; path=/;${d ? ` domain=${d};` : ""} expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    }
  } else {
    const value = `/fr/${code}`;
    for (const d of domains) {
      document.cookie = `${COOKIE}=${value}; path=/;${d ? ` domain=${d};` : ""} max-age=31536000`;
    }
  }

  window.location.reload();
}
