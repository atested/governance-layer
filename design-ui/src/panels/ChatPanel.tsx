import type { FormEvent } from "react";
import type { ChatMessage } from "../types/design";

export type ChatPanelProps = {
  messages: ChatMessage[];
  draft: string;
  setDraft: (draft: string) => void;
  onSubmit: (event: FormEvent) => void | Promise<void>;
};

export function ChatPanel({
  messages,
  draft,
  setDraft,
  onSubmit
}: ChatPanelProps) {
  return (
    <section className="chat-panel" data-testid="chat-panel">
      <h2>Chat</h2>
      <div className="message-list">
        {messages.map((message) => (
          <p className={`message message-${message.role}`} key={message.id}>
            <b>{message.role}</b> {message.content}
          </p>
        ))}
      </div>
      <form className="chat-form" onSubmit={onSubmit}>
        <textarea
          aria-label="Chat message"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask a question, or try purpose:, constraint:, boundary:, connect X to Y"
          value={draft}
        />
        <button type="submit">Send</button>
      </form>
    </section>
  );
}
