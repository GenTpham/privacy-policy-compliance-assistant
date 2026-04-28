import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  onLogout: () => void;
}

/**
 * Fixed top header bar.
 * Height: 56px (h-14) per UI-SPEC Chat Page layout.
 * Title: "Privacy Policy Assistant" (20px/600 per UI-SPEC Typography heading).
 * Logout button: "Log out" (two words per UI-SPEC Copywriting Contract).
 * Hover: text-destructive on logout (UI-SPEC Color section).
 */
export function Header({ onLogout }: HeaderProps) {
  return (
    <header className="h-14 flex items-center justify-between px-4 bg-white border-b border-zinc-200 shrink-0">
      {/* App title — 20px semibold per UI-SPEC Typography heading */}
      <h1 className="text-xl font-semibold text-zinc-950">
        Privacy Policy Assistant
      </h1>

      {/* Logout button — "Log out" (two words, UI-SPEC Copywriting Contract) */}
      <Button
        variant="ghost"
        onClick={onLogout}
        className="text-zinc-700 hover:text-destructive hover:bg-zinc-100 flex items-center gap-1"
        aria-label="Log out"
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
        Log out
      </Button>
    </header>
  );
}
