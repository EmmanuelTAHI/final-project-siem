import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { authApi } from "@/lib/api";
import toast from "react-hot-toast";
import type { LoginCredentials } from "@/types";

export function useAuth() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, setAuth, setLoading, logout: storeLogout } = useAuthStore();

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      setLoading(true);
      try {
        const data = await authApi.login(credentials);
        setAuth(data.user, data.access, data.refresh);
        toast.success(`Bienvenue, ${data.user.first_name} !`);
        router.replace("/dashboard");
      } catch (error: unknown) {
        const axiosError = error as { response?: { data?: { detail?: string } } };
        const msg = axiosError?.response?.data?.detail || "Identifiants incorrects";
        toast.error(msg);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [router, setAuth, setLoading]
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore
    } finally {
      storeLogout();
      toast.success("Déconnexion réussie");
      router.replace("/login");
    }
  }, [router, storeLogout]);

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
  };
}
