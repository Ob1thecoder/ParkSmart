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
    <div className="shrink-0 border-t border-black/5 bg-white px-3 py-3 pb-safe">
      <div className="flex gap-2">
        <input
          type="text"
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask Valet…"
          className="h-11 flex-1 rounded-xl border border-black/10 px-3 text-sm outline-none ring-park-fern/25 focus:ring-2 disabled:bg-zinc-100"
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
