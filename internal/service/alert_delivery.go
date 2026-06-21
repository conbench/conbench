package service

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"mime"
	"net"
	"net/http"
	"net/mail"
	"net/smtp"
	"net/url"
	"strings"
	"time"

	"github.com/conbench/conbench/internal/storage"
)

type AlertDeliveryStore interface {
	EnqueueAlertDeliveries(ctx context.Context, p storage.EnqueueAlertDeliveriesParams) (int, error)
	ClaimPendingAlertDeliveries(ctx context.Context, p storage.ClaimPendingAlertDeliveriesParams) ([]storage.AlertDelivery, error)
	MarkAlertDeliveryDelivered(ctx context.Context, p storage.MarkAlertDeliveryDeliveredParams) (storage.AlertDelivery, error)
	MarkAlertDeliveryFailed(ctx context.Context, p storage.MarkAlertDeliveryFailedParams) (storage.AlertDelivery, error)
}

const (
	AlertDeliveryChannelWebhook       = "webhook"
	AlertDeliveryChannelSlack         = "slack"
	AlertDeliveryChannelGitHubCheck   = "github-check"
	AlertDeliveryChannelGitHubComment = "github-comment"
	AlertDeliveryChannelEmail         = "email"
)

type AlertDeliverySender interface {
	SendAlertDelivery(ctx context.Context, payload AlertDeliveryPayload) error
}

type AlertDeliveryOptions struct {
	Channel    string
	Target     string
	Limit      int32
	RetryAfter time.Duration
}

type AlertDeliverySummary struct {
	Enqueued  int                    `json:"enqueued"`
	Attempted int                    `json:"attempted"`
	Delivered int                    `json:"delivered"`
	Failed    int                    `json:"failed"`
	Failures  []AlertDeliveryFailure `json:"failures,omitempty"`
}

type AlertDeliveryFailure struct {
	DeliveryID string `json:"delivery_id"`
	EventID    string `json:"event_id"`
	Error      string `json:"error"`
}

type AlertDeliveryPayload struct {
	DeliveryID string             `json:"delivery_id"`
	Channel    string             `json:"channel"`
	Target     string             `json:"-"`
	Event      AlertDeliveryEvent `json:"event"`
}

type AlertDeliveryEvent struct {
	ID           string          `json:"id"`
	RuleID       string          `json:"rule_id"`
	Kind         string          `json:"kind"`
	Status       string          `json:"status"`
	StatusReason string          `json:"status_reason"`
	RunID        *string         `json:"run_id,omitempty"`
	CommitSHA    *string         `json:"commit_sha,omitempty"`
	Repository   string          `json:"repository,omitempty"`
	ReportURL    string          `json:"report_url"`
	Summary      json.RawMessage `json:"summary"`
	CreatedAt    time.Time       `json:"created_at"`
}

type AlertDeliveryDispatcher struct {
	store  AlertDeliveryStore
	sender AlertDeliverySender
	now    func() time.Time
}

func NewAlertDeliveryDispatcher(
	store AlertDeliveryStore,
	sender AlertDeliverySender,
	now func() time.Time,
) *AlertDeliveryDispatcher {
	if now == nil {
		now = func() time.Time { return time.Now().UTC() }
	}
	return &AlertDeliveryDispatcher{store: store, sender: sender, now: now}
}

