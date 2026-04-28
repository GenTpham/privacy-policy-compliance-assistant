import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { Loader2 } from "lucide-react";
import { tokens } from "@/lib/tokens";

type ErrorKind = "credentials" | "network" | null;

/**
 * Login form with 4 states: default, loading, error-credentials, error-network.
 * Copywriting from UI-SPEC.md Copywriting Contract.
 */
export function LoginForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorKind, setErrorKind] = useState<ErrorKind>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  // If already authenticated, redirect to chat (UI-01: authenticated visit to /login)
  if (tokens.getAccess()) {
    navigate("/", { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorKind(null);
    setIsLoading(true);
    try {
      await login(username, password);
      // login() navigates to / on success — no further action needed
    } catch (err) {
      if (err instanceof TypeError) {
        // Network failure (fetch throws TypeError on connection errors)
        setErrorKind("network");
      } else {
        // API returned non-OK status (401 from backend)
        setErrorKind("credentials");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      {/* Heading — 20px semibold per UI-SPEC typography */}
      <h1 className="text-xl font-semibold text-zinc-950">Sign in to continue</h1>

      {/* Username field */}
      <div className="flex flex-col gap-2">
        <Label htmlFor="username" className="text-sm font-semibold text-zinc-950">
          Username
        </Label>
        <Input
          id="username"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={isLoading}
          required
        />
      </div>

      {/* Password field */}
      <div className="flex flex-col gap-2">
        <Label htmlFor="password" className="text-sm font-semibold text-zinc-950">
          Password
        </Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isLoading}
          required
        />
      </div>

      {/* Error messages — text-destructive per UI-SPEC */}
      {errorKind === "credentials" && (
        <p className="text-sm text-destructive" role="alert">
          Invalid username or password. Please try again.
        </p>
      )}
      {errorKind === "network" && (
        <p className="text-sm text-destructive" role="alert">
          Unable to connect. Check your connection and try again.
        </p>
      )}

      {/* Submit button — full width, accent (#18181b) background per UI-SPEC */}
      <Button
        type="submit"
        disabled={isLoading}
        className="w-full bg-zinc-950 text-white hover:bg-zinc-800"
      >
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Signing in...
          </>
        ) : (
          "Sign In"
        )}
      </Button>
    </form>
  );
}
