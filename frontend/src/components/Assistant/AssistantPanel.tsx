import { useChatContext } from "../../context/ChatContext";
import type { MarkerData } from "../../types";
import { CarParkDetail } from "../Map/CarParkDetail";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";

type Props = {
  isDesktop: boolean;
  mobileExpanded: boolean;
  onMobileExpandedChange: (v: boolean) => void;
  detail: MarkerData | null;
  detailAsOf?: string;
  onCloseDetail: () => void;
};

export function AssistantPanel({
  isDesktop,
  mobileExpanded,
  onMobileExpandedChange,
  detail,
  detailAsOf,
  onCloseDetail,
}: Props) {
  const { messages, busy, error, sendMessage, retryChat, clearError } = useChatContext();

  const expanded = isDesktop || mobileExpanded;

  if (!isDesktop && !expanded) {
    return (
      <button
        type="button"
        onClick={() => onMobileExpandedChange(true)}
        className="fixed bottom-4 left-1/2 z-[2000] flex -translate-x-1/2 items-center gap-2 rounded-full bg-park-ink px-5 py-3 text-sm font-semibold text-white shadow-lg md:hidden"
      >
        Ask ParkSmart…
      </button>
    );
  }

  const drawerClass = isDesktop
    ? "hidden h-dvh w-[380px] shrink-0 flex-col border-l border-black/5 bg-white shadow-drawer md:flex"
    : "fixed inset-x-0 bottom-0 z-[2000] flex max-h-[78vh] flex-col rounded-t-3xl bg-white pb-safe shadow-sheet md:hidden";

  return (
    <aside className={drawerClass}>
      <header className="flex shrink-0 items-center justify-between border-b border-black/5 px-3 py-2">
        <h2 className="font-display text-lg font-semibold tracking-tight">ParkSmart</h2>
        {!isDesktop ? (
          <button
            type="button"
            className="text-xs font-medium text-park-fern underline"
            onClick={() => onMobileExpandedChange(false)}
          >
            Minimise
          </button>
        ) : null}
      </header>

      {detail ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-3">
          <button
            type="button"
            className="mb-2 self-start text-sm font-medium text-park-fern underline"
            onClick={onCloseDetail}
          >
            ← Back to chat
          </button>
          <CarParkDetail data={detail} asOf={detailAsOf} />
        </div>
      ) : (
        <>
          <MessageList messages={messages} />
          {error ? (
            <div className="mx-3 mb-2 flex flex-wrap items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-900">
              <span className="flex-1">{error}</span>
              <button type="button" className="font-semibold underline" onClick={() => void retryChat()}>
                Retry
              </button>
              <button type="button" className="font-semibold underline" onClick={clearError}>
                Dismiss
              </button>
            </div>
          ) : null}
          <MessageInput disabled={busy} onSend={(t) => void sendMessage(t)} />
        </>
      )}
    </aside>
  );
}
