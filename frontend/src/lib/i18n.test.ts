import { afterEach, describe, expect, it } from "vitest";
import { getCurrentLanguage, SUPPORTED_LANGUAGES } from "./i18n";

function setCookie(value: string) {
  document.cookie = `googtrans=${encodeURIComponent(value)}; path=/`;
}

function clearCookie() {
  document.cookie = "googtrans=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
}

describe("getCurrentLanguage", () => {
  afterEach(() => {
    clearCookie();
  });

  it("retourne fr quand le cookie googtrans est absent", () => {
    expect(getCurrentLanguage()).toBe("fr");
  });

  it("lit la langue cible depuis le cookie googtrans", () => {
    setCookie("/fr/en");
    expect(getCurrentLanguage()).toBe("en");
  });

  it("retourne fr si la langue cible du cookie n'est pas supportée", () => {
    setCookie("/fr/de");
    expect(getCurrentLanguage()).toBe("fr");
  });

  it("reconnaît le code chinois zh-CN", () => {
    setCookie("/fr/zh-CN");
    expect(getCurrentLanguage()).toBe("zh-CN");
  });
});

describe("SUPPORTED_LANGUAGES", () => {
  it("expose les 5 langues attendues", () => {
    expect(SUPPORTED_LANGUAGES.map((l) => l.code)).toEqual([
      "fr",
      "en",
      "es",
      "ru",
      "zh-CN",
    ]);
  });
});
