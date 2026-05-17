import type { ChatMessage } from "../../context/ChatContext";
import { MessageBubble } from "./MessageBubble";

type Props = {
  messages: ChatMessage[];
};

export function MessageList({ messages }: Props) {
  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-3 py-3">
      {messages.length === 0 ? (
        <p className="text-center text-sm text-park-slate">
          Ask where to park, future availability, or street rules for Chatswood.
        </p>
      ) : (
        messages.map((m) => <MessageBubble key={m.id} msg={m} />)
      )}
    </div>
  );
}
