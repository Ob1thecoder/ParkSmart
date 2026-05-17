import type { ChatMessage } from "../../context/ChatContext";
import { ToolResultCard } from "./ToolResultCard";

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

function StreamingDots() {
  return (
    <div className="flex items-center gap-1 pt-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1 w-1 rounded-full bg-park-slate/50 animate-dot-jump"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
  );
}

export function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[88%] rounded-2xl rounded-br-sm bg-park-ink px-3 py-2 text-[13px] leading-relaxed text-white">
          {msg.content}
        </div>
      </div>
    );
  }

  const hasContent = msg.content.length > 0;
  const hasRunningTools = msg.tools.some((t) => t.isRunning);
  const showStreamingDots = msg.streaming && !hasContent && hasRunningTools;

  return (
    <div className="flex items-start gap-2">
      <VAvatar />
      <div className="flex-1 min-w-0">
        {msg.streaming && !hasContent && !hasRunningTools ? (
          <p className="text-xs font-medium text-park-slate">Valet is checking</p>
        ) : null}

        {showStreamingDots ? (
          <>
            <p className="text-xs font-medium text-park-slate">Valet is checking</p>
            <StreamingDots />
          </>
        ) : null}

        {hasContent ? (
          <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-park-ink">
            {msg.content}
          </p>
        ) : null}

        {msg.tools.map((t, i) => (
          <ToolResultCard
            key={`${t.tool}-${i}`}
            tool={t.tool}
            input={t.input}
            result={t.result}
            isRunning={t.isRunning}
          />
        ))}

        {msg.streaming && hasContent ? <StreamingDots /> : null}
      </div>
    </div>
  );
}
