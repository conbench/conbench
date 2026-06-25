package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/mail"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/spf13/cobra"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/commitrepair"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

const (
	defaultAdminRepairLimit           = 100
	defaultAdminRepairBackfillTimeout = 2 * time.Minute
	defaultAdminRepairGitHubTimeout   = 20 * time.Second
	defaultAdminAlertsDeliverLimit    = int32(100)
	defaultAdminAlertsDeliverRetry    = 5 * time.Minute
	defaultAdminAlertsDeliverTimeout  = 10 * time.Second
)

type adminRepairConfig struct {
	DatabaseURL     string
	GitHubToken     string
	Repository      *string
	Limit           int
	Cursor          *commitrepair.Cursor
	DryRun          bool
	Backfill        bool
	BackfillTimeout time.Duration
	GitHubTimeout   time.Duration
	Format          string
}

type adminAlertsEvaluateConfig struct {
	DatabaseURL   string
	PublicBaseURL string
	Format        string
}

type adminAlertsDeliverConfig struct {
	DatabaseURL      string
	Channel          string
	Target           string
	WebhookURL       string
	SlackWebhookURL  string
	GitHubRepository string
	GitHubToken      string
	GitHubAPIURL     string
	EmailSMTPAddr    string
	EmailFrom        string
	EmailTo          string
	EmailUsername    string
	EmailPassword    string
	Limit            int32
	RetryAfter       time.Duration
	Timeout          time.Duration
	Format           string
}

type adminTokenCreateConfig struct {
	DatabaseURL string
	Email       string
	UserName    string
	TokenName   string
}

type adminTokenCreateOutput struct {
	UserID    string    `json:"user_id"`
	TokenID   string    `json:"token_id"`
	Email     string    `json:"email"`
	UserName  string    `json:"user_name"`
	TokenName string    `json:"token_name"`
	Token     string    `json:"token"`
	Prefix    string    `json:"prefix"`
	CreatedAt time.Time `json:"created_at"`
}

var runAdminRepair = runAdminRepairReal

var runAdminAlertsEvaluate = runAdminAlertsEvaluateReal

var runAdminAlertsDeliver = runAdminAlertsDeliverReal

var runAdminTokenCreate = runAdminTokenCreateReal

var newAdminGitHubClient = newAdminGitHubClientReal

func newAdminGitHubClientReal(tokenEnv string) *commit.GitHubClient {
	return commit.NewGitHubClient(tokenEnv, "")
}

func adminAlertsEvaluateCommand(stdout, stderr io.Writer) *cobra.Command {
	return newAdminAlertsEvaluateCommand(stdout, stderr, runAdminAlertsEvaluateConfig)
}

func adminAlertsDeliverCommand(stdout, stderr io.Writer) *cobra.Command {
	return newAdminAlertsDeliverCommand(stdout, stderr, runAdminAlertsDeliverConfig)
}

func adminTokensCreateCommand(stdout, stderr io.Writer) *cobra.Command {
	return newAdminTokensCreateCommand(stdout, stderr, runAdminTokenCreateConfig)
}

func newAdminTokensCreateCommand(
	stdout, stderr io.Writer,
	run func(context.Context, adminTokenCreateConfig, io.Writer, io.Writer) error,
) *cobra.Command {
	cfg := adminTokenCreateConfig{}
	cmd := configureCommand(&cobra.Command{
		Use:   "create",
		Short: "Mint an API token for a reporter or service account.",
		Args: func(cmd *cobra.Command, args []string) error {
			if len(args) > 0 {
				return commandUsageError(cmd, "unexpected argument %q", args[0])
			}
			email, err := normalizeAdminTokenEmail(cfg.Email)
			if err != nil {
				return commandUsageError(cmd, "%s", err)
			}
			cfg.Email = email
			cfg.TokenName = strings.TrimSpace(cfg.TokenName)
			if cfg.TokenName == "" {
				return commandUsageError(cmd, "--token-name is required")
			}
			cfg.UserName = strings.TrimSpace(cfg.UserName)
			if cfg.UserName == "" {
				cfg.UserName = cfg.Email
			}
			cfg.DatabaseURL = os.Getenv("CONBENCH_DB_URL")
			if cfg.DatabaseURL == "" {
				return errors.New("CONBENCH_DB_URL is required")
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout, stderr)
		},
	})
	cmd.Flags().StringVar(&cfg.Email, "email", "", "user email to own the token")
	cmd.Flags().StringVar(&cfg.UserName, "user-name", "", "display name for a newly-created user")
	cmd.Flags().StringVar(&cfg.TokenName, "token-name", "", "display name for the token")
	return cmd
}

