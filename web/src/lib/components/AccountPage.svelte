<script lang="ts">
  import { onMount } from "svelte";

  import { createConbenchClient } from "../api/client";
  import type { components } from "../api/schema";

  type User = components["schemas"]["MeOutputBody"];
  type Token = components["schemas"]["TokenView"];
  type CreatedToken = components["schemas"]["CreateTokenOutputBody"];
  type AlertRule = components["schemas"]["AlertRuleView"];
  type AlertEvent = components["schemas"]["AlertEventView"];
  type LoadState = "loading" | "signed-out" | "signed-in" | "error";

  let { baseUrl = "" }: { baseUrl?: string } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let loadState = $state<LoadState>("loading");
  let user = $state<User | null>(null);
  let tokens = $state<Token[]>([]);
  let alertRules = $state<AlertRule[]>([]);
  let eventsByRule = $state<Record<string, AlertEvent[]>>({});
  let selectedRuleID = $state<string | null>(null);

  let pageError = $state<string | null>(null);
  let tokenError = $state<string | null>(null);
  let alertError = $state<string | null>(null);
  let eventsError = $state<string | null>(null);
  let logoutError = $state<string | null>(null);
  let eventsLoading = $state(false);

  let tokenName = $state("");
  let createdToken = $state<CreatedToken | null>(null);

  let ruleName = $state("");
  let ruleRepository = $state("");
  let ruleBaseline = $state("fork_point");
  let ruleRunReason = $state("");
  let ruleThreshold = $state("5");
  let ruleThresholdZ = $state("5");
  let ruleEnabled = $state(true);
  let eventRequestToken = 0;

  onMount(() => {
    void load();
  });

  async function load() {
    loadState = "loading";
    pageError = null;
    let me;
    try {
      me = await client.GET("/api/users/me");
    } catch (err) {
      loadState = "error";
      pageError = messageOf(err, "failed to load account");
      return;
    }
    if (me.error || !me.data) {
      if (isAuthError(me)) {
        loadState = "signed-out";
        user = null;
        pageError = detailOf(me.error, "authentication required");
        return;
      }
      loadState = "error";
      pageError = detailOf(me.error, "failed to load account");
      return;
    }

    user = me.data;
    loadState = "signed-in";
    await Promise.all([loadTokens(), loadAlertRules()]);
  }

  async function loadTokens() {
    tokenError = null;
    let res;
    try {
      res = await client.GET("/api/tokens");
    } catch (err) {
      tokenError = messageOf(err, "failed to load API tokens");
      return;
    }
    if (res.error || !res.data) {
      tokenError = detailOf(res.error, "failed to load API tokens");
      return;
    }
    tokens = res.data.tokens ?? [];
  }

  async function loadAlertRules() {
    alertError = null;
    let res;
    try {
      res = await client.GET("/api/alert-rules");
    } catch (err) {
      alertError = messageOf(err, "failed to load alert rules");
      return;
    }
    if (res.error || !res.data) {
      alertError = detailOf(res.error, "failed to load alert rules");
      return;
    }
    alertRules = res.data.rules ?? [];
  }

  async function createToken(e: SubmitEvent) {
    e.preventDefault();
    const name = tokenName.trim();
    if (name === "") {
      tokenError = "token name is required";
      return;
    }

    tokenError = null;
    createdToken = null;
    let res;
    try {
      res = await client.POST("/api/tokens", { body: { name } });
    } catch (err) {
      tokenError = messageOf(err, "failed to create API token");
      return;
    }
    if (res.error || !res.data) {
      tokenError = detailOf(res.error, "failed to create API token");
      return;
    }

    createdToken = res.data;
    tokens = [
      {
        id: res.data.id,
        name: res.data.name,
        prefix: res.data.prefix,
        created_at: res.data.created_at,
      },
      ...tokens,
    ];
    tokenName = "";
  }

  async function revokeToken(token: Token) {
    tokenError = null;
    let res;
    try {
      res = await client.DELETE("/api/tokens/{id}", { params: { path: { id: token.id } } });
    } catch (err) {
      tokenError = messageOf(err, `failed to revoke ${token.name}`);
      return;
    }
    if (res.error) {
      tokenError = detailOf(res.error, `failed to revoke ${token.name}`);
      return;
    }
    tokens = tokens.filter((row) => row.id !== token.id);
  }

  async function createAlertRule(e: SubmitEvent) {
    e.preventDefault();
    const name = ruleName.trim();
    const repository = ruleRepository.trim();
    if (name === "" || repository === "") {
      alertError = "rule name and repository are required";
      return;
    }

    alertError = null;
    const body: {
      name: string;
      repository: string;
      baseline: string;
      enabled: boolean;
      threshold?: number;
      threshold_z?: number;
      run_reason?: string;
    } = {
      name,
      repository,
      baseline: ruleBaseline,
      enabled: ruleEnabled,
    };
    const threshold = positiveNumber(ruleThreshold);
    const thresholdZ = positiveNumber(ruleThresholdZ);
    const runReason = ruleRunReason.trim();
    if (threshold !== null) body.threshold = threshold;
    if (thresholdZ !== null) body.threshold_z = thresholdZ;
    if (runReason !== "") body.run_reason = runReason;

    let res;
    try {
      res = await client.POST("/api/alert-rules", { body });
    } catch (err) {
      alertError = messageOf(err, "failed to create alert rule");
      return;
    }
    if (res.error || !res.data) {
      alertError = detailOf(res.error, "failed to create alert rule");
      return;
    }

    alertRules = [res.data, ...alertRules];
    ruleName = "";
    ruleRepository = "";
    ruleRunReason = "";
    ruleBaseline = "fork_point";
    ruleThreshold = "5";
    ruleThresholdZ = "5";
    ruleEnabled = true;
  }

  async function deleteAlertRule(rule: AlertRule) {
    alertError = null;
    let res;
    try {
      res = await client.DELETE("/api/alert-rules/{id}", { params: { path: { id: rule.id } } });
    } catch (err) {
      alertError = messageOf(err, `failed to delete ${rule.name}`);
      return;
    }
    if (res.error) {
      alertError = detailOf(res.error, `failed to delete ${rule.name}`);
      return;
    }
    alertRules = alertRules.filter((row) => row.id !== rule.id);
    const { [rule.id]: _removed, ...remaining } = eventsByRule;
    eventsByRule = remaining;
    if (selectedRuleID === rule.id) {
      eventRequestToken += 1;
      selectedRuleID = null;
      eventsLoading = false;
      eventsError = null;
    }
  }

  async function loadEvents(rule: AlertRule) {
    const requestToken = ++eventRequestToken;
    selectedRuleID = rule.id;
    eventsError = null;
    eventsLoading = true;
    try {
      const res = await client.GET("/api/alert-rules/{id}/events", {
        params: { path: { id: rule.id }, query: { limit: 50 } },
      });
      if (!isCurrentEventRequest(requestToken, rule.id)) return;
      if (res.error || !res.data) {
        eventsError = detailOf(res.error, `failed to load events for ${rule.name}`);
        return;
      }
      eventsByRule = { ...eventsByRule, [rule.id]: res.data.events ?? [] };
      eventsError = null;
    } catch (err) {
      if (!isCurrentEventRequest(requestToken, rule.id)) return;
      eventsError = messageOf(err, `failed to load events for ${rule.name}`);
    } finally {
      if (isCurrentEventRequest(requestToken, rule.id)) {
        eventsLoading = false;
      }
    }
  }

  async function logout() {
    logoutError = null;
    let res;
    try {
      res = await client.POST("/api/auth/logout");
    } catch (err) {
      logoutError = messageOf(err, "failed to log out");
      return;
    }
    if (res.error) {
      logoutError = detailOf(res.error, "failed to log out");
      return;
    }
    loadState = "signed-out";
    user = null;
    tokens = [];
    alertRules = [];
    eventsByRule = {};
    selectedRuleID = null;
    pageError = "authentication required";
  }

  function isCurrentEventRequest(requestToken: number, ruleID: string): boolean {
    return requestToken === eventRequestToken && selectedRuleID === ruleID;
  }

  function isAuthError(res: { error?: unknown; response?: Response }): boolean {
    return res.response?.status === 401 || detailOf(res.error, "").toLowerCase().includes("authentication");
  }

  function detailOf(error: unknown, fallback: string): string {
    if (error && typeof error === "object" && "detail" in error && typeof error.detail === "string") {
      return error.detail;
    }
    return fallback;
  }

  function messageOf(error: unknown, fallback: string): string {
    const detail = detailOf(error, "");
    if (detail !== "") return detail;
    if (error instanceof Error) return error.message;
    if (typeof error === "string" && error !== "") return error;
    return fallback;
  }

  function positiveNumber(raw: string | number): number | null {
    const text = String(raw).trim();
    if (text === "") return null;
    const n = Number(text);
    return Number.isFinite(n) && n > 0 ? n : null;
  }

  function dateText(value: string | undefined | null): string {
    if (!value) return "never";
    return new Date(value).toLocaleString();
  }

  function shortID(value: string | undefined): string {
    if (!value) return "-";
    return value.length <= 12 ? value : value.slice(0, 12);
  }

  function selectedEvents(): AlertEvent[] {
    return selectedRuleID === null ? [] : (eventsByRule[selectedRuleID] ?? []);
  }