func (d *AlertDeliveryDispatcher) Deliver(
	ctx context.Context,
	options AlertDeliveryOptions,
) (AlertDeliverySummary, error) {
	now := d.now().UTC()
	enqueued, err := d.store.EnqueueAlertDeliveries(ctx, storage.EnqueueAlertDeliveriesParams{
		Channel:   options.Channel,
		Target:    options.Target,
		Limit:     options.Limit,
		CreatedAt: now,
	})
	if err != nil {
		return AlertDeliverySummary{}, err
	}
	summary := AlertDeliverySummary{Enqueued: enqueued}
	for remaining := options.Limit; remaining > 0; remaining-- {
		claimAt := d.now().UTC()
		deliveries, err := d.store.ClaimPendingAlertDeliveries(ctx, storage.ClaimPendingAlertDeliveriesParams{
			Channel:    options.Channel,
			Target:     options.Target,
			Now:        claimAt,
			LeaseUntil: claimAt.Add(options.RetryAfter),
			Limit:      1,
		})
		if err != nil {
			return summary, err
		}
		if len(deliveries) == 0 {
			break
		}
		delivery := deliveries[0]
		summary.Attempted++
		payload := AlertDeliveryPayload{
			DeliveryID: delivery.ID,
			Channel:    delivery.Channel,
			Target:     delivery.Target,
			Event:      alertDeliveryEventOf(delivery.Event),
		}
		if err := d.sender.SendAlertDelivery(ctx, payload); err != nil {
			attemptedAt := d.now().UTC()
			summary.Failed++
			summary.Failures = append(summary.Failures, AlertDeliveryFailure{
				DeliveryID: delivery.ID,
				EventID:    delivery.EventID,
				Error:      err.Error(),
			})
			_, markErr := d.store.MarkAlertDeliveryFailed(ctx, storage.MarkAlertDeliveryFailedParams{
				ID:            delivery.ID,
				Error:         err.Error(),
				AttemptedAt:   attemptedAt,
				NextAttemptAt: attemptedAt.Add(options.RetryAfter),
			})
			if markErr != nil {
				return summary, markErr
			}
			continue
		}
		attemptedAt := d.now().UTC()
		_, err = d.store.MarkAlertDeliveryDelivered(ctx, storage.MarkAlertDeliveryDeliveredParams{
			ID:          delivery.ID,
			AttemptedAt: attemptedAt,
		})
		if err != nil {
			return summary, err
		}
		summary.Delivered++
	}
	if summary.Failed > 0 {
		return summary, errors.New("one or more alert deliveries failed")
	}
	return summary, nil
}

func alertDeliveryEventOf(event storage.AlertEvent) AlertDeliveryEvent {
	return AlertDeliveryEvent{
		ID:           event.ID,
		RuleID:       event.RuleID,
		Kind:         event.Kind,
		Status:       event.Status,
		StatusReason: event.StatusReason,
		RunID:        event.RunID,
		CommitSHA:    event.CommitSHA,
		Repository:   event.Repository,
		ReportURL:    event.ReportURL,
		Summary:      rawJSONOrNull(event.Summary),
		CreatedAt:    event.CreatedAt,
	}
}

func rawJSONOrNull(b []byte) json.RawMessage {
	if len(b) == 0 {
		return json.RawMessage("null")
	}
	return json.RawMessage(b)
}

type WebhookAlertDeliverySender struct {
	client *http.Client
}

func NewWebhookAlertDeliverySender(client *http.Client) *WebhookAlertDeliverySender {
	if client == nil {
		client = http.DefaultClient
	}
	return &WebhookAlertDeliverySender{client: client}
}

func (s *WebhookAlertDeliverySender) SendAlertDelivery(ctx context.Context, payload AlertDeliveryPayload) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("encode webhook payload: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, payload.Target, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build webhook request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "conbench-alert-delivery")
	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("post webhook: request failed")
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("post webhook: unexpected HTTP status %d", resp.StatusCode)
	}
	return nil
}

type SlackAlertDeliverySender struct {
	client *http.Client
}

type EmailAlertDeliverySender struct {
	addr     string
	from     string
	username string
	password string
	timeout  time.Duration
}

func NewSlackAlertDeliverySender(client *http.Client) *SlackAlertDeliverySender {
	if client == nil {
		client = http.DefaultClient
	}
	return &SlackAlertDeliverySender{client: client}
}

func NewEmailAlertDeliverySender(addr, from, username, password string) *EmailAlertDeliverySender {
	return &EmailAlertDeliverySender{
		addr:     addr,
		from:     from,
		username: username,
		password: password,
		timeout:  10 * time.Second,
	}
}

