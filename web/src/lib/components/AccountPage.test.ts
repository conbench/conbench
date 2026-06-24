import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AccountPage from "./AccountPage.svelte";

const GET = vi.fn();
const POST = vi.fn();
const DELETE = vi.fn();

vi.mock("../api/client", () => ({
  createConbenchClient: () => ({ GET, POST, DELETE }),
}));

const user = {
  id: "user-1",
  email: "author@example.com",
  name: "Benchmark Author",
};

const token = {
  id: "tok-1",
  name: "ci token",
  prefix: "cb_1234",
  created_at: "2026-01-02T00:00:00Z",
  last_used_at: "2026-01-03T00:00:00Z",
};

const alertRule = {
  id: "rule-1",
  user_id: "user-1",
  name: "Arrow nightly",
  repository: "https://github.com/apache/arrow",
  baseline: "fork_point",
  threshold: 5,
  threshold_z: 5,
  enabled: true,
  state: "open",
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-03T00:00:00Z",
  last_evaluated_at: "2026-01-04T00:00:00Z",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function mockSignedIn() {
  GET.mockImplementation((path: string) => {
    if (path === "/api/users/me") return Promise.resolve({ data: user });
    if (path === "/api/tokens") return Promise.resolve({ data: { tokens: [token] } });
    if (path === "/api/alert-rules") return Promise.resolve({ data: { rules: [alertRule] } });
    throw new Error(`unexpected GET ${path}`);
  });
}

beforeEach(() => {
  GET.mockReset();
  POST.mockReset();
  DELETE.mockReset();
  window.history.replaceState(null, "", "/account");
});

describe("AccountPage", () => {
  it("renders a load error when the identity request rejects", async () => {
    GET.mockRejectedValueOnce(new Error("network down"));

    render(AccountPage);

    await waitFor(() => expect(screen.getByRole("heading", { name: /account unavailable/i })).toBeInTheDocument());
    expect(screen.getByText("network down")).toBeInTheDocument();
  });

  it("shows the signed-out state without loading private resources", async () => {
    GET.mockResolvedValueOnce({ error: { detail: "authentication required" } });

    render(AccountPage);

    await waitFor(() => expect(screen.getByRole("heading", { name: /account/i })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/api/auth/login");
    expect(screen.getByText(/authentication required/i)).toBeInTheDocument();
    expect(GET).toHaveBeenCalledTimes(1);
    expect(GET).toHaveBeenCalledWith("/api/users/me");
  });

  it("renders identity, tokens, and alert rules for a signed-in user", async () => {
    mockSignedIn();

    render(AccountPage);

    await waitFor(() => expect(screen.getByText("author@example.com")).toBeInTheDocument());
    expect(screen.getByText("Benchmark Author")).toBeInTheDocument();

    const tokens = screen.getByRole("region", { name: /api tokens/i });
    expect(within(tokens).getByText("ci token")).toBeInTheDocument();
    expect(within(tokens).getByText("cb_1234")).toBeInTheDocument();

    const alerts = screen.getByRole("region", { name: /alert rules/i });
    expect(within(alerts).getByText("Arrow nightly")).toBeInTheDocument();
    expect(within(alerts).getByText("https://github.com/apache/arrow")).toBeInTheDocument();
    expect(within(alerts).getByText("open")).toBeInTheDocument();
  });

  it("creates a token, shows the plaintext once, and revokes tokens", async () => {
    mockSignedIn();
    POST.mockResolvedValueOnce({
      data: {
        id: "tok-2",
        name: "release bot",
        prefix: "cb_9876",
        token: "cb_secret_plaintext",
        created_at: "2026-01-05T00:00:00Z",
      },
    });
    DELETE.mockResolvedValueOnce({ response: { status: 204 } });

    render(AccountPage);
    await waitFor(() => expect(screen.getByText("ci token")).toBeInTheDocument());

    await fireEvent.input(screen.getByLabelText(/token name/i), { target: { value: "release bot" } });
    await fireEvent.submit(screen.getByTestId("token-create-form"));

    await waitFor(() => expect(screen.getByText("cb_secret_plaintext")).toBeInTheDocument());
    expect(POST).toHaveBeenCalledWith("/api/tokens", { body: { name: "release bot" } });
    expect(screen.getAllByText("release bot")).toHaveLength(2);

    await fireEvent.click(screen.getByRole("button", { name: /revoke ci token/i }));
    await waitFor(() => expect(DELETE).toHaveBeenCalledWith("/api/tokens/{id}", { params: { path: { id: "tok-1" } } }));
    expect(screen.queryByText("ci token")).toBeNull();
  });

  it("creates alert rules and drills into alert events", async () => {
    mockSignedIn();
    POST.mockResolvedValueOnce({
      data: {
        ...alertRule,
        id: "rule-2",
        name: "Arrow PR",
        repository: "https://github.com/apache/arrow-rs",
        baseline: "parent",
        threshold: 3,
        threshold_z: 4,
        enabled: false,
        state: "inactive",
      },
    });
    GET.mockImplementation((path: string) => {
      if (path === "/api/users/me") return Promise.resolve({ data: user });
      if (path === "/api/tokens") return Promise.resolve({ data: { tokens: [token] } });
      if (path === "/api/alert-rules") return Promise.resolve({ data: { rules: [alertRule] } });
      if (path === "/api/alert-rules/{id}/events") {
        return Promise.resolve({
          data: {
            events: [
              {
                id: "event-1",
                rule_id: "rule-1",
                kind: "opened",
                status: "failure",
                status_reason: "lookback regression detected",
                run_id: "run-1",
                commit_sha: "abcdef",
                report_url: "/ci/report?run_ids=run-1",
                summary: { regressions: 2 },
                created_at: "2026-01-04T00:00:00Z",
              },
            ],
          },
        });
      }
      throw new Error(`unexpected GET ${path}`);
    });

    render(AccountPage);
    await waitFor(() => expect(screen.getByText("Arrow nightly")).toBeInTheDocument());

    await fireEvent.input(screen.getByLabelText(/rule name/i), { target: { value: "Arrow PR" } });
    await fireEvent.input(screen.getByLabelText(/repository/i), { target: { value: "https://github.com/apache/arrow-rs" } });
    await fireEvent.change(screen.getByLabelText(/baseline/i), { target: { value: "parent" } });
    await fireEvent.input(screen.getByLabelText(/^pairwise threshold/i), { target: { value: "3" } });
    await fireEvent.input(screen.getByLabelText(/z-score threshold/i), { target: { value: "4" } });
    await fireEvent.click(screen.getByLabelText(/enabled/i));
    await fireEvent.submit(screen.getByTestId("alert-create-form"));

    await waitFor(() => expect(screen.getByText("Arrow PR")).toBeInTheDocument());
    expect(POST).toHaveBeenCalledWith("/api/alert-rules", {
      body: {
        name: "Arrow PR",
        repository: "https://github.com/apache/arrow-rs",
        baseline: "parent",
        threshold: 3,
        threshold_z: 4,
        enabled: false,
      },
    });

    await fireEvent.click(screen.getByRole("button", { name: /events for arrow nightly/i }));
    await waitFor(() => expect(screen.getByText("lookback regression detected")).toBeInTheDocument());
    expect(GET).toHaveBeenCalledWith("/api/alert-rules/{id}/events", {
      params: { path: { id: "rule-1" }, query: { limit: 50 } },
    });
    expect(screen.getByRole("link", { name: /report for event-1/i })).toHaveAttribute(
      "href",
      "/ci/report?run_ids=run-1",
    );
  });

  it("ignores stale alert event responses after another rule is selected", async () => {
    const firstEvents = deferred<{ error: { detail: string } }>();
    const secondEvents = deferred<{ data: { events: Record<string, unknown>[] } }>();
    const secondRule = {
      ...alertRule,
      id: "rule-2",
      name: "Arrow commits",
      repository: "https://github.com/apache/arrow-rs",
      state: "inactive",
    };

    GET.mockImplementation((path: string, options?: { params?: { path?: { id?: string } } }) => {
      if (path === "/api/users/me") return Promise.resolve({ data: user });
      if (path === "/api/tokens") return Promise.resolve({ data: { tokens: [token] } });
      if (path === "/api/alert-rules") return Promise.resolve({ data: { rules: [alertRule, secondRule] } });
      if (path === "/api/alert-rules/{id}/events" && options?.params?.path?.id === "rule-1") {
        return firstEvents.promise;
      }
      if (path === "/api/alert-rules/{id}/events" && options?.params?.path?.id === "rule-2") {
        return secondEvents.promise;
      }
      throw new Error(`unexpected GET ${path}`);
    });

    render(AccountPage);
    await waitFor(() => expect(screen.getByText("Arrow nightly")).toBeInTheDocument());

    await fireEvent.click(screen.getByRole("button", { name: /events for arrow nightly/i }));
    await fireEvent.click(screen.getByRole("button", { name: /events for arrow commits/i }));
    secondEvents.resolve({
      data: {
        events: [
          {
            id: "event-2",
            rule_id: "rule-2",
            kind: "resolved",
            status: "success",
            status_reason: "second rule resolved",
            report_url: "/ci/report?run_ids=run-2",
            summary: {},
            created_at: "2026-01-05T00:00:00Z",
          },
        ],
      },
    });
    await waitFor(() => expect(screen.getByText("second rule resolved")).toBeInTheDocument());

    firstEvents.resolve({ error: { detail: "first rule timed out" } });
    await firstEvents.promise;
    await waitFor(() => expect(screen.queryByText("first rule timed out")).not.toBeInTheDocument());
    expect(screen.getByRole("link", { name: /report for event-2/i })).toHaveAttribute(
      "href",
      "/ci/report?run_ids=run-2",
    );
  });

  it("logs out and returns to the signed-out state", async () => {
    mockSignedIn();
    POST.mockResolvedValueOnce({ response: { status: 204 } });

    render(AccountPage);
    await waitFor(() => expect(screen.getByText("author@example.com")).toBeInTheDocument());

    await fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    await waitFor(() => expect(screen.getByRole("link", { name: /sign in/i })).toBeInTheDocument());
    expect(POST).toHaveBeenCalledWith("/api/auth/logout");
  });
});
