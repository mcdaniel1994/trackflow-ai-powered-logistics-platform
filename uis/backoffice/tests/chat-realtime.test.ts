import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatSocketClient } from "@/lib/realtime/chat";

class FakeSocket {
  readyState = 0;
  sent: string[] = [];
  close = vi.fn(() => { this.readyState = 3; });
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  send(frame: string) { this.sent.push(frame); }
  open() { this.readyState = 1; this.onopen?.(); }
  message(frame: unknown) { this.onmessage?.({ data: JSON.stringify(frame) }); }
  disconnect() { this.readyState = 3; this.onclose?.(); }
}

describe("ChatSocketClient", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("uses a same-origin socket, queues until open, and sends named frames", () => {
    const sockets: FakeSocket[] = [];
    const events = vi.fn();
    const states = vi.fn();
    const factory = vi.fn(() => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket as unknown as WebSocket;
    });
    const client = new ChatSocketClient({
      sessionId: "session / one",
      onEvent: events,
      onStateChange: states,
      websocketFactory: factory,
    });

    client.sendUserMessage("Where is it?", "ticket");
    expect(factory).toHaveBeenCalledWith(expect.stringMatching(/^ws:\/\/.*\/realtime\/chat\/session%20%2F%20one$/));
    expect(sockets[0].sent).toEqual([]);
    sockets[0].open();
    expect(JSON.parse(sockets[0].sent[0])).toEqual({
      event: "user_message",
      data: { session_id: "session / one", text: "Where is it?", route: "ticket" },
    });

    sockets[0].message({ event: "session_snapshot", data: { messages: [] } });
    expect(events).toHaveBeenCalledWith({ event: "session_snapshot", data: { messages: [] } });
    expect(states).toHaveBeenCalledWith("connected");
  });

  it("reconnects with bounded exponential backoff and preserves queued input", () => {
    const sockets: FakeSocket[] = [];
    const timers: Array<{ callback: () => void; delay: number }> = [];
    const client = new ChatSocketClient({
      sessionId: "session-1",
      onEvent: vi.fn(),
      onStateChange: vi.fn(),
      random: () => 0.5,
      websocketFactory: () => {
        const socket = new FakeSocket();
        sockets.push(socket);
        return socket as unknown as WebSocket;
      },
      setTimer: (callback, delay) => {
        timers.push({ callback, delay });
        return 1 as unknown as ReturnType<typeof setTimeout>;
      },
    });

    client.connect();
    sockets[0].disconnect();
    expect(timers[0].delay).toBe(500);
    client.interrupt("new direction", "knowledge");
    timers[0].callback();
    expect(sockets).toHaveLength(2);
    sockets[1].open();
    expect(JSON.parse(sockets[1].sent[0])).toEqual({
      event: "interrupt_requested",
      data: { session_id: "session-1", new_input: "new direction", route: "knowledge" },
    });
  });

  it("ignores malformed frames and stops reconnecting after close", () => {
    const socket = new FakeSocket();
    const events = vi.fn();
    const setTimer = vi.fn();
    const states = vi.fn();
    const client = new ChatSocketClient({
      sessionId: "session-1",
      onEvent: events,
      onStateChange: states,
      websocketFactory: () => socket as unknown as WebSocket,
      setTimer,
    });
    client.connect();
    socket.onmessage?.({ data: "not json" });
    client.close();
    socket.onclose?.();

    expect(events).not.toHaveBeenCalled();
    expect(setTimer).not.toHaveBeenCalled();
    expect(states).toHaveBeenLastCalledWith("disconnected");
  });
});