func (s *EmailAlertDeliverySender) WithTimeout(timeout time.Duration) *EmailAlertDeliverySender {
	s.timeout = timeout
	return s
}

func (s *SlackAlertDeliverySender) SendAlertDelivery(ctx context.Context, payload AlertDeliveryPayload) error {
	body, err := json.Marshal(slackAlertDeliveryMessage(payload.Event))
	if err != nil {
		return fmt.Errorf("encode slack payload: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, payload.Target, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build slack request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "conbench-alert-delivery")
	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("post slack webhook: request failed")
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("post slack webhook: unexpected HTTP status %d", resp.StatusCode)
	}
	return nil
}

func (s *EmailAlertDeliverySender) SendAlertDelivery(ctx context.Context, payload AlertDeliveryPayload) error {
	from, fromHeader, err := NormalizeAlertEmailFrom(s.from)
	if err != nil {
		return fmt.Errorf("send email alert: %w", err)
	}
	_, recipients, err := NormalizeAlertEmailRecipients(payload.Target)
	if err != nil {
		return fmt.Errorf("send email alert: %w", err)
	}
	host, err := ValidateAlertEmailSMTPAddr(s.addr)
	if err != nil {
		return fmt.Errorf("send email alert: %w", err)
	}
	auth, err := s.smtpAuth(host)
	if err != nil {
		return fmt.Errorf("send email alert: %w", err)
	}
	msg := emailAlertMessage(fromHeader, recipients, payload.Event)
	if err := s.sendMail(ctx, host, auth, from, recipients, msg); err != nil {
		return fmt.Errorf("send email alert: %w", err)
	}
	return nil
}

func (s *EmailAlertDeliverySender) smtpAuth(host string) (smtp.Auth, error) {
	if s.username == "" && s.password == "" {
		return nil, nil
	}
	if s.username == "" || s.password == "" {
		return nil, errors.New("email username and password must be set together")
	}
	return smtp.PlainAuth("", s.username, s.password, host), nil
}

func (s *EmailAlertDeliverySender) sendMail(
	ctx context.Context,
	host string,
	auth smtp.Auth,
	from string,
	recipients []string,
	msg []byte,
) error {
	deadline, hasDeadline := emailAlertDeliveryDeadline(ctx, s.timeout, time.Now())
	dialCtx := ctx
	if hasDeadline {
		var cancel context.CancelFunc
		dialCtx, cancel = context.WithDeadline(ctx, deadline)
		defer cancel()
	}
	dialer := net.Dialer{}
	if hasDeadline {
		dialer.Deadline = deadline
	}
	conn, err := dialer.DialContext(dialCtx, "tcp", s.addr)
	if err != nil {
		return errors.New("connect smtp server failed")
	}
	defer conn.Close()
	if hasDeadline {
		if err := conn.SetDeadline(deadline); err != nil {
			return fmt.Errorf("set smtp deadline: %w", err)
		}
	}
	client, err := smtp.NewClient(conn, host)
	if err != nil {
		return errors.New("create smtp client failed")
	}
	defer client.Close()
	if ok, _ := client.Extension("STARTTLS"); ok {
		if err := client.StartTLS(&tls.Config{ServerName: host, MinVersion: tls.VersionTLS12}); err != nil {
			return errors.New("start smtp tls failed")
		}
	}
	if auth != nil {
		if ok, _ := client.Extension("AUTH"); !ok {
			return errors.New("smtp server does not support auth")
		}
		if err := client.Auth(auth); err != nil {
			return errors.New("smtp auth failed")
		}
	}
	if err := client.Mail(from); err != nil {
		return errors.New("smtp mail from failed")
	}
	for _, recipient := range recipients {
		if err := client.Rcpt(recipient); err != nil {
			return errors.New("smtp recipient failed")
		}
	}
	writer, err := client.Data()
	if err != nil {
		return errors.New("smtp data failed")
	}
	if _, err := writer.Write(msg); err != nil {
		return errors.New("write smtp message failed")
	}
	if err := writer.Close(); err != nil {
		return errors.New("close smtp message failed")
	}
	if err := client.Quit(); err != nil {
		return errors.New("smtp quit failed")
	}
	return nil
}

func emailAlertDeliveryDeadline(ctx context.Context, timeout time.Duration, now time.Time) (time.Time, bool) {
	deadline, hasDeadline := ctx.Deadline()
	if timeout <= 0 {
		return deadline, hasDeadline
	}
	timeoutDeadline := now.Add(timeout)
	if !hasDeadline || timeoutDeadline.Before(deadline) {
		return timeoutDeadline, true
	}
	return deadline, true
}

func ValidateAlertEmailSMTPAddr(raw string) (string, error) {
	host, port, err := net.SplitHostPort(raw)
	if err != nil || host == "" || port == "" {
		return "", errors.New("email smtp address must be host:port")
	}
	return host, nil
}

func NormalizeAlertEmailFrom(raw string) (string, string, error) {
	address, err := mail.ParseAddress(raw)
	if err != nil || address.Address == "" {
		return "", "", errors.New("email from address is invalid")
	}
	return address.Address, strings.TrimSpace(raw), nil
}

func NormalizeAlertEmailRecipients(raw string) (string, []string, error) {
	addresses, err := mail.ParseAddressList(raw)
	if err != nil || len(addresses) == 0 {
		return "", nil, errors.New("email recipients are invalid")
	}
	recipients := make([]string, 0, len(addresses))
	seen := make(map[string]struct{}, len(addresses))
	for _, address := range addresses {
		if address.Address == "" {
			return "", nil, errors.New("email recipients are invalid")
		}
		key := strings.ToLower(address.Address)
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		recipients = append(recipients, address.Address)
	}
	if len(recipients) == 0 {
		return "", nil, errors.New("email recipients are invalid")
	}
	return strings.Join(recipients, ","), recipients, nil
}

type GitHubCheckAlertDeliverySender struct {
	client  *http.Client
	token   string
	baseURL string
}

type GitHubCommentAlertDeliverySender struct {
	client  *http.Client
	token   string
	baseURL string
}

type githubCheckRunRequest struct {
	Name       string               `json:"name"`
	HeadSHA    string               `json:"head_sha"`
	Status     string               `json:"status"`
	Conclusion string               `json:"conclusion"`
	DetailsURL string               `json:"details_url,omitempty"`
	ExternalID string               `json:"external_id,omitempty"`
	Output     githubCheckRunOutput `json:"output"`
}

type githubCheckRunOutput struct {
	Title   string `json:"title"`
	Summary string `json:"summary"`
}

type githubCommitCommentRequest struct {
	Body string `json:"body"`
}

func NewGitHubCheckAlertDeliverySender(client *http.Client, token, baseURL string) *GitHubCheckAlertDeliverySender {
	if client == nil {
		client = http.DefaultClient
	}
	if baseURL == "" {
		baseURL = "https://api.github.com"
	}
	return &GitHubCheckAlertDeliverySender{
		client:  client,
		token:   token,
		baseURL: strings.TrimRight(baseURL, "/"),
	}
}

func NewGitHubCommentAlertDeliverySender(client *http.Client, token, baseURL string) *GitHubCommentAlertDeliverySender {
	if client == nil {
		client = http.DefaultClient
	}
	if baseURL == "" {
		baseURL = "https://api.github.com"
	}
	return &GitHubCommentAlertDeliverySender{
		client:  client,
		token:   token,
		baseURL: strings.TrimRight(baseURL, "/"),
	}
}

func (s *GitHubCheckAlertDeliverySender) SendAlertDelivery(
	ctx context.Context,
	payload AlertDeliveryPayload,
) error {
	if payload.Event.CommitSHA == nil || *payload.Event.CommitSHA == "" {
		return errors.New("post github check run: alert event has no commit sha")
	}
	repository := payload.Target
	if repository == "" {
		repository = payload.Event.Repository
	}
	repositorySpec, err := githubRepositorySpec(repository)
	if err != nil {
		return fmt.Errorf("post github check run: %w", err)
	}
	body := githubCheckRunRequest{
		Name:       "Conbench alert",
		HeadSHA:    *payload.Event.CommitSHA,
		Status:     "completed",
		Conclusion: githubCheckConclusion(payload.Event.Status),
		ExternalID: payload.Event.ID,
		Output: githubCheckRunOutput{
			Title:   fmt.Sprintf("Conbench alert: %s", payload.Event.Status),
			Summary: githubCheckSummary(payload.Event),
		},
	}
	if isAbsoluteHTTPURL(payload.Event.ReportURL) {
		body.DetailsURL = payload.Event.ReportURL
	}
	encoded, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("encode github check run: %w", err)
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		s.baseURL+"/repos/"+repositorySpec+"/check-runs",
		bytes.NewReader(encoded),
	)
	if err != nil {
		return fmt.Errorf("build github check run request: %w", err)
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("Authorization", "Bearer "+s.token)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "conbench-alert-delivery")
	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("post github check run: request failed")
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("post github check run: unexpected HTTP status %d", resp.StatusCode)
	}
	return nil
}

