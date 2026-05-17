import type { ChatMessage } from "../../context/ChatContext";
import { MessageBubble } from "./MessageBubble";

type Props = {
  messages: ChatMessage[];
  onSuggestionClick?: (text: string) => void;
};

const SUGGESTIONS = [
  "Where to park now?",
  "Station busy Fri 3pm?",
  "Rules on Victoria Ave",
  "Best spot near station",
];

function VAvatar({ size = 28 }: { size?: number }) {
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full bg-park-fern text-white"
      style={{ width: size, height: size }}
    >
      <span className="font-display text-[11px] font-bold">V</span>
    </div>
  );
}

function EmptyState({ onChipClick }: { onChipClick?: (text: string) => void }) {
  return (
    <div className="px-3 py-4">
      <div className="rounded-2xl bg-greeting p-4">
        <div className="flex items-center gap-2.5">
          <VAvatar />
          <div>
            <h3 className="font-display text-sm font-semibold text-park-ink">Valet</h3>
            <p className="text-[10px] text-park-slate">Your parking assistant</p>
          </div>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-park-slate">
          Hi! I'm Valet, your parking guide. I can help you find available spots, predict future
          availability, and explain street parking rules around Chatswood.
        </p>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-1.5">
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            onClick={() => onChipClick?.(text)}
            className="rounded-xl border border-black/[0.08] bg-white px-2.5 py-2 text-left text-[11px] font-medium text-park-ink transition-colors hover:bg-park-mist/50"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

export function MessageList({ messages, onSuggestionClick }: Props) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col overflow-y-auto bg-warm">
        <EmptyState onChipClick={onSuggestionClick} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto bg-warm px-3 py-3">
      {messages.map((m) => (
        <MessageBubble key={m.id} msg={m} />
      ))}
    </div>
  );
}
