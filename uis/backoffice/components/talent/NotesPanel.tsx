// Notes panel — the feature this whole app was built to make safe. Ana's
// original incident was lost interview notes; everything here is shaped around
// "make destruction deliberate":
//   - Each note has its own Delete button (no bulk action).
//   - Delete shows a native confirm before calling the API.
//   - Add is optimistic (low risk); delete is NOT optimistic — we wait for the
//     server to confirm before removing the row.
//
// Notes are sorted client-side, newest first, so the most recent interview
// context is the first thing the user sees.

"use client";

import { FormEvent, useMemo, useState } from "react";
import { createNote, deleteNote, errorMessage } from "@/lib/talent/api";
import type { Note } from "@/lib/talent/types";
import { Button } from "@/components/talent/ui/Button";
import { Spinner } from "@/components/talent/ui/Spinner";
import { Textarea } from "@/components/talent/ui/Textarea";

type NotesPanelProps = {
  candidateId: string;
  initialNotes: Note[];
};

function formatDateTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function NotesPanel({ candidateId, initialNotes }: NotesPanelProps) {
  const [notes, setNotes] = useState(initialNotes);
  const [content, setContent] = useState("");
  const [pendingAdd, setPendingAdd] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const sortedNotes = useMemo(
    () =>
      [...notes].sort(
        (first, second) =>
          new Date(second.created_at).getTime() - new Date(first.created_at).getTime(),
      ),
    [notes],
  );

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextContent = content.trim();

    if (!nextContent) {
      setError("Write a note before adding it.");
      return;
    }

    setPendingAdd(true);
    setError("");
    setSuccess("");

    try {
      const created = await createNote(candidateId, nextContent);
      setNotes((current) => [created, ...current]);
      setContent("");
      setSuccess("Note added.");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPendingAdd(false);
    }
  }

  async function handleDelete(note: Note) {
    // Native confirm is intentional — the spec calls for explicit friction
    // before a destructive action. A nicer modal would be ergonomic, but a
    // single accidental click should never destroy interview notes again.
    const confirmed = window.confirm("Delete this candidate note? This cannot be undone.");

    if (!confirmed) {
      return;
    }

    setDeletingId(note.id);
    setError("");
    setSuccess("");

    try {
      await deleteNote(candidateId, note.id);
      setNotes((current) => current.filter((item) => item.id !== note.id));
      setSuccess("Note deleted.");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDeletingId("");
    }
  }

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-navy-deep">Notes</h2>
          <p className="text-sm text-neutral-500">Calls, interviews, and review context stay here.</p>
        </div>
        {pendingAdd ? <Spinner label="Adding" /> : null}
      </div>

      <form onSubmit={handleAdd} className="mt-4 space-y-3">
        <label htmlFor="new-note" className="block text-sm font-semibold text-navy-deep">
          Add note
        </label>
        <Textarea
          id="new-note"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          rows={4}
          placeholder="Capture the discussion while it is fresh."
          disabled={pendingAdd}
        />
        <Button type="submit" disabled={pendingAdd || !content.trim()}>
          Add note
        </Button>
      </form>

      {error ? (
        <div className="mt-4 rounded-md border border-coral/30 bg-coral/10 p-3 text-sm text-navy-deep">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="mt-4 rounded-md border border-teal/40 bg-teal/10 p-3 text-sm font-semibold text-navy-deep">
          {success}
        </div>
      ) : null}

      <div className="mt-5 space-y-3">
        {sortedNotes.length ? (
          sortedNotes.map((note) => (
            <article key={note.id} className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
              <div className="flex items-start justify-between gap-4">
                <time className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  {formatDateTime(note.created_at)}
                </time>
                <Button
                  variant="danger"
                  className="px-3 py-1.5"
                  onClick={() => handleDelete(note)}
                  disabled={Boolean(deletingId)}
                >
                  {deletingId === note.id ? "Deleting" : "Delete"}
                </Button>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-navy-deep">{note.content}</p>
            </article>
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-neutral-300 bg-neutral-50 p-6 text-sm text-neutral-700">
            No notes yet.
          </div>
        )}
      </div>
    </section>
  );
}