func (s *GitHubCommentAlertDeliverySender) SendAlertDelivery(
	ctx context.Context,
	payload AlertDeliveryPayload,
) error {
	if payload.Event.CommitSHA == nil || *payload.Event.CommitSHA == "" {
		return errors.New("post github commit comment: alert event has no commit sha")
	}
	repository := payload.Target
	if repository == "" {
		repository = payload.Event.Repository
	}
	repositorySpec, err := githubRepositorySpec(repository)
	if err != nil {
		return fmt.Errorf("post github commit comment: %w", err)
	}
	body := githubCommitCommentRequest{Body: githubCommentBody(payload.Event)}
	encoded, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("encode github commit comment: %w", err)
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		s.baseURL+"/repos/"+repositorySpec+"/commits/"+url.PathEscape(*payload.Event.CommitSHA)+"/comments",
		bytes.NewReader(encoded),
	)
	if err != nil {
		return fmt.Errorf("build github commit comment request: %w", err)
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("Authorization", "Bearer "+s.token)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "conbench-alert-delivery")
	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("post github commit comment: request failed")
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("post github commit comment: unexpected HTTP status %d", resp.StatusCode)
	}
	return nil
}

func githubRepositorySpec(raw string) (string, error) {
	if rest, ok := strings.CutPrefix(raw, "git@github.com:"); ok {
		raw = "https://github.com/" + rest
	}
	u, err := url.Parse(strings.TrimRight(raw, "/"))
	if err != nil || u.Scheme != "https" || u.Host != "github.com" {
		return "", errors.New("target must be a github.com repository URL")
	}
	parts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", errors.New("target must be a github.com repository URL")
	}
	owner, repo := parts[0], strings.TrimSuffix(parts[1], ".git")
	if repo == "" {
		return "", errors.New("target must be a github.com repository URL")
	}
	return url.PathEscape(owner) + "/" + url.PathEscape(repo), nil
}

