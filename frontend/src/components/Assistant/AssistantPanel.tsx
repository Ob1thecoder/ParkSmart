import { useState } from "react";
import { useChatContext } from "../../context/ChatContext";
import type { MarkerData, OccupancyResponse } from "../../types";
import type { PredictionMap } from "../../hooks/usePredictions";
import { CarParkDetail } from "../Map/CarParkDetail";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import { CarParksTab } from "./CarParksTab";

type TabId = "chat" | "parks";

type Props = {
  isDesktop: boolean;
  mobileExpanded: boolean;
  onMobileExpandedChange: (v: boolean) => void;
  detail: MarkerData | null;
  detailAsOf?: string;
  detailViewTime: Date | null;
  onCloseDetail: () => void;
  occupancy?: OccupancyResponse[];
  occupancyLoading?: boolean;
  predictions?: PredictionMap;
  viewTime?: Date;
  onSelectCarPark?: (id: string) => void;
};

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

function ChatIcon({ active }: { active: boolean }) {
  return (
    <svg
      className="h-3 w-3"
      viewBox="0 0 24 24"
      fill="none"
      stroke={active ? "#1f6b4a" : "#5c6f66"}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function CarIcon({ active }: { active: boolean }) {
  return (
    <svg
      className="h-3 w-3"
      viewBox="0 0 24 24"
      fill="none"
      stroke={active ? "#1f6b4a" : "#5c6f66"}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M7 17m-2 0a2 2 0 104 0 2 2 0 10-4 0M17 17m-2 0a2 2 0 104 0 2 2 0 10-4 0" />
      <path d="M5 17H3v-6l2-5h9l4 5h1a2 2 0 012 2v4h-2m-4 0H9" />
    </svg>
  );
}

export function AssistantPanel({
  isDesktop,
  mobileExpanded,
  onMobileExpandedChange,
  detail,
  detailAsOf,
  detailViewTime,
  onCloseDetail,
  occupancy = [],
  occupancyLoading = false,
  predictions = {},
  viewTime,
  onSelectCarPark,
}: Props) {
  const { messages, busy, error, sendMessage, retryChat, clearError } = useChatContext();
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [showLive, setShowLive] = useState(true);

  const expanded = isDesktop || mobileExpanded;
  const isStreaming = messages.some((m) => m.role === "assistant" && m.streaming);

  if (!isDesktop && !expanded) {
    return null;
  }

  const drawerClass = isDesktop
    ? "hidden h-full w-[380px] shrink-0 flex-col border-l border-black/5 bg-white shadow-drawer md:flex"
    : "fixed inset-x-0 bottom-0 z-[2000] flex max-h-[85vh] flex-col rounded-t-3xl bg-white shadow-sheet md:hidden";

  const handleSuggestion = (text: string) => {
    void sendMessage(text);
  };

  return (
    <aside className={drawerClass}>
      <header className="flex shrink-0 items-center gap-2.5 border-b border-black/5 bg-white px-3 py-2.5 shadow-subtle">
        <VAvatar />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-sm font-semibold text-park-ink">Valet</h2>
            <div className="flex items-center gap-1">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  isStreaming ? "bg-park-amber animate-live-pulse" : "bg-park-fern"
                }`}
              />
              <span className="text-[10px] text-park-slate">
                {isStreaming ? "On it…" : "Online"}
              </span>
            </div>
          </div>
          <p className="text-[10px] text-park-slate">Your parking assistant</p>
        </div>
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

      {!detail ? (
        <div className="flex shrink-0 border-b border-black/5 bg-white">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-semibold transition-colors ${
              activeTab === "chat"
                ? "border-b-2 border-park-fern text-park-fern"
                : "text-park-slate hover:text-park-ink"
            }`}
          >
            <ChatIcon active={activeTab === "chat"} />
            Chat
          </button>
          <button
            onClick={() => setActiveTab("parks")}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-semibold transition-colors ${
              activeTab === "parks"
                ? "border-b-2 border-park-fern text-park-fern"
                : "text-park-slate hover:text-park-ink"
            }`}
          >
            <CarIcon active={activeTab === "parks"} />
            Car Parks
          </button>
        </div>
      ) : null}

      {detail ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-3">
          <CarParkDetail
            data={detail}
            asOf={detailAsOf}
            viewTime={detailViewTime}
            onClose={onCloseDetail}
          />
        </div>
      ) : activeTab === "chat" ? (
        <>
          <MessageList messages={messages} onSuggestionClick={handleSuggestion} />
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
      ) : (
        <CarParksTab
          occupancy={occupancy}
          loading={occupancyLoading}
          predictions={predictions}
          showLive={showLive}
          onToggle={setShowLive}
          viewTime={viewTime}
          onSelect={onSelectCarPark}
        />
      )}
    </aside>
  );
}