func normalizeAdminTokenEmail(raw string) (string, error) {
	email := strings.TrimSpace(raw)
	if email == "" {
		return "", errors.New("--email is required")
	}
	addr, err := mail.ParseAddress(email)
	if err != nil || addr.Address != email || addr.Name != "" {
		return "", errors.New("--email must be a single email address")
	}
	return email, nil
}

func runAdminTokenCreateConfig(ctx context.Context, cfg adminTokenCreateConfig, stdout, stderr io.Writer) error {
	out, err := runAdminTokenCreate(ctx, cfg, stdout, stderr)
	if err != nil {
		return err
	}
	return writeJSONLine(stdout, out)
}

func runAdminTokenCreateReal(
	ctx context.Context,
	cfg adminTokenCreateConfig,
	_ io.Writer,
	_ io.Writer,
) (adminTokenCreateOutput, error) {
	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return adminTokenCreateOutput{}, errors.New("connect database failed")
	}
	defer pool.Close()
	if err := pool.Ping(ctx); err != nil {
		return adminTokenCreateOutput{}, errors.New("connect database failed")
	}

	store := db.NewStore(pool)
	userID, err := store.GetOrCreateUserByEmail(ctx, cfg.Email, cfg.UserName, "!")
	if err != nil {
		return adminTokenCreateOutput{}, fmt.Errorf("create user: %w", err)
	}
	user, err := store.GetUserByID(ctx, userID)
	if err != nil {
		return adminTokenCreateOutput{}, fmt.Errorf("read user: %w", err)
	}
	tok, err := auth.GenerateToken()
	if err != nil {
		return adminTokenCreateOutput{}, err
	}
	now := time.Now().UTC()
	tokenID, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID:      userID,
		Name:        cfg.TokenName,
		TokenHash:   tok.Hash,
		TokenPrefix: tok.Prefix,
		CreatedAt:   now,
	})
	if err != nil {
		return adminTokenCreateOutput{}, fmt.Errorf("create token: %w", err)
	}
	return adminTokenCreateOutput{
		UserID:    userID,
		TokenID:   tokenID,
		Email:     user.Email,
		UserName:  user.Name,
		TokenName: cfg.TokenName,
		Token:     tok.Plaintext,
		Prefix:    tok.Prefix,
		CreatedAt: now,
	}, nil
}

