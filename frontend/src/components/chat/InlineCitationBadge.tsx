export interface InlineCitationBadgeProps {
  id: number;
  onClick?: (id: number) => void;
}

/**
 * Inline clickable citation badge rendered after a claim in the answer text.
 * Clicking opens the Evidence panel scrolled to this source (handled by parent).
 */
export function InlineCitationBadge({ id, onClick }: InlineCitationBadgeProps) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(id)}
      className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-700 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300 align-middle"
      aria-label={`Citation ${id}`}
    >
      [{id}]
    </button>
  );
}
