import { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  disabled: boolean;
  onSend: (text: string) => void;
};

type SpeechRecognitionType = typeof window extends { SpeechRecognition: infer T } ? T : unknown;

function MicIcon({ listening }: { listening: boolean }) {
  return (
    <svg
      className={`h-5 w-5 ${listening ? "text-white" : "text-park-slate"}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
      <path d="M19 10v2a7 7 0 01-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22,2 15,22 11,13 2,9" />
    </svg>
  );
}

export function MessageInput({ disabled, onSend }: Props) {
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionType | null>(null);

  useEffect(() => {
    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: SpeechRecognitionType }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: SpeechRecognitionType }).webkitSpeechRecognition;

    if (SpeechRecognition) {
      setSpeechSupported(true);
      const recognition = new (SpeechRecognition as unknown as new () => {
        continuous: boolean;
        interimResults: boolean;
        lang: string;
        onresult: ((event: { results: { transcript: string; isFinal: boolean }[][] }) => void) | null;
        onerror: ((event: { error: string }) => void) | null;
        onend: (() => void) | null;
        start: () => void;
        stop: () => void;
        abort: () => void;
      })();
      
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-AU";

      recognition.onresult = (event) => {
        const results = event.results;
        if (results.length > 0) {
          const transcript = results[results.length - 1][0].transcript;
          setText(transcript);
        }
      };

      recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        setListening(false);
      };

      recognition.onend = () => {
        setListening(false);
      };

      recognitionRef.current = recognition as SpeechRecognitionType;
    }

    return () => {
      if (recognitionRef.current) {
        (recognitionRef.current as { abort: () => void }).abort();
      }
    };
  }, []);

  const toggleListening = useCallback(() => {
    if (!recognitionRef.current) return;

    const recognition = recognitionRef.current as {
      start: () => void;
      stop: () => void;
    };

    if (listening) {
      recognition.stop();
      setListening(false);
    } else {
      setText("");
      recognition.start();
      setListening(true);
    }
  }, [listening]);

  const submit = () => {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
  };

  return (
    <div className="shrink-0 border-t border-black/5 bg-white px-3 py-3 pb-safe">
      <div className="flex items-center gap-2">
        {speechSupported ? (
          <button
            type="button"
            disabled={disabled}
            onClick={toggleListening}
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-colors ${
              listening
                ? "bg-park-brick text-white animate-pulse"
                : "bg-park-mist text-park-slate hover:bg-park-mist/80"
            } disabled:opacity-40`}
            aria-label={listening ? "Stop listening" : "Start voice input"}
          >
            <MicIcon listening={listening} />
          </button>
        ) : null}
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
          placeholder={listening ? "Listening..." : "Ask Valet…"}
          className={`h-11 flex-1 rounded-xl border px-3 text-sm outline-none ring-park-fern/25 focus:ring-2 disabled:bg-zinc-100 ${
            listening ? "border-park-brick/30 bg-park-brick/5" : "border-black/10"
          }`}
        />
        <button
          type="button"
          disabled={disabled || !text.trim()}
          onClick={submit}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-park-fern text-white disabled:opacity-40"
          aria-label="Send message"
        >
          <SendIcon />
        </button>
      </div>
      {listening ? (
        <p className="mt-2 text-center text-xs text-park-brick">
          Speak now… tap mic to stop
        </p>
      ) : null}
    </div>
  );
}