func newAdminAlertsDeliverCommand(
	stdout, stderr io.Writer,
	run func(context.Context, adminAlertsDeliverConfig, io.Writer, io.Writer) error,
) *cobra.Command {
	cfg := adminAlertsDeliverConfig{
		Channel:    service.AlertDeliveryChannelWebhook,
		Limit:      defaultAdminAlertsDeliverLimit,
		RetryAfter: defaultAdminAlertsDeliverRetry,
		Timeout:    defaultAdminAlertsDeliverTimeout,
		Format:     "text",
	}
	cmd := configureCommand(&cobra.Command{
		Use:   "deliver",
		Short: "Deliver server-side alert events.",
		Args: func(cmd *cobra.Command, args []string) error {
			switch {
			case len(args) > 0:
				return commandUsageError(cmd, "unexpected argument %q", args[0])
			case cfg.Limit <= 0:
				return commandUsageError(cmd, "--limit must be greater than 0")
			case cfg.RetryAfter <= 0:
				return commandUsageError(cmd, "--retry-after must be greater than 0")
			case cfg.Timeout <= 0:
				return commandUsageError(cmd, "--timeout must be greater than 0")
			case cfg.RetryAfter <= cfg.Timeout:
				return commandUsageError(cmd, "--retry-after must be greater than --timeout")
			case cfg.Format != "text" && cfg.Format != "json":
				return commandUsageError(cmd, "--format must be text or json")
			case cfg.Channel != service.AlertDeliveryChannelWebhook &&
				cfg.Channel != service.AlertDeliveryChannelSlack &&
				cfg.Channel != service.AlertDeliveryChannelGitHubCheck &&
				cfg.Channel != service.AlertDeliveryChannelGitHubComment &&
				cfg.Channel != service.AlertDeliveryChannelEmail:
				return commandUsageError(cmd, "--channel must be webhook, slack, github-check, github-comment, or email")
			}
			cfg.DatabaseURL = os.Getenv("CONBENCH_DB_URL")
			if cfg.DatabaseURL == "" {
				return errors.New("CONBENCH_DB_URL is required")
			}
			switch cfg.Channel {
			case service.AlertDeliveryChannelWebhook:
				if cfg.WebhookURL == "" {
					cfg.WebhookURL = os.Getenv("CONBENCH_ALERT_WEBHOOK_URL")
				}
				if cfg.WebhookURL == "" {
					return commandUsageError(cmd, "--webhook-url or CONBENCH_ALERT_WEBHOOK_URL is required")
				}
				if err := validateAdminAlertDeliveryURL("--webhook-url", cfg.WebhookURL); err != nil {
					return commandUsageError(cmd, "%s", err)
				}
				cfg.Target = cfg.WebhookURL
			case service.AlertDeliveryChannelSlack:
				if cfg.SlackWebhookURL == "" {
					cfg.SlackWebhookURL = os.Getenv("CONBENCH_ALERT_SLACK_WEBHOOK_URL")
				}
				if cfg.SlackWebhookURL == "" {
					return commandUsageError(cmd, "--slack-webhook-url or CONBENCH_ALERT_SLACK_WEBHOOK_URL is required")
				}
				if err := validateAdminAlertDeliveryURL("--slack-webhook-url", cfg.SlackWebhookURL); err != nil {
					return commandUsageError(cmd, "%s", err)
				}
				cfg.Target = cfg.SlackWebhookURL
			case service.AlertDeliveryChannelGitHubCheck, service.AlertDeliveryChannelGitHubComment:
				if cfg.GitHubRepository == "" {
					cfg.GitHubRepository = os.Getenv("CONBENCH_ALERT_GITHUB_REPOSITORY")
				}
				if cfg.GitHubRepository == "" {
					return commandUsageError(cmd, "--github-repository or CONBENCH_ALERT_GITHUB_REPOSITORY is required")
				}
				repository, err := validateAdminAlertGitHubRepository(cfg.GitHubRepository)
				if err != nil {
					return commandUsageError(cmd, "%s", err)
				}
				cfg.GitHubRepository = repository
				cfg.Target = repository
				if cfg.GitHubToken == "" {
					cfg.GitHubToken = firstUsableGitHubTokenEnv(
						"CONBENCH_ALERT_GITHUB_TOKEN",
						"GITHUB_TOKEN",
						"GITHUB_API_TOKEN",
					)
				} else {
					cfg.GitHubToken = commit.FirstUsableGitHubToken(cfg.GitHubToken)
				}
				if cfg.GitHubToken == "" {
					return commandUsageError(
						cmd,
						"--github-token, CONBENCH_ALERT_GITHUB_TOKEN, GITHUB_TOKEN, or GITHUB_API_TOKEN is required",
					)
				}
				if cfg.GitHubAPIURL == "" {
					cfg.GitHubAPIURL = os.Getenv("CONBENCH_ALERT_GITHUB_API_URL")
				}
				if cfg.GitHubAPIURL != "" {
					if err := validateAdminAlertDeliveryURL("--github-api-url", cfg.GitHubAPIURL); err != nil {
						return commandUsageError(cmd, "%s", err)
					}
				}
			case service.AlertDeliveryChannelEmail:
				if cfg.EmailSMTPAddr == "" {
					cfg.EmailSMTPAddr = os.Getenv("CONBENCH_ALERT_EMAIL_SMTP_ADDR")
				}
				if cfg.EmailSMTPAddr == "" {
					return commandUsageError(cmd, "--email-smtp-addr or CONBENCH_ALERT_EMAIL_SMTP_ADDR is required")
				}
				if _, err := service.ValidateAlertEmailSMTPAddr(cfg.EmailSMTPAddr); err != nil {
					return commandUsageError(cmd, "%s", err)
				}
				if cfg.EmailFrom == "" {
					cfg.EmailFrom = os.Getenv("CONBENCH_ALERT_EMAIL_FROM")
				}
				if cfg.EmailFrom == "" {
					return commandUsageError(cmd, "--email-from or CONBENCH_ALERT_EMAIL_FROM is required")
				}
				_, emailFrom, err := service.NormalizeAlertEmailFrom(cfg.EmailFrom)
				if err != nil {
					return commandUsageError(cmd, "%s", err)
				}
				cfg.EmailFrom = emailFrom
				if cfg.EmailTo == "" {
					cfg.EmailTo = os.Getenv("CONBENCH_ALERT_EMAIL_TO")
				}
				if cfg.EmailTo == "" {
					return commandUsageError(cmd, "--email-to or CONBENCH_ALERT_EMAIL_TO is required")
				}
				emailTo, _, err := service.NormalizeAlertEmailRecipients(cfg.EmailTo)
				if err != nil {
					return commandUsageError(cmd, "%s", err)
				}
				cfg.EmailTo = emailTo
				cfg.Target = emailTo
				if cfg.EmailUsername == "" {
					cfg.EmailUsername = os.Getenv("CONBENCH_ALERT_EMAIL_USERNAME")
				}
				if cfg.EmailPassword == "" {
					cfg.EmailPassword = os.Getenv("CONBENCH_ALERT_EMAIL_PASSWORD")
				}
				if (cfg.EmailUsername == "") != (cfg.EmailPassword == "") {
					return commandUsageError(
						cmd,
						"CONBENCH_ALERT_EMAIL_USERNAME and CONBENCH_ALERT_EMAIL_PASSWORD must be set together",
					)
				}
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout, stderr)
		},
	})
	cmd.Flags().StringVar(&cfg.Channel, "channel", cfg.Channel, "delivery channel: webhook, slack, github-check, github-comment, or email")
	cmd.Flags().StringVar(&cfg.WebhookURL, "webhook-url", cfg.WebhookURL, "webhook URL for alert delivery (or CONBENCH_ALERT_WEBHOOK_URL)")
	cmd.Flags().StringVar(&cfg.SlackWebhookURL, "slack-webhook-url", cfg.SlackWebhookURL, "Slack incoming webhook URL for alert delivery (or CONBENCH_ALERT_SLACK_WEBHOOK_URL)")
	cmd.Flags().StringVar(&cfg.GitHubRepository, "github-repository", cfg.GitHubRepository, "GitHub repository URL for check-run delivery (or CONBENCH_ALERT_GITHUB_REPOSITORY)")
	cmd.Flags().StringVar(&cfg.GitHubToken, "github-token", cfg.GitHubToken, "GitHub token for check-run delivery (or CONBENCH_ALERT_GITHUB_TOKEN, GITHUB_TOKEN, GITHUB_API_TOKEN)")
	cmd.Flags().StringVar(&cfg.GitHubAPIURL, "github-api-url", cfg.GitHubAPIURL, "GitHub API base URL for check-run delivery (or CONBENCH_ALERT_GITHUB_API_URL)")
	cmd.Flags().StringVar(&cfg.EmailSMTPAddr, "email-smtp-addr", cfg.EmailSMTPAddr, "SMTP host:port for email alert delivery (or CONBENCH_ALERT_EMAIL_SMTP_ADDR)")
	cmd.Flags().StringVar(&cfg.EmailFrom, "email-from", cfg.EmailFrom, "from address for email alert delivery (or CONBENCH_ALERT_EMAIL_FROM)")
	cmd.Flags().StringVar(&cfg.EmailTo, "email-to", cfg.EmailTo, "comma-separated recipient addresses for email alert delivery (or CONBENCH_ALERT_EMAIL_TO)")
	cmd.Flags().StringVar(&cfg.EmailUsername, "email-username", cfg.EmailUsername, "SMTP username for email alert delivery (or CONBENCH_ALERT_EMAIL_USERNAME)")
	cmd.Flags().StringVar(&cfg.EmailPassword, "email-password", cfg.EmailPassword, "SMTP password for email alert delivery (or CONBENCH_ALERT_EMAIL_PASSWORD)")
	cmd.Flags().Int32Var(&cfg.Limit, "limit", cfg.Limit, "maximum deliveries to enqueue and attempt")
	cmd.Flags().DurationVar(&cfg.RetryAfter, "retry-after", cfg.RetryAfter, "delay before retrying a failed delivery")
	cmd.Flags().DurationVar(&cfg.Timeout, "timeout", cfg.Timeout, "delivery request timeout")
	cmd.Flags().StringVar(&cfg.Format, "format", cfg.Format, "output format: text or json")
	return cmd
}

