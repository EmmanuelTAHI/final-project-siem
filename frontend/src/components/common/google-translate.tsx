"use client";

/**
 * Intégration du service en ligne Google Website Translator.
 *
 * - Charge le script officiel translate.google.com et initialise le widget
 *   dans un conteneur invisible ; la langue active est pilotée ailleurs via
 *   le cookie `googtrans` (voir lib/i18n.ts).
 * - Masque toute l'UI Google (bannière, popups, surlignages) : seul notre
 *   sélecteur dans Paramètres est visible.
 * - Patch anti-crash : Google Translate enveloppe les nœuds texte dans des
 *   <font>, ce qui casse removeChild/insertBefore lors de la réconciliation
 *   React. Le garde ci-dessous neutralise ces erreurs connues.
 */

import { useEffect } from "react";

declare global {
  interface Window {
    googleTranslateElementInit?: () => void;
    google?: {
      translate?: {
        TranslateElement?: new (
          options: {
            pageLanguage: string;
            includedLanguages: string;
            autoDisplay: boolean;
          },
          elementId: string
        ) => void;
      };
    };
  }
}

function installDomGuards() {
  if ((window as unknown as Record<string, unknown>).__gtDomGuards) return;
  (window as unknown as Record<string, unknown>).__gtDomGuards = true;

  const originalRemoveChild = Node.prototype.removeChild;
  Node.prototype.removeChild = function <T extends Node>(this: Node, child: T): T {
    if (child.parentNode !== this) {
      return child;
    }
    return originalRemoveChild.call(this, child) as T;
  };

  const originalInsertBefore = Node.prototype.insertBefore;
  Node.prototype.insertBefore = function <T extends Node>(
    this: Node,
    newNode: T,
    referenceNode: Node | null
  ): T {
    if (referenceNode && referenceNode.parentNode !== this) {
      return originalInsertBefore.call(this, newNode, null) as T;
    }
    return originalInsertBefore.call(this, newNode, referenceNode) as T;
  };
}

export function GoogleTranslateProvider() {
  useEffect(() => {
    installDomGuards();

    if (document.getElementById("google-translate-script")) return;

    window.googleTranslateElementInit = () => {
      const TranslateElement = window.google?.translate?.TranslateElement;
      if (!TranslateElement) return;
      new TranslateElement(
        {
          pageLanguage: "fr",
          includedLanguages: "en,es,ru,zh-CN",
          autoDisplay: false,
        },
        "google_translate_element"
      );
    };

    const script = document.createElement("script");
    script.id = "google-translate-script";
    script.src =
      "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
    script.async = true;
    document.body.appendChild(script);
  }, []);

  return (
    <>
      <div id="google_translate_element" style={{ display: "none" }} />
    </>
  );
}
