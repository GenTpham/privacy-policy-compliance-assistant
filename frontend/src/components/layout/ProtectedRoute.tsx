import { Navigate } from "react-router-dom";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * Guards authenticated routes.
 * Checks localStorage for access_token synchronously — no useEffect needed.
 * Synchronous check prevents flash of unprotected content (D-12, CONTEXT.md).
 * Uses React Router v6 <Navigate replace /> — NOT useHistory (removed in v6).
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