func validateAdminAlertDeliveryURL(flagName, raw string) error {
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") {
		return fmt.Errorf("%s must be an http or https URL", flagName)
	}
	return nil
}

func validateAdminAlertGitHubRepository(raw string) (string, error) {
	normalized := commit.NormalizeRepoURL(raw)
	u, err := url.Parse(normalized)
	if err != nil || u.Scheme != "https" || u.Host != "github.com" {
		return "", errors.New("--github-repository must be a github.com repository URL")
	}
	parts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", errors.New("--github-repository must be a github.com repository URL")
	}
	return normalized, nil
}

func firstUsableGitHubTokenEnv(names ...string) string {
	for _, name := range names {
		if value := commit.FirstUsableGitHubToken(os.Getenv(name)); value != "" {
			return value
		}
	}
	return ""
}

func runAdminAlertsDeliverConfig(ctx context.Context, cfg adminAlertsDeliverConfig, stdout, stderr io.Writer) error {
	summary, runErr := runAdminAlertsDeliver(ctx, cfg, stdout, stderr)
	writeAdminAlertDeliveryWarnings(stderr, summary)
	if runErr != nil && adminAlertDeliverySummaryEmpty(summary) {
		return runErr
	}
	if err := writeAdminAlertDeliverySummary(stdout, cfg.Format, summary); err != nil && runErr == nil {
		runErr = err
	}
	return runErr
}

