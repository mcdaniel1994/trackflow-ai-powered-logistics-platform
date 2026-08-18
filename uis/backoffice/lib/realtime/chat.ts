import type { AgentRoute } from "@/lib/agents/types";

export type ChatConnectionState = "connecting" | "connected" | "reconnecting" | "disconnected";

export interface ChatSocketEvent {
  event: string;
  data: Record<string, unknown>;
}

interface ChatSocketOptions {
  sessionId: string;
  onEvent: (event: ChatSocketEvent) => void;
  onStateChange: (state: ChatConnectionState) => void;
  websocketFactory?: (url: string) => WebSocket;
  random?: () => number;
  setTimer?: (callback: () => void, delay: number) => ReturnType<typeof setTimeout>;
  clearTimer?: (timer: ReturnType<typeof setTimeout>) => void;
}

function socketUrl(sessionId: string) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/realtime/chat/${encodeURIComponent(sessionId)}`;
}

export class ChatSocketClient {
  private readonly sessionId: string;
  private readonly onEvent: ChatSocketOptions["onEvent"];
  private readonly onStateChange: ChatSocketOptions["onStateChange"];
  private readonly websocketFactory: NonNullable<ChatSocketOptions["websocketFactory"]>;
  private readonly random: NonNullable<ChatSocketOptions["random"]>;
  private readonly setTimer: NonNullable<ChatSocketOptions["setTimer"]>;
  private readonly clearTimer: NonNullable<ChatSocketOptions["clearTimer"]>;
  private socket: WebSocket | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private attempts = 0;
  private disposed = false;
  private queue: string[] = [];

  constructor(options: ChatSocketOptions) {
    this.sessionId = options.sessionId;
    this.onEvent = options.onEvent;
    this.onStateChange = options.onStateChange;
    this.websocketFactory = options.websocketFactory ?? ((url) => new WebSocket(url));
    this.random = options.random ?? Math.random;
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
  }

  connect() {
    if (this.disposed || this.socket) return;
    this.onStateChange(this.attempts ? "reconnecting" : "connecting");
    const socket = this.websocketFactory(socketUrl(this.sessionId));
    this.socket = socket;
    socket.onopen = () => {
      if (this.socket !== socket || this.disposed) return;
      this.attempts = 0;
      this.onStateChange("connected");
      for (const frame of this.queue) socket.send(frame);
      this.queue = [];
    };
    socket.onmessage = (message) => {
      try {
        const parsed = JSON.parse(String(message.data)) as ChatSocketEvent;
        if (parsed && typeof parsed.event === "string" && parsed.data && typeof parsed.data === "object") {
          this.onEvent(parsed);
        }
      } catch {
        // Ignore malformed frames; the server remains the authoritative session source.
      }
    };
    socket.onerror = () => socket.close();
    socket.onclose = () => {
      if (this.socket === socket) this.socket = null;
      if (this.disposed) {
        this.onStateChange("disconnected");
        return;
      }
      this.scheduleReconnect();
    };
  }

  sendUserMessage(text: string, route: AgentRoute) {
    this.send("user_message", { session_id: this.sessionId, text, route });
  }

  interrupt(newInput: string | null, route: AgentRoute) {
    this.send("interrupt_requested", {
      session_id: this.sessionId,
      new_input: newInput,
      route,
    });
  }

  close() {
    this.disposed = true;
    if (this.retryTimer !== null) this.clearTimer(this.retryTimer);
    this.retryTimer = null;
    this.queue = [];
    this.socket?.close(1000, "Client closed");
    this.socket = null;
    this.onStateChange("disconnected");
  }

  private send(event: string, data: Record<string, unknown>) {
    const frame = JSON.stringify({ event, data });
    if (this.socket?.readyState === 1) {
      this.socket.send(frame);
      return;
    }
    this.queue.push(frame);
    this.connect();
  }

  private scheduleReconnect() {
    this.attempts += 1;
    this.onStateChange("reconnecting");
    const base = Math.min(10_000, 500 * 2 ** Math.min(this.attempts - 1, 5));
    const delay = Math.round(base * (0.8 + this.random() * 0.4));
    this.retryTimer = this.setTimer(() => {
      this.retryTimer = null;
      this.connect();
    }, delay);
  }
}