func githubCheckConclusion(status string) string {
	switch status {
	case string(CIReportStatusSuccess):
		return "success"
	case string(CIReportStatusFailure):
		return "failure"
	default:
		return "neutral"
	}
}

func githubCheckSummary(event AlertDeliveryEvent) string {
	summary := event.StatusReason
	if event.ReportURL != "" {
		summary += "\n\nReport: " + event.ReportURL
	}
	if event.RunID != nil && *event.RunID != "" {
		summary += "\nRun: " + *event.RunID
	}
	return summary
}

func githubCommentBody(event AlertDeliveryEvent) string {
	var b strings.Builder
	fmt.Fprintf(&b, "### Conbench alert: %s\n\n", event.Status)
	b.WriteString(event.StatusReason)
	if event.ReportURL != "" {
		if isAbsoluteHTTPURL(event.ReportURL) {
			fmt.Fprintf(&b, "\n\n[Open Conbench report](%s)", event.ReportURL)
		} else {
			fmt.Fprintf(&b, "\n\nReport: `%s`", event.ReportURL)
		}
	}
	if event.RunID != nil && *event.RunID != "" {
		fmt.Fprintf(&b, "\n\nRun: `%s`", *event.RunID)
	}
	fmt.Fprintf(&b, "\n\nAlert event: `%s`", event.ID)
	return b.String()
}

