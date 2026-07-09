import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import toast from "react-hot-toast";
import UsersPage from "./page";
import { usersApi } from "@/lib/api";

vi.mock("react-hot-toast", () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

vi.mock("@/lib/api", () => ({
  usersApi: {
    createUser: vi.fn(),
    updateUser: vi.fn(),
    deleteUser: vi.fn(),
  },
}));

vi.mock("@/hooks/use-users", () => ({
  useUsers: () => ({ data: [], refetch: vi.fn() }),
  useAuditTrail: () => ({ data: [] }),
}));

describe("UsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("refuse la création si le prénom ou l'email sont vides", async () => {
    render(<UsersPage />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /nouvel utilisateur/i }));
    await user.click(screen.getByRole("button", { name: /créer le compte/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Prénom et email requis");
    });
    expect(usersApi.createUser).not.toHaveBeenCalled();
  });

  it("crée l'utilisateur quand prénom et email sont renseignés", async () => {
    vi.mocked(usersApi.createUser).mockResolvedValue({} as never);
    render(<UsersPage />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /nouvel utilisateur/i }));
    await user.type(screen.getByPlaceholderText("Jean"), "Jean");
    await user.type(screen.getByPlaceholderText(/jean.dupont@example.com/i), "jean@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "SecurePass123");
    await user.click(screen.getByRole("button", { name: /créer le compte/i }));

    await waitFor(() => {
      expect(usersApi.createUser).toHaveBeenCalled();
    });
  });
});
