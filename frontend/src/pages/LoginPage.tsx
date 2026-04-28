import { LoginForm } from "@/components/auth/LoginForm";

/**
 * Login page — full-height white background, card centered vertically.
 * Card max-width 400px per UI-SPEC Login Page layout.
 */
export function LoginPage() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="w-full max-w-[400px] bg-white border border-zinc-200 rounded-lg p-8">
        <LoginForm />
      </div>
    </div>
  );
}