func emailAlertMessage(fromHeader string, recipients []string, event AlertDeliveryEvent) []byte {
	subject := sanitizeEmailHeader("Conbench alert: " + event.Status)
	headers := []string{
		"From: " + sanitizeEmailHeader(fromHeader),
		"To: " + sanitizeEmailHeader(strings.Join(recipients, ", ")),
		"Subject: " + mime.QEncoding.Encode("utf-8", subject),
		"Date: " + event.CreatedAt.UTC().Format(time.RFC1123Z),
		"MIME-Version: 1.0",
		"Content-Type: text/plain; charset=utf-8",
		"Content-Transfer-Encoding: 8bit",
	}
	body := emailAlertBody(event)
	return []byte(strings.Join(headers, "\r\n") + "\r\n\r\n" + body)
}

func emailAlertBody(event AlertDeliveryEvent) string {
	var b strings.Builder
	fmt.Fprintf(&b, "Conbench alert: %s\n\n", event.Status)
	fmt.Fprintf(&b, "Kind: %s\n", event.Kind)
	fmt.Fprintf(&b, "Reason: %s\n", event.StatusReason)
	if event.ReportURL != "" {
		fmt.Fprintf(&b, "Report: %s\n", event.ReportURL)
	}
	if event.Repository != "" {
		fmt.Fprintf(&b, "Repository: %s\n", event.Repository)
	}
	if event.CommitSHA != nil && *event.CommitSHA != "" {
		fmt.Fprintf(&b, "Commit: %s\n", *event.CommitSHA)
	}
	if event.RunID != nil && *event.RunID != "" {
		fmt.Fprintf(&b, "Run: %s\n", *event.RunID)
	}
	fmt.Fprintf(&b, "Alert event: %s\n", event.ID)
	fmt.Fprintf(&b, "Alert rule: %s\n", event.RuleID)
	fmt.Fprintf(&b, "Created at: %s\n", event.CreatedAt.UTC().Format(time.RFC3339))
	return b.String()
}

func sanitizeEmailHeader(value string) string {
	replacer := strings.NewReplacer("\r", " ", "\n", " ")
	return replacer.Replace(value)
}

type slackBlock struct {
	Type string         `json:"type"`
	Text slackTextBlock `json:"text"`
}

type slackTextBlock struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type slackMessage struct {
	Text   string       `json:"text"`
	Blocks []slackBlock `json:"blocks"`
}

func slackAlertDeliveryMessage(event AlertDeliveryEvent) slackMessage {
	text := fmt.Sprintf("Conbench alert: %s - %s - %s", event.Status, event.StatusReason, event.ReportURL)
	message := slackMessage{
		Text: text,
		Blocks: []slackBlock{
			{
				Type: "section",
				Text: slackTextBlock{
					Type: "mrkdwn",
					Text: fmt.Sprintf("*Conbench alert:* %s\n%s", event.Status, event.StatusReason),
				},
			},
		},
	}
	if isAbsoluteHTTPURL(event.ReportURL) {
		message.Blocks = append(message.Blocks, slackBlock{
			Type: "section",
			Text: slackTextBlock{
				Type: "mrkdwn",
				Text: fmt.Sprintf("<%s|Open report>", event.ReportURL),
			},
		})
	}
	return message
}

func isAbsoluteHTTPURL(raw string) bool {
	u, err := url.Parse(raw)
	return err == nil && u.Host != "" && (u.Scheme == "http" || u.Scheme == "https")
}
