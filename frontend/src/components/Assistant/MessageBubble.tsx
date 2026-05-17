import type { ChatMessage } from "../../context/ChatContext";
import { ToolCallBadge } from "./ToolCallBadge";

export function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[90%] rounded-2xl rounded-br-md bg-park-ink px-3 py-2 text-sm text-white">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[95%] rounded-2xl rounded-bl-md border border-black/5 bg-park-mist/80 px-3 py-2 text-sm text-park-ink">
        <p className="whitespace-pre-wrap">{msg.content}</p>
        {msg.tools.map((t, i) => (
          <ToolCallBadge key={`${t.tool}-${i}`} {...t} />
        ))}
        {msg.streaming ? (
          <span className="mt-1 inline-block h-2 w-2 animate-pulse rounded-full bg-park-fern" />
        ) : null}
      </div>
    </div>
  );
}