</script>

<main class="page account-page">
  <header class="page-header">
    <div>
      <p class="eyebrow">Account</p>
      <h1>Account</h1>
      <p class="page-subtitle">Session identity, user-owned tokens, and server-side alert rules.</p>
    </div>
    {#if loadState === "signed-in" && user !== null}
      <div class="page-actions">
        <button type="button" class="secondary-button" onclick={logout}>Log out</button>
      </div>
    {/if}
  </header>

  {#if loadState === "loading"}
    <section class="panel empty-panel"><p>Loading…</p></section>
  {:else if loadState === "error"}
    <section class="panel empty-panel">
      <h2>Account unavailable</h2>
      <p class="error">{pageError}</p>
    </section>
  {:else if loadState === "signed-out"}
    <section class="panel signed-out">
      <div>
        <h2>Signed out</h2>
        <p>{pageError ?? "authentication required"}</p>
      </div>
      <a class="primary-link" href="/api/auth/login">Sign in</a>
    </section>
  {:else if user !== null}
    <section class="account-grid" aria-label="Account overview">
      <div class="panel identity-panel">
        <h2>Identity</h2>
        <dl>
          <dt>Name</dt>
          <dd>{user.name || "not set"}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>User ID</dt>
          <dd><code>{user.id}</code></dd>
        </dl>
        {#if logoutError}
          <p class="error">{logoutError}</p>
        {/if}
      </div>

      <section class="panel token-panel" aria-label="API tokens">
        <div class="section-head">
          <div>
            <h2>API tokens</h2>
            <p>{tokens.length} active or recently revoked token{tokens.length === 1 ? "" : "s"}</p>
          </div>
        </div>

        <form class="inline-form" data-testid="token-create-form" onsubmit={createToken}>
          <label>
            <span>Token name</span>
            <input bind:value={tokenName} autocomplete="off" />
          </label>
          <button type="submit">Create token</button>
        </form>

        {#if createdToken}
          <div class="secret-box" role="status">
            <span>{createdToken.name}</span>
            <code>{createdToken.token}</code>
          </div>
        {/if}
        {#if tokenError}
          <p class="error">{tokenError}</p>
        {/if}

        {#if tokens.length === 0}
          <p class="empty-copy">No API tokens.</p>
        {:else}
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Prefix</th>
                  <th>Created</th>
                  <th>Last used</th>
                  <th>Status</th>
                  <th><span class="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {#each tokens as token (token.id)}
                  <tr>
                    <td>{token.name}</td>
                    <td><code>{token.prefix}</code></td>
                    <td>{dateText(token.created_at)}</td>
                    <td>{dateText(token.last_used_at)}</td>
                    <td>{token.revoked_at ? "revoked" : "active"}</td>
                    <td>
                      <button
                        type="button"
                        class="link-button"
                        aria-label={`revoke ${token.name}`}
                        disabled={Boolean(token.revoked_at)}
                        onclick={() => revokeToken(token)}
                      >Revoke</button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </section>
    </section>

    <section class="panel alert-panel" aria-label="Alert rules">
      <div class="section-head">
        <div>
          <h2>Alert rules</h2>
          <p>{alertRules.length} rule{alertRules.length === 1 ? "" : "s"}</p>
        </div>
      </div>

      <form class="rule-form" data-testid="alert-create-form" onsubmit={createAlertRule}>
        <label>
          <span>Rule name</span>
          <input bind:value={ruleName} autocomplete="off" />
        </label>
        <label class="wide">
          <span>Repository</span>
          <input bind:value={ruleRepository} autocomplete="off" />
        </label>
        <label>
          <span>Baseline</span>
          <select bind:value={ruleBaseline}>
            <option value="fork_point">fork_point</option>
            <option value="parent">parent</option>
            <option value="latest_default">latest_default</option>
          </select>
        </label>
        <label>
          <span>Run reason</span>
          <input bind:value={ruleRunReason} autocomplete="off" />
        </label>
        <label>
          <span>Pairwise threshold</span>
          <input type="number" min="0" step="0.1" bind:value={ruleThreshold} />
        </label>
        <label>
          <span>Z-score threshold</span>
          <input type="number" min="0" step="0.1" bind:value={ruleThresholdZ} />
        </label>
        <label class="check-field">
          <input type="checkbox" bind:checked={ruleEnabled} />
          <span>Enabled</span>
        </label>
        <button type="submit">Create rule</button>
      </form>

      {#if alertError}
        <p class="error">{alertError}</p>
      {/if}

      {#if alertRules.length === 0}
        <p class="empty-copy">No alert rules.</p>
      {:else}
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Repository</th>
                <th>Baseline</th>
                <th>Thresholds</th>
                <th>State</th>
                <th>Evaluated</th>
                <th><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {#each alertRules as rule (rule.id)}
                <tr>
                  <td>
                    <strong>{rule.name}</strong>
                    {#if rule.run_reason}
                      <span class="subtle-inline">{rule.run_reason}</span>
                    {/if}
                  </td>
                  <td class="repo-cell">{rule.repository}</td>
                  <td><code>{rule.baseline}</code></td>
                  <td>{rule.threshold}% / {rule.threshold_z}z</td>
                  <td>
                    <span class:status-open={rule.state === "open"} class:status-disabled={!rule.enabled}>
                      {rule.enabled ? rule.state : "disabled"}
                    </span>
                  </td>
                  <td>{dateText(rule.last_evaluated_at)}</td>
                  <td class="row-actions">
                    <button type="button" class="link-button" aria-label={`events for ${rule.name}`} onclick={() => loadEvents(rule)}>
                      Events
                    </button>
                    <button type="button" class="link-button danger" aria-label={`delete ${rule.name}`} onclick={() => deleteAlertRule(rule)}>
                      Delete
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>

    {#if selectedRuleID !== null}
      <section class="panel events-panel" aria-label="Alert events">
        <div class="section-head">
          <div>
            <h2>Alert events</h2>
            <p>{eventsLoading ? "Loading" : `${selectedEvents().length} event${selectedEvents().length === 1 ? "" : "s"}`}</p>
          </div>
        </div>
        {#if eventsError}
          <p class="error">{eventsError}</p>
        {:else if !eventsLoading && selectedEvents().length === 0}
          <p class="empty-copy">No alert events.</p>
        {:else}
          <div class="events-list">
            {#each selectedEvents() as event (event.id)}
              <article class="event-row">
                <div>
                  <strong>{event.kind}</strong>
                  <span>{event.status}</span>
                  <p>{event.status_reason}</p>
                </div>
                <dl>
                  <dt>Run</dt>
                  <dd>{event.run_id ?? "-"}</dd>
                  <dt>Commit</dt>
                  <dd>{shortID(event.commit_sha)}</dd>
                  <dt>Created</dt>
                  <dd>{dateText(event.created_at)}</dd>
                </dl>
                <a href={event.report_url} aria-label={`report for ${event.id}`}>Report</a>
              </article>
            {/each}
          </div>
        {/if}
      </section>
    {/if}
  {/if}
</main>

<style>
  .account-page {
    gap: 14px;
  }
  .page-actions {
    flex-shrink: 0;
  }
  .secondary-button,
  .inline-form button,
  .rule-form button {
    min-height: 30px;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-sm);
    background: var(--c-surface);
    color: var(--c-text);
    font-weight: 700;
    cursor: pointer;
  }
  .inline-form button,
  .rule-form button {
    background: var(--c-accent);
    border-color: var(--c-accent);
    color: var(--c-on-accent);
    padding: 0 12px;
  }
  .secondary-button:hover,
  .link-button:hover {
    background: var(--c-surface-hover);
  }
  .account-grid {
    display: grid;
    grid-template-columns: minmax(250px, 0.7fr) minmax(0, 1.3fr);
    gap: 14px;
  }
  .identity-panel,
  .token-panel,
  .alert-panel,
  .events-panel,
  .signed-out,
  .empty-panel {
    padding: 14px;
  }
  .signed-out {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }
  .primary-link {
    min-height: 32px;
    display: inline-flex;
    align-items: center;
    padding: 0 12px;
    border-radius: var(--radius-sm);
    background: var(--c-accent);
    color: var(--c-on-accent);
    font-weight: 700;
    text-decoration: none;
  }
  h2 {
    margin: 0;
    font-size: 0.95rem;
  }
  .section-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }
  .section-head p,
  .signed-out p,
  .empty-copy {
    margin: 4px 0 0;
    color: var(--c-text-muted);
    font-size: 0.8rem;
  }
  dl {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 7px 12px;
    margin: 12px 0 0;
  }
  dt {
    color: var(--c-text-muted);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
  }
  dd {
    min-width: 0;
    margin: 0;
    overflow-wrap: anywhere;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.78rem;
  }
  .inline-form {
    display: grid;
    grid-template-columns: minmax(160px, 280px) max-content;
    align-items: end;
    gap: 10px;
    margin-bottom: 12px;
  }
  .rule-form {
    display: grid;
    grid-template-columns: minmax(160px, 1fr) minmax(260px, 2fr) repeat(4, minmax(120px, 0.8fr)) max-content max-content;
    align-items: end;
    gap: 10px;
    margin-bottom: 12px;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    color: var(--c-text-muted);
    font-size: 0.76rem;
    font-weight: 700;
  }
  input,
  select {
    min-height: 30px;
    min-width: 0;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-sm);
    background: var(--c-bg-inset);
    color: var(--c-text);
    padding: 0 8px;
  }
  .check-field {
    min-height: 30px;
    flex-direction: row;
    align-items: center;
    gap: 7px;
    color: var(--c-text);
  }
  .check-field input {
    min-height: auto;
  }
  .secret-box {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 8px;
    align-items: center;
    margin-bottom: 12px;
    padding: 8px 10px;
    border: 1px solid color-mix(in srgb, var(--c-success) 30%, var(--c-border-muted));
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--c-success) 9%, #fff);
  }
  .secret-box span {
    font-weight: 700;
  }
  .secret-box code {
    overflow-wrap: anywhere;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  th,
  td {
    padding: 8px;
    border-top: 1px solid var(--c-border-muted);
    text-align: left;
    vertical-align: top;
  }
  th {
    color: var(--c-text-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
  }
  .repo-cell {
    max-width: 320px;
    overflow-wrap: anywhere;
  }
  .row-actions {
    display: flex;
    gap: 8px;
    white-space: nowrap;
  }
  .link-button {
    border: 0;
    background: transparent;
    color: var(--c-accent);
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    padding: 0;
  }
  .link-button:disabled {
    color: var(--c-text-faint);
    cursor: default;
  }
  .danger {
    color: var(--c-error);
  }
  .status-open {
    color: var(--c-error);
    font-weight: 700;
  }
  .status-disabled {
    color: var(--c-text-muted);
  }
  .events-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .event-row {
    display: grid;
    grid-template-columns: minmax(180px, 1fr) minmax(260px, 1fr) max-content;
    gap: 12px;
    align-items: start;
    padding-top: 8px;
    border-top: 1px solid var(--c-border-muted);
  }
  .event-row p {
    margin: 4px 0 0;
    color: var(--c-text-muted);
  }
  .event-row span {
    margin-left: 6px;
    color: var(--c-text-muted);
  }
  .event-row dl {
    margin: 0;
  }
  .error {
    color: var(--c-error);
  }
  .subtle-inline {
    display: block;
    color: var(--c-text-muted);
    font-size: 0.75rem;
    font-weight: 400;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  @media (max-width: 1100px) {
    .account-grid,
    .rule-form {
      grid-template-columns: 1fr;
    }
    .inline-form {
      grid-template-columns: 1fr;
    }
    .event-row {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 760px) {
    .signed-out {
      align-items: flex-start;
      flex-direction: column;
    }
    th {
      display: none;
    }
    tr {
      display: grid;
      border-top: 1px solid var(--c-border-muted);
      padding: 6px 0;
    }
    td {
      border-top: 0;
      padding: 4px 0;
    }
    .row-actions {
      white-space: normal;
    }
  }
</style>
