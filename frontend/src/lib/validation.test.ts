import { describe, expect, it } from "vitest";
import { validatePasswordChange } from "./validation";

describe("validatePasswordChange", () => {
  it("refuse si le mot de passe actuel est vide", () => {
    expect(validatePasswordChange("", "newpassword1", "newpassword1")).toBe(
      "Remplissez tous les champs"
    );
  });

  it("refuse si le nouveau mot de passe est vide", () => {
    expect(validatePasswordChange("current123", "", "")).toBe(
      "Remplissez tous les champs"
    );
  });

  it("refuse si la confirmation ne correspond pas", () => {
    expect(validatePasswordChange("current123", "newpassword1", "different1")).toBe(
      "Les mots de passe ne correspondent pas"
    );
  });

  it("refuse un mot de passe de moins de 8 caractères", () => {
    expect(validatePasswordChange("current123", "short1", "short1")).toBe(
      "Min. 8 caractères"
    );
  });

  it("accepte un mot de passe valide", () => {
    expect(validatePasswordChange("current123", "newpassword1", "newpassword1")).toBeNull();
  });
});