func runAdminAlertsDeliverReal(
	ctx context.Context,
	cfg adminAlertsDeliverConfig,
	_ io.Writer,
	_ io.Writer,
) (service.AlertDeliverySummary, error) {
	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return service.AlertDeliverySummary{}, errors.New("connect database failed")
	}
	defer pool.Close()
	if err := pool.Ping(ctx); err != nil {
		return service.AlertDeliverySummary{}, errors.New("connect database failed")
	}

	store := db.NewStore(pool)
	client := &http.Client{Timeout: cfg.Timeout}
	var sender service.AlertDeliverySender
	switch cfg.Channel {
	case service.AlertDeliveryChannelSlack:
		sender = service.NewSlackAlertDeliverySender(client)
	case service.AlertDeliveryChannelGitHubCheck:
		sender = service.NewGitHubCheckAlertDeliverySender(client, cfg.GitHubToken, cfg.GitHubAPIURL)
	case service.AlertDeliveryChannelGitHubComment:
		sender = service.NewGitHubCommentAlertDeliverySender(client, cfg.GitHubToken, cfg.GitHubAPIURL)
	case service.AlertDeliveryChannelEmail:
		sender = service.NewEmailAlertDeliverySender(
			cfg.EmailSMTPAddr,
			cfg.EmailFrom,
			cfg.EmailUsername,
			cfg.EmailPassword,
		).WithTimeout(cfg.Timeout)
	default:
		sender = service.NewWebhookAlertDeliverySender(client)
	}
	return service.NewAlertDeliveryDispatcher(store, sender, nil).Deliver(ctx, service.AlertDeliveryOptions{
		Channel:    cfg.Channel,
		Target:     cfg.Target,
		Limit:      cfg.Limit,
		RetryAfter: cfg.RetryAfter,
	})
}

func writeAdminAlertDeliverySummary(stdout io.Writer, format string, summary service.AlertDeliverySummary) error {
	switch format {
	case "json":
		out, err := json.MarshalIndent(summary, "", "  ")
		if err != nil {
			return fmt.Errorf("encode output: %w", err)
		}
		fmt.Fprintln(stdout, string(out))
	default:
		fmt.Fprintf(stdout,
			"enqueued=%d attempted=%d delivered=%d failed=%d\n",
			summary.Enqueued,
			summary.Attempted,
			summary.Delivered,
			summary.Failed,
		)
	}
	return nil
}

func writeAdminAlertDeliveryWarnings(stderr io.Writer, summary service.AlertDeliverySummary) {
	for _, failure := range summary.Failures {
		fmt.Fprintf(
			stderr,
			"alert delivery warning: delivery_id=%s event_id=%s error=%s\n",
			failure.DeliveryID,
			failure.EventID,
			failure.Error,
		)
	}
}

func adminAlertDeliverySummaryEmpty(summary service.AlertDeliverySummary) bool {
	return summary.Enqueued == 0 &&
		summary.Attempted == 0 &&
		summary.Delivered == 0 &&
		summary.Failed == 0 &&
		len(summary.Failures) == 0
}

func newAdminAlertsEvaluateCommand(
	stdout, stderr io.Writer,
	run func(context.Context, adminAlertsEvaluateConfig, io.Writer, io.Writer) error,
) *cobra.Command {
	cfg := adminAlertsEvaluateConfig{Format: "text"}
	cmd := configureCommand(&cobra.Command{
		Use:   "evaluate",
		Short: "Evaluate server-side alert rules.",
		Args: func(cmd *cobra.Command, args []string) error {
			switch {
			case len(args) > 0:
				return commandUsageError(cmd, "unexpected argument %q", args[0])
			case cfg.Format != "text" && cfg.Format != "json":
				return commandUsageError(cmd, "--format must be text or json")
			}
			cfg.DatabaseURL = os.Getenv("CONBENCH_DB_URL")
			if cfg.DatabaseURL == "" {
				return errors.New("CONBENCH_DB_URL is required")
			}
			cfg.PublicBaseURL = os.Getenv("CONBENCH_INTENDED_BASE_URL")
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout, stderr)
		},
	})
	cmd.Flags().StringVar(&cfg.Format, "format", cfg.Format, "output format: text or json")
	return cmd
}

