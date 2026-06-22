import { useAuth } from "@/hooks/useAuth";
import { useSSEChat } from "@/hooks/useSSEChat";
import { Header } from "@/components/layout/Header";
import { MessageList } from "@/components/chat/MessageList";
import { ChatInput } from "@/components/chat/ChatInput";

/**
 * Full chat page — single-column, full-width layout (D-01, CONTEXT.md).
 * Layout: header (56px) + message list (flex-1, scrollable) + input row (52px).
 * forceLogout is passed as the onUnauthorized callback to submit() — called by
 * fetchWithAuth when refresh token is expired (D-10, CONTEXT.md).
 */
export function ChatPage() {
  const { logout, forceLogout } = useAuth();
  const { messages, isStreaming, submit } = useSSEChat();

  const handleSubmit = (message: string) => {
    submit(message, forceLogout);
  };

  return (
    <div className="h-screen flex flex-col bg-white overflow-hidden">
      <Header onLogout={logout} />
      <MessageList messages={messages} isStreaming={isStreaming} />
      <ChatInput isStreaming={isStreaming} onSubmit={handleSubmit} />
    </div>
  );
}
