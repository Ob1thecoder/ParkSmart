import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { postChatStream } from "../api";
import type { ChatStreamEvent } from "../types";

export type ChatToolEntry = {
  tool: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
  isRunning: boolean;
};

export type ChatMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      tools: ChatToolEntry[];
      streaming: boolean;
    };

type ChatContextValue = {
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  retryChat: () => Promise<void>;
  clearError: () => void;
};

const ChatContext = createContext<ChatContextValue | null>(null);

function nid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const historyRef = useRef<{ role: "user" | "assistant"; content: string }[]>([]);
  const busyRef = useRef(false);
  const lastFailedUserRef = useRef<string | null>(null);
  busyRef.current = busy;

  const runStream = useCallback(
    async (trimmed: string, asstId: string, priorHistory: typeof historyRef.current) => {
      let accumulated = "";
      const tools: ChatToolEntry[] = [];

      const patchAssistant = (patch: Partial<Extract<ChatMessage, { role: "assistant" }>>) => {
        setMessages((m) =>
          m.map((row) => (row.id === asstId && row.role === "assistant" ? { ...row, ...patch } : row)),
        );
      };

      let streamError: string | null = null;

      const onEvent = (ev: ChatStreamEvent) => {
        if (ev.type === "text") {
          accumulated += ev.content;
          patchAssistant({ content: accumulated });
        } else if (ev.type === "tool_call") {
          tools.push({ tool: ev.tool, input: ev.input, isRunning: true });
          patchAssistant({ tools: [...tools] });
        } else if (ev.type === "tool_result") {
          const idx = tools.findIndex((t) => t.tool === ev.tool && t.isRunning);
          if (idx >= 0) {
            tools[idx] = { ...tools[idx], result: ev.result, isRunning: false };
            patchAssistant({ tools: [...tools] });
          }
        } else if (ev.type === "error") {
          streamError = ev.message;
        }
      };

      await postChatStream({ message: trimmed, history: priorHistory }, onEvent);

      if (streamError) {
        throw new Error(streamError);
      }

      tools.forEach((t) => {
        t.isRunning = false;
      });
      patchAssistant({ tools: [...tools], streaming: false });

      historyRef.current.push({ role: "user", content: trimmed });
      historyRef.current.push({ role: "assistant", content: accumulated });
    },
    [],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busyRef.current) return;

      setError(null);
      lastFailedUserRef.current = null;
      const userMsg: ChatMessage = { id: nid(), role: "user", content: trimmed };
      const asstId = nid();
      const asstPlaceholder: ChatMessage = {
        id: asstId,
        role: "assistant",
        content: "",
        tools: [],
        streaming: true,
      };

      const prior = [...historyRef.current];
      setMessages((m) => [...m, userMsg, asstPlaceholder]);
      setBusy(true);

      try {
        await runStream(trimmed, asstId, prior);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Chat request failed";
        setError(msg);
        lastFailedUserRef.current = trimmed;
        setMessages((m) =>
          m.map((row) =>
            row.id === asstId && row.role === "assistant"
              ? {
                  ...row,
                  content:
                    row.content ||
                    "Something went wrong while reaching the assistant. You can retry below.",
                  streaming: false,
                }
              : row,
          ),
        );
      } finally {
        setBusy(false);
      }
    },
    [runStream],
  );

  const retryChat = useCallback(async () => {
    const trimmed = lastFailedUserRef.current;
    if (!error || !trimmed || busyRef.current) return;

    const asstId = nid();
    const asstPlaceholder: ChatMessage = {
      id: asstId,
      role: "assistant",
      content: "",
      tools: [],
      streaming: true,
    };

    setMessages((m) => {
      const last = m[m.length - 1];
      const base = last?.role === "assistant" ? m.slice(0, -1) : m;
      return [...base, asstPlaceholder];
    });

    const prior = [...historyRef.current];
    setError(null);
    setBusy(true);

    try {
      await runStream(trimmed, asstId, prior);
      lastFailedUserRef.current = null;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Chat request failed";
      setError(msg);
      lastFailedUserRef.current = trimmed;
      setMessages((m) =>
        m.map((row) =>
          row.id === asstId && row.role === "assistant"
            ? {
                ...row,
                content: row.content || "Request failed again.",
                streaming: false,
              }
            : row,
        ),
      );
    } finally {
      setBusy(false);
    }
  }, [error, runStream]);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({ messages, busy, error, sendMessage, retryChat, clearError }),
    [messages, busy, error, sendMessage, retryChat, clearError],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used within ChatProvider");
  return ctx;
}
