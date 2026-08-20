"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

type Seed = { question: string; route?: string; nonce: number } | null;

type ChatPanelValue = {
  open: boolean;
  seed: Seed;
  openPanel: (question?: string, route?: string) => void;
  closePanel: () => void;
};

const ChatPanelContext = createContext<ChatPanelValue | null>(null);

/**
 * Owns the Back Office chat slide-over's open state so the panel can be mounted once in the protected
 * layout and opened from any route (the header "Ask AI" button or the home Ask box). Opening never
 * creates server state; a chat session is created only when the first message is sent.
 */
export function ChatPanelProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [seed, setSeed] = useState<Seed>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const openPanel = useCallback((question?: string, route?: string) => {
    // Remember the invoking control so focus returns to it on close.
    triggerRef.current = (typeof document !== "undefined" ? (document.activeElement as HTMLElement | null) : null) ?? null;
    setOpen(true);
    if (question && question.trim()) setSeed({ question: question.trim(), route, nonce: Date.now() });
  }, []);

  const closePanel = useCallback(() => {
    setOpen(false);
    const element = triggerRef.current;
    if (element) window.setTimeout(() => element.focus?.(), 0);
  }, []);

  const value = useMemo(() => ({ open, seed, openPanel, closePanel }), [open, seed, openPanel, closePanel]);
  return <ChatPanelContext.Provider value={value}>{children}</ChatPanelContext.Provider>;
}

export function useChatPanel(): ChatPanelValue {
  const context = useContext(ChatPanelContext);
  if (!context) {
    throw new Error("useChatPanel must be used within ChatPanelProvider.");
  }
  return context;
}
