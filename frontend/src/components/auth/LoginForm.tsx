import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/lib/theme";
import { tokens } from "@/lib/tokens";
import { Loader2 } from "lucide-react";

type ErrorKind = "credentials" | "network" | null;

export function LoginForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorKind, setErrorKind] = useState<ErrorKind>(null);
  const { login } = useAuth();
  const { t, accent } = useTheme();
  const navigate = useNavigate();

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
    } catch (err) {
      setErrorKind(err instanceof TypeError ? "network" : "credentials");
    } finally {
      setIsLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "9px 12px",
    fontSize: 13,
    border: `1px solid ${t.border}`,
    borderRadius: 6,
    background: t.surface2,
    color: t.text,
    outline: "none",
    fontFamily: "inherit",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    color: t.text2,
    display: "block",
    marginBottom: 6,
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h1 style={{ fontSize: 18, fontWeight: 600, color: t.text, margin: 0 }}>Sign in to continue</h1>

      <div>
        <label htmlFor="username" style={labelStyle}>Username</label>
        <input
          id="username"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={isLoading}
          required
          style={inputStyle}
        />
      </div>

      <div>
        <label htmlFor="password" style={labelStyle}>Password</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isLoading}
          required
          style={inputStyle}
        />
      </div>

      {errorKind === "credentials" && (
        <p role="alert" style={{ fontSize: 12, color: "#EF4444", margin: 0 }}>
          Invalid username or password. Please try again.
        </p>
      )}
      {errorKind === "network" && (
        <p role="alert" style={{ fontSize: 12, color: "#EF4444", margin: 0 }}>
          Unable to connect. Check your connection and try again.
        </p>
      )}

      <button
        type="submit"
        disabled={isLoading}
        style={{
          width: "100%",
          padding: "10px",
          background: accent,
          color: "#fff",
          border: "none",
          borderRadius: 6,
          fontSize: 14,
          fontWeight: 600,
          cursor: isLoading ? "not-allowed" : "pointer",
          opacity: isLoading ? 0.7 : 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          fontFamily: "inherit",
        }}
      >
        {isLoading && <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />}
        {isLoading ? "Signing in..." : "Sign In"}
      </button>
    </form>
  );
}
