import { useState } from "react";

type Props = {
  disabled: boolean;
  onSend: (text: string) => void;
};

export function MessageInput({ disabled, onSend }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
  };

  return (
    <div className="border-t border-black/5 p-3 pb-safe">
      <div className="flex gap-2">
        <textarea
          rows={2}
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask ParkSmart…"
          className="min-h-[44px] flex-1 resize-none rounded-xl border border-black/10 px-3 py-2 text-sm outline-none ring-park-fern/25 focus:ring-2 disabled:bg-zinc-100"
        />
        <button
          type="button"
          disabled={disabled || !text.trim()}
          onClick={submit}
          className="self-end rounded-xl bg-park-fern px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  );
}
