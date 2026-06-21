"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { KeyRound, PlusCircle, Power, RotateCcw, Search, ShieldCheck } from "lucide-react";
import {
  createUser,
  listUsers,
  revokeUserSessions,
  updateUserStatus,
} from "@/lib/auth/api";
import { errorMessage } from "@/lib/auth/errors";
import type { AuthUser, CreatedUser, UserStatus } from "@/lib/auth/types";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Select } from "@/components/talent/ui/Select";
import { Spinner } from "@/components/talent/ui/Spinner";
import { useAuth } from "@/lib/auth/context";

type StatusFilter = "all" | UserStatus;
type ActionHelpKey = "suspend" | "disable" | "reactivate" | "revoke";
type ActionHelpSurface = "desktop" | "mobile";

const ACTION_HELP: Record<ActionHelpKey, string> = {
  suspend: "Temporarily blocks login and refresh, revokes active sessions, and can be reversed.",
  disable: "Deactivates the account and revokes sessions. This is reversible, not a hard delete.",
  reactivate: "Restores the account to active. The user must sign in again.",
  revoke: "Keeps the account active but logs the user out everywhere by revoking refresh sessions.",
};

const SELF_LOCKOUT_MESSAGE = "You can't suspend or disable your own account.";

function actionHelpId(userId: string, surface: ActionHelpSurface, action: ActionHelpKey) {
  return `user-action-${surface}-${action}-${userId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

function ActionTooltip({
  id,
  text,
  className = "",
  children,
}: {
  id: string;
  text: string;
  className?: string;
  children: (describedBy: string) => ReactNode;
}) {
  return (
    <span className={`group relative inline-flex max-w-full ${className}`.trim()}>
      {children(id)}
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full right-0 z-30 mb-2 w-64 max-w-[calc(100vw-2rem)] rounded-md border border-mist bg-navy-deep px-3 py-2 text-left text-xs font-semibold leading-snug text-white opacity-0 shadow-lg transition group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}

function formatDate(value: string | null) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function statusBadgeClass(status: UserStatus) {
  if (status === "active") {
    return "border-teal/40 bg-teal/10 text-navy-deep";
  }

  if (status === "suspended") {
    return "border-coral/40 bg-coral/10 text-navy-deep";
  }

  return "border-neutral-300 bg-neutral-100 text-neutral-700";
}

function matchesUser(user: AuthUser, query: string, status: StatusFilter) {
  const normalizedQuery = query.trim().toLowerCase();
  const statusMatches = status === "all" || user.status === status;
  const queryMatches =
    !normalizedQuery ||
    user.name.toLowerCase().includes(normalizedQuery) ||
    user.email.toLowerCase().includes(normalizedQuery);

  return statusMatches && queryMatches;
}

export function AdminUsersView() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [createPending, setCreatePending] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createdUser, setCreatedUser] = useState<CreatedUser | null>(null);
  const [actionPending, setActionPending] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  async function loadUsers() {
    setLoading(true);
    setLoadError("");

    try {
      setUsers(await listUsers());
    } catch (caught) {
      setLoadError(errorMessage(caught));
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;

    async function loadInitialUsers() {
      try {
        const initialUsers = await listUsers();
        if (active) {
          setUsers(initialUsers);
        }
      } catch (caught) {
        if (active) {
          setLoadError(errorMessage(caught));
          setUsers([]);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadInitialUsers();

    return () => {
      active = false;
    };
  }, []);

  const filteredUsers = useMemo(
    () => users.filter((user) => matchesUser(user, query, statusFilter)),
    [query, statusFilter, users],
  );

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError("");
    setCreatedUser(null);

    if (!newName.trim() || !newEmail.trim()) {
      setCreateError("Name and email are required.");
      return;
    }

    setCreatePending(true);
    try {
      const created = await createUser(newName.trim(), newEmail.trim());
      setCreatedUser(created);
      setUsers((current) => [created, ...current.filter((user) => user.id !== created.id)]);
      setNewName("");
      setNewEmail("");
    } catch (caught) {
      setCreateError(errorMessage(caught));
    } finally {
      setCreatePending(false);
    }
  }

  async function runAction(user: AuthUser, action: "suspend" | "disable" | "reactivate" | "revoke") {
    setActionError("");
    setActionSuccess("");

    if (user.id === currentUser.id && (action === "suspend" || action === "disable")) {
      setActionError(SELF_LOCKOUT_MESSAGE);
      return;
    }

    setActionPending(`${user.id}:${action}`);

    try {
      if (action === "revoke") {
        await revokeUserSessions(user.id);
        setActionSuccess(`Revoked sessions for ${user.email}.`);
      } else {
        const nextStatus =
          action === "reactivate" ? "active" : action === "suspend" ? "suspended" : "disabled";
        const updated = await updateUserStatus(user.id, nextStatus);
        setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        setActionSuccess(`${updated.email} is now ${updated.status}.`);
      }
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setActionPending("");
    }
  }

  return (
    <div className="w-full max-w-full min-w-0 space-y-6">
      <header className="flex flex-col justify-between gap-4 border-b border-mist pb-6 lg:flex-row lg:items-end">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Administration</p>
          <h1 className="mt-2 text-2xl font-black text-navy-deep sm:text-3xl">User Management</h1>
          <p className="mt-3 max-w-3xl text-neutral-600">
            Create Back Office users, manage account status, and revoke active sessions.
          </p>
        </div>
        <Button variant="secondary" className="w-fit gap-2" onClick={loadUsers} disabled={loading}>
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </header>

      <section className="grid w-full max-w-full min-w-0 gap-6">
        <div className="min-w-0 space-y-6">
          <section className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-navy-deep">Create user</h2>
            <p className="mt-1 text-sm text-neutral-600">
              New users receive a one-time temporary password and must change it on first login.
            </p>

            <form onSubmit={handleCreate} className="mt-4 space-y-4">
              {createError ? (
                <div className="rounded-md border border-coral/30 bg-coral/10 p-3 text-sm text-navy-deep">
                  {createError}
                </div>
              ) : null}

              <Field label="Name" htmlFor="new-user-name">
                <Input
                  id="new-user-name"
                  value={newName}
                  onChange={(event) => setNewName(event.target.value)}
                  disabled={createPending}
                  autoComplete="name"
                />
              </Field>

              <Field label="Email" htmlFor="new-user-email">
                <Input
                  id="new-user-email"
                  type="email"
                  value={newEmail}
                  onChange={(event) => setNewEmail(event.target.value)}
                  disabled={createPending}
                  autoComplete="email"
                />
              </Field>

              <Button type="submit" className="gap-2" disabled={createPending}>
                {createPending ? (
                  <Spinner label="Creating" className="text-white" />
                ) : (
                  <>
                    <PlusCircle className="h-4 w-4" aria-hidden="true" />
                    <span>Create user</span>
                  </>
                )}
              </Button>
            </form>
          </section>

          {createdUser ? (
            <section className="rounded-lg border border-coral/40 bg-coral/10 p-5 shadow-sm">
              <div className="flex items-center gap-2 text-navy-deep">
                <KeyRound className="h-5 w-5 text-coral" aria-hidden="true" />
                <h2 className="text-lg font-semibold">Account setup</h2>
              </div>
              <p className="mt-2 text-sm text-navy-deep">
                {createdUser.setup_email_sent
                  ? `Setup email sent to ${createdUser.email}. The temporary password below is shown once as a fallback.`
                  : `Setup email could not be sent automatically. This password is shown once and cannot be retrieved later. Deliver it securely to ${createdUser.email}.`}
              </p>
              <p className="mt-4 break-all rounded-md border border-coral/30 bg-white px-3 py-2 font-mono text-sm font-bold text-navy-deep">
                {createdUser.temporary_password}
              </p>
            </section>
          ) : null}
        </div>

        <section className="min-w-0 rounded-lg border border-neutral-200 bg-white shadow-sm">
          <div className="grid min-w-0 gap-3 border-b border-neutral-200 p-4 md:grid-cols-[minmax(0,1fr)_180px]">
            <label className="relative">
              <span className="sr-only">Search users</span>
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-neutral-500" aria-hidden="true" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by name or email"
                className="pl-9"
              />
            </label>
            <Select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
              aria-label="Filter by status"
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="disabled">Disabled</option>
            </Select>
          </div>

          {actionError ? (
            <div className="m-4 rounded-md border border-coral/30 bg-coral/10 p-3 text-sm text-navy-deep">
              {actionError}
            </div>
          ) : null}

          {actionSuccess ? (
            <div className="m-4 rounded-md border border-teal/40 bg-teal/10 p-3 text-sm font-semibold text-navy-deep">
              {actionSuccess}
            </div>
          ) : null}

          {loadError ? (
            <div className="m-4 rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
              <p className="font-semibold">Could not load users.</p>
              <p className="mt-1">{loadError}</p>
            </div>
          ) : null}

          <div className="hidden max-w-full md:block">
            <table className="w-full table-fixed text-left text-sm">
              <colgroup>
                <col className="w-[30%]" />
                <col className="w-[14%]" />
                <col className="w-[12%]" />
                <col className="w-[17%]" />
                <col className="w-[27%]" />
              </colgroup>
              <thead className="bg-mist text-xs uppercase tracking-wide text-neutral-700">
                <tr>
                  <th scope="col" className="px-3 py-3 font-semibold">User</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Role</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Last login</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center">
                      <Spinner label="Loading users" />
                    </td>
                  </tr>
                ) : filteredUsers.length ? (
                  filteredUsers.map((user) => (
                    <tr key={user.id}>
                      <td className="px-3 py-3 align-top">
                        <p className="font-bold text-navy-deep">{user.name}</p>
                        <p className="break-all text-xs text-neutral-500">{user.email}</p>
                      </td>
                      <td className="px-3 py-3 align-top">
                        <span className="inline-flex items-center gap-1 rounded-md bg-ivory px-2 py-1 text-xs font-bold capitalize text-navy">
                          <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                          {user.role}
                        </span>
                      </td>
                      <td className="px-3 py-3 align-top">
                        <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-bold capitalize ${statusBadgeClass(user.status)}`}>
                          {user.status}
                        </span>
                      </td>
                      <td className="px-3 py-3 align-top text-neutral-700">
                        {formatDate(user.last_login_at)}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <div className="flex w-full min-w-0 flex-wrap justify-end gap-2">
                          {user.status === "active" ? (
                            <ActionTooltip
                              id={actionHelpId(user.id, "desktop", "suspend")}
                              text={ACTION_HELP.suspend}
                            >
                              {(describedBy) => (
                                <Button
                                  variant="secondary"
                                  className="h-8 gap-1 px-2 py-1"
                                  disabled={Boolean(actionPending) || user.id === currentUser.id}
                                  onClick={() => runAction(user, "suspend")}
                                  aria-describedby={describedBy}
                                  title={ACTION_HELP.suspend}
                                >
                                  <Power className="h-3.5 w-3.5" aria-hidden="true" />
                                  Suspend
                                </Button>
                              )}
                            </ActionTooltip>
                          ) : (
                            <ActionTooltip
                              id={actionHelpId(user.id, "desktop", "reactivate")}
                              text={ACTION_HELP.reactivate}
                            >
                              {(describedBy) => (
                                <Button
                                  variant="secondary"
                                  className="h-8 gap-1 px-2 py-1"
                                  disabled={Boolean(actionPending)}
                                  onClick={() => runAction(user, "reactivate")}
                                  aria-describedby={describedBy}
                                  title={ACTION_HELP.reactivate}
                                >
                                  <Power className="h-3.5 w-3.5" aria-hidden="true" />
                                  Reactivate
                                </Button>
                              )}
                            </ActionTooltip>
                          )}
                          <ActionTooltip
                            id={actionHelpId(user.id, "desktop", "disable")}
                            text={ACTION_HELP.disable}
                          >
                            {(describedBy) => (
                              <Button
                                variant="danger"
                                className="h-8 px-2 py-1"
                                disabled={Boolean(actionPending) || user.status === "disabled" || user.id === currentUser.id}
                                onClick={() => runAction(user, "disable")}
                                aria-describedby={describedBy}
                                title={ACTION_HELP.disable}
                              >
                                Disable
                              </Button>
                            )}
                          </ActionTooltip>
                          <ActionTooltip
                            id={actionHelpId(user.id, "desktop", "revoke")}
                            text={ACTION_HELP.revoke}
                          >
                            {(describedBy) => (
                              <Button
                                variant="secondary"
                                className="h-8 gap-1 px-2 py-1"
                                disabled={Boolean(actionPending)}
                                onClick={() => runAction(user, "revoke")}
                                aria-describedby={describedBy}
                                title={ACTION_HELP.revoke}
                              >
                                <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                                Revoke sessions
                              </Button>
                            )}
                          </ActionTooltip>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm font-semibold text-neutral-600">
                      No users match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="divide-y divide-neutral-200 md:hidden">
            {loading ? (
              <div className="px-4 py-8 text-center">
                <Spinner label="Loading users" />
              </div>
            ) : filteredUsers.length ? (
              filteredUsers.map((user) => (
                <article key={user.id} className="space-y-4 p-4">
                  <div className="min-w-0">
                    <p className="font-bold text-navy-deep">{user.name}</p>
                    <p className="break-all text-sm text-neutral-500">{user.email}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span className="inline-flex items-center gap-1 rounded-md bg-ivory px-2 py-1 text-xs font-bold capitalize text-navy">
                      <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                      {user.role}
                    </span>
                    <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-bold capitalize ${statusBadgeClass(user.status)}`}>
                      {user.status}
                    </span>
                    <span className="inline-flex rounded-md border border-neutral-200 px-2 py-1 text-xs font-semibold text-neutral-600">
                      Last login: {formatDate(user.last_login_at)}
                    </span>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {user.status === "active" ? (
                      <ActionTooltip
                        id={actionHelpId(user.id, "mobile", "suspend")}
                        text={ACTION_HELP.suspend}
                        className="w-full"
                      >
                        {(describedBy) => (
                          <Button
                            variant="secondary"
                            className="h-9 w-full gap-1 px-2 py-1"
                            disabled={Boolean(actionPending) || user.id === currentUser.id}
                            onClick={() => runAction(user, "suspend")}
                            aria-describedby={describedBy}
                            title={ACTION_HELP.suspend}
                          >
                            <Power className="h-3.5 w-3.5" aria-hidden="true" />
                            Suspend
                          </Button>
                        )}
                      </ActionTooltip>
                    ) : (
                      <ActionTooltip
                        id={actionHelpId(user.id, "mobile", "reactivate")}
                        text={ACTION_HELP.reactivate}
                        className="w-full"
                      >
                        {(describedBy) => (
                          <Button
                            variant="secondary"
                            className="h-9 w-full gap-1 px-2 py-1"
                            disabled={Boolean(actionPending)}
                            onClick={() => runAction(user, "reactivate")}
                            aria-describedby={describedBy}
                            title={ACTION_HELP.reactivate}
                          >
                            <Power className="h-3.5 w-3.5" aria-hidden="true" />
                            Reactivate
                          </Button>
                        )}
                      </ActionTooltip>
                    )}
                    <ActionTooltip
                      id={actionHelpId(user.id, "mobile", "disable")}
                      text={ACTION_HELP.disable}
                      className="w-full"
                    >
                      {(describedBy) => (
                        <Button
                          variant="danger"
                          className="h-9 w-full px-2 py-1"
                          disabled={Boolean(actionPending) || user.status === "disabled" || user.id === currentUser.id}
                          onClick={() => runAction(user, "disable")}
                          aria-describedby={describedBy}
                          title={ACTION_HELP.disable}
                        >
                          Disable
                        </Button>
                      )}
                    </ActionTooltip>
                    <ActionTooltip
                      id={actionHelpId(user.id, "mobile", "revoke")}
                      text={ACTION_HELP.revoke}
                      className="w-full"
                    >
                      {(describedBy) => (
                        <Button
                          variant="secondary"
                          className="h-9 w-full gap-1 px-2 py-1"
                          disabled={Boolean(actionPending)}
                          onClick={() => runAction(user, "revoke")}
                          aria-describedby={describedBy}
                          title={ACTION_HELP.revoke}
                        >
                          <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                          Revoke sessions
                        </Button>
                      )}
                    </ActionTooltip>
                  </div>
                </article>
              ))
            ) : (
              <div className="px-4 py-8 text-center text-sm font-semibold text-neutral-600">
                No users match the current filters.
              </div>
            )}
          </div>
        </section>
      </section>
    </div>
  );
}
