import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import toast from "react-hot-toast";
import { RuleFormModal } from "./rule-form-modal";
import { correlationApi } from "@/lib/api";

vi.mock("react-hot-toast", () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

vi.mock("@/lib/api", () => ({
  correlationApi: {
    createRule: vi.fn(),
    updateRule: vi.fn(),
  },
}));

describe("RuleFormModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("refuse la sauvegarde et affiche une erreur si le nom est vide", async () => {
    const onSave = vi.fn();
    render(
      <RuleFormModal open={true} onClose={() => {}} rule={null} onSave={onSave} />
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /créer la règle/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Le nom est requis");
    });
    expect(correlationApi.createRule).not.toHaveBeenCalled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("construit une condition de type threshold par défaut dans l'aperçu JSON", () => {
    render(
      <RuleFormModal open={true} onClose={() => {}} rule={null} onSave={() => {}} />
    );

    expect(screen.getByText(/"type": "threshold"/)).toBeInTheDocument();
    expect(screen.getByText(/"threshold": 5/)).toBeInTheDocument();
    expect(screen.getByText(/"window_minutes": 5/)).toBeInTheDocument();
  });

  it("envoie la règle créée à createRule avec le nom saisi", async () => {
    const onSave = vi.fn();
    vi.mocked(correlationApi.createRule).mockResolvedValue({
      id: "1",
      name: "Ma règle",
    } as never);

    render(
      <RuleFormModal open={true} onClose={() => {}} rule={null} onSave={onSave} />
    );

    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/brute force detection/i), "Ma règle");
    await user.click(screen.getByRole("button", { name: /créer la règle/i }));

    await waitFor(() => {
      expect(correlationApi.createRule).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Ma règle" })
      );
    });
    expect(onSave).toHaveBeenCalled();
  });
});