func runAdminAlertsEvaluateConfig(ctx context.Context, cfg adminAlertsEvaluateConfig, stdout, stderr io.Writer) error {
	summary, runErr := runAdminAlertsEvaluate(ctx, cfg, stdout, stderr)
	writeAdminAlertsWarnings(stderr, summary)
	if runErr != nil && adminAlertsSummaryEmpty(summary) {
		return runErr
	}
	if err := writeAdminAlertsSummary(stdout, cfg.Format, summary); err != nil && runErr == nil {
		runErr = err
	}
	return runErr
}

func runAdminAlertsEvaluateReal(
	ctx context.Context,
	cfg adminAlertsEvaluateConfig,
	_ io.Writer,
	_ io.Writer,
) (service.AlertEvaluationSummary, error) {
	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return service.AlertEvaluationSummary{}, errors.New("connect database failed")
	}
	defer pool.Close()
	if err := pool.Ping(ctx); err != nil {
		return service.AlertEvaluationSummary{}, errors.New("connect database failed")
	}

	store := db.NewStore(pool)
	reporter := service.NewCIReporter(store, cfg.PublicBaseURL)
	return service.NewAlertEvaluator(store, reporter, nil).Evaluate(ctx, service.AlertEvaluationOptions{})
}

func writeAdminAlertsSummary(stdout io.Writer, format string, summary service.AlertEvaluationSummary) error {
	switch format {
	case "json":
		out, err := json.MarshalIndent(adminAlertsSummaryOutputOf(summary), "", "  ")
		if err != nil {
			return fmt.Errorf("encode output: %w", err)
		}
		fmt.Fprintln(stdout, string(out))
	default:
		fmt.Fprintf(stdout,
			"rules=%d evaluated=%d opened=%d resolved=%d unchanged=%d skipped=%d no_candidate=%d failed=%d\n",
			summary.Rules,
			summary.Evaluated,
			summary.Opened,
			summary.Resolved,
			summary.Unchanged,
			summary.Skipped,
			summary.NoCandidate,
			summary.Failed,
		)
	}
	return nil
}

type adminAlertsSummaryOutput struct {
	Rules       int                        `json:"rules"`
	Evaluated   int                        `json:"evaluated"`
	Opened      int                        `json:"opened"`
	Resolved    int                        `json:"resolved"`
	Unchanged   int                        `json:"unchanged"`
	Skipped     int                        `json:"skipped"`
	NoCandidate int                        `json:"no_candidate"`
	Failed      int                        `json:"failed"`
	Failures    []service.AlertRuleFailure `json:"failures,omitempty"`
	Events      []adminAlertEventOutput    `json:"events,omitempty"`
}

type adminAlertEventOutput struct {
	ID           string          `json:"id"`
	RuleID       string          `json:"rule_id"`
	Kind         string          `json:"kind"`
	Status       string          `json:"status"`
	StatusReason string          `json:"status_reason"`
	RunID        *string         `json:"run_id,omitempty"`
	CommitSHA    *string         `json:"commit_sha,omitempty"`
	Repository   string          `json:"repository"`
	ReportURL    string          `json:"report_url"`
	Summary      json.RawMessage `json:"summary"`
	CreatedAt    time.Time       `json:"created_at"`
}

func adminAlertsSummaryOutputOf(summary service.AlertEvaluationSummary) adminAlertsSummaryOutput {
	out := adminAlertsSummaryOutput{
		Rules:       summary.Rules,
		Evaluated:   summary.Evaluated,
		Opened:      summary.Opened,
		Resolved:    summary.Resolved,
		Unchanged:   summary.Unchanged,
		Skipped:     summary.Skipped,
		NoCandidate: summary.NoCandidate,
		Failed:      summary.Failed,
		Failures:    summary.Failures,
	}
	if len(summary.Events) > 0 {
		out.Events = make([]adminAlertEventOutput, 0, len(summary.Events))
		for _, event := range summary.Events {
			out.Events = append(out.Events, adminAlertEventOutput{
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
			})
		}
	}
	return out
}

