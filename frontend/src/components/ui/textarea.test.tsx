import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Textarea } from "./textarea";

describe("Textarea", () => {
  it("affiche un placeholder et applique le padding/typographie du design system", () => {
    render(<Textarea placeholder="Décrivez..." />);
    const el = screen.getByPlaceholderText("Décrivez...");
    expect(el).toBeInTheDocument();
    expect(el.className).toContain("px-3");
    expect(el.className).toContain("py-2");
    expect(el.className).toContain("text-sm");
  });

  it("accepte la saisie utilisateur", async () => {
    render(<Textarea placeholder="note" />);
    const user = userEvent.setup();
    const el = screen.getByPlaceholderText("note");
    await user.type(el, "Investigation en cours");
    expect(el).toHaveValue("Investigation en cours");
  });
});