func rawJSONOrNull(b []byte) json.RawMessage {
	if len(b) == 0 {
		return json.RawMessage("null")
	}
	return json.RawMessage(b)
}

func writeAdminAlertsWarnings(stderr io.Writer, summary service.AlertEvaluationSummary) {
	for _, failure := range summary.Failures {
		fmt.Fprintf(stderr, "alert evaluation warning: rule_id=%s error=%s\n", failure.RuleID, failure.Error)
	}
}

func adminAlertsSummaryEmpty(summary service.AlertEvaluationSummary) bool {
	return summary.Rules == 0 &&
		summary.Evaluated == 0 &&
		summary.Opened == 0 &&
		summary.Resolved == 0 &&
		summary.Unchanged == 0 &&
		summary.Skipped == 0 &&
		summary.NoCandidate == 0 &&
		summary.Failed == 0 &&
		len(summary.Failures) == 0 &&
		len(summary.Events) == 0
}

func adminRepairCommand(stdout, stderr io.Writer) *cobra.Command {
	return newAdminRepairCommand(stdout, stderr, runAdminRepairConfig)
}

func newAdminRepairCommand(
	stdout, stderr io.Writer,
	run func(context.Context, adminRepairConfig, io.Writer, io.Writer) error,
) *cobra.Command {
	cfg := adminRepairConfig{
		Limit:           defaultAdminRepairLimit,
		BackfillTimeout: defaultAdminRepairBackfillTimeout,
		GitHubTimeout:   defaultAdminRepairGitHubTimeout,
		Format:          "text",
	}
	var repository string
	var cursorRaw string
	cmd := configureCommand(&cobra.Command{
		Use:   "repair-commits",
		Short: "Repair stored unknown commit rows.",
		Args: func(cmd *cobra.Command, args []string) error {
			switch {
			case len(args) > 0:
				return commandUsageError(cmd, "unexpected argument %q", args[0])
			case cfg.Limit <= 0:
				return commandUsageError(cmd, "--limit must be greater than 0")
			case cfg.BackfillTimeout <= 0:
				return commandUsageError(cmd, "--backfill-timeout must be greater than 0")
			case cfg.GitHubTimeout <= 0:
				return commandUsageError(cmd, "--github-timeout must be greater than 0")
			case cfg.Format != "text" && cfg.Format != "json":
				return commandUsageError(cmd, "--format must be text or json")
			}

			if repository != "" {
				normalized := commit.NormalizeRepoURL(repository)
				cfg.Repository = &normalized
			}
			if cursorRaw != "" {
				cursor, err := commitrepair.DecodeCursor(cursorRaw)
				if err != nil {
					return commandUsageError(cmd, "invalid --cursor: %s", err)
				}
				cfg.Cursor = &cursor
			}
			if cfg.Cursor != nil && cfg.Repository != nil && cfg.Cursor.Repository != *cfg.Repository {
				return commandUsageError(
					cmd,
					"cursor repository %q does not match repository filter %q",
					cfg.Cursor.Repository, *cfg.Repository,
				)
			}

			cfg.DatabaseURL = os.Getenv("CONBENCH_DB_URL")
			if cfg.DatabaseURL == "" {
				return errors.New("CONBENCH_DB_URL is required")
			}
			cfg.GitHubToken = os.Getenv("GITHUB_API_TOKEN")
			if cfg.GitHubToken == "" {
				return errors.New("GITHUB_API_TOKEN is required")
			}
			if !commit.HasUsableGitHubToken(cfg.GitHubToken) {
				return errors.New("GITHUB_API_TOKEN has no usable token")
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return run(cmd.Context(), cfg, stdout, stderr)
		},
	})
	cmd.Flags().StringVar(&repository, "repository", "", "repository URL")
	cmd.Flags().StringVar(&cursorRaw, "cursor", "", "repair cursor")
	cmd.Flags().IntVar(&cfg.Limit, "limit", cfg.Limit, "maximum rows to inspect")
	cmd.Flags().BoolVar(&cfg.DryRun, "dry-run", false, "report repairs without updating rows")
	cmd.Flags().BoolVar(&cfg.Backfill, "backfill", false, "enqueue default-branch ancestry backfill")
	cmd.Flags().DurationVar(&cfg.BackfillTimeout, "backfill-timeout", cfg.BackfillTimeout, "backfill drain timeout")
	cmd.Flags().DurationVar(&cfg.GitHubTimeout, "github-timeout", cfg.GitHubTimeout, "GitHub enrichment timeout")
	cmd.Flags().StringVar(&cfg.Format, "format", cfg.Format, "output format: text or json")
	return cmd
}

func runAdminRepairConfig(ctx context.Context, cfg adminRepairConfig, stdout, stderr io.Writer) error {
	summary, runErr := runAdminRepair(ctx, cfg, stdout, stderr)
	if runErr == nil {
		runErr = fatalAdminRepairSummaryError(summary)
	}
	writeAdminRepairWarnings(stderr, summary)
	if runErr != nil && adminRepairSummaryEmpty(summary) {
		return runErr
	}
	if err := writeAdminRepairSummary(stdout, cfg.Format, summary); err != nil && runErr == nil {
		runErr = err
	}
	return runErr
}

func runAdminRepairReal(ctx context.Context, cfg adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return commitrepair.Summary{}, errors.New("connect database failed")
	}
	defer pool.Close()
	if err := pool.Ping(ctx); err != nil {
		return commitrepair.Summary{}, errors.New("connect database failed")
	}

	store := db.NewStore(pool)
	client := newAdminGitHubClient(cfg.GitHubToken)
	provider := commit.NewGitHubProvider(client, cfg.GitHubTimeout, nil)

	var backfiller *commit.Backfiller
	if cfg.Backfill {
		backfiller = commit.NewBackfiller(client, store)
	}

	summary, err := commitrepair.NewRepairer(store, provider, backfiller).Run(ctx, commitrepair.Options{
		Repository: cfg.Repository,
		Limit:      cfg.Limit,
		Cursor:     cfg.Cursor,
		DryRun:     cfg.DryRun,
		Backfill:   cfg.Backfill,
	})
	if backfiller != nil {
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.BackfillTimeout)
		if backfiller.Shutdown(shutdownCtx) {
			summary.BackfillTimedOut = true
			if err == nil {
				err = errors.New("backfill shutdown timed out")
			}
		}
		cancel()
	}
	return summary, err
}

func fatalAdminRepairSummaryError(summary commitrepair.Summary) error {
	githubAttempts := summary.Scanned - summary.UnsupportedRepository
	if githubAttempts <= 0 || summary.Failed != githubAttempts || summary.AuthOrQuotaFailures != githubAttempts {
		return nil
	}
	return errors.New("GitHub authentication or quota failure")
}

func adminRepairSummaryEmpty(summary commitrepair.Summary) bool {
	return summary.Scanned == 0 &&
		summary.Repaired == 0 &&
		summary.WouldRepair == 0 &&
		summary.UnsupportedRepository == 0 &&
		summary.Failed == 0 &&
		summary.AuthOrQuotaFailures == 0 &&
		summary.AlreadyRepaired == 0 &&
		summary.BackfillEnqueued == 0 &&
		summary.WouldBackfill == 0 &&
		!summary.BackfillTimedOut &&
		summary.NextCursor == nil &&
		len(summary.Failures) == 0
}

func writeAdminRepairSummary(stdout io.Writer, format string, summary commitrepair.Summary) error {
	switch format {
	case "json":
		out, err := json.MarshalIndent(summary, "", "  ")
		if err != nil {
			return fmt.Errorf("encode output: %w", err)
		}
		fmt.Fprintln(stdout, string(out))
	default:
		fmt.Fprintf(stdout,
			"scanned=%d repaired=%d would_repair=%d unsupported_repository=%d failed=%d auth_or_quota_failures=%d already_repaired=%d backfill_enqueued=%d would_backfill=%d backfill_timed_out=%t",
			summary.Scanned,
			summary.Repaired,
			summary.WouldRepair,
			summary.UnsupportedRepository,
			summary.Failed,
			summary.AuthOrQuotaFailures,
			summary.AlreadyRepaired,
			summary.BackfillEnqueued,
			summary.WouldBackfill,
			summary.BackfillTimedOut,
		)
		if summary.NextCursor != nil {
			fmt.Fprintf(stdout, " next_cursor=%s", *summary.NextCursor)
		}
		fmt.Fprintln(stdout)
	}
	return nil
}

func writeAdminRepairWarnings(stderr io.Writer, summary commitrepair.Summary) {
	for _, failure := range summary.Failures {
		fmt.Fprintf(stderr, "commit repair warning: repository=%s sha=%s error=%s\n",
			failure.Repository, failure.Sha, failure.Error)
	}
}
