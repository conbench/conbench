package prodclone

import (
	"fmt"
	"net"
	"net/url"
	"os"
	"strconv"
	"strings"
)

const (
	EnvDBURL           = "CONBENCH_PROD_CLONE_DB_URL"
	EnvConfirm         = "CONBENCH_PROD_CLONE_CONFIRM"
	EnvReadOnlyRole    = "CONBENCH_PROD_CLONE_READONLY_ROLE"
	EnvExpectedHosts   = "CONBENCH_PROD_CLONE_EXPECTED_HOSTS"
	EnvDevelopmentRole = "CONBENCH_PROD_CLONE_DEVELOPMENT_ROLE"
	ConfirmReadOnly    = "read-only"
)

const cloneApplicationName = "conbench-admin-prod-clone-compat"

type Config struct {
	RawDBURL        string
	Confirm         string
	ReadOnlyRole    string
	ExpectedHosts   []string
	DevelopmentRole string
}

func LoadConfig() (Config, error) {
	cfg := Config{
		RawDBURL:        os.Getenv(EnvDBURL),
		Confirm:         os.Getenv(EnvConfirm),
		ReadOnlyRole:    os.Getenv(EnvReadOnlyRole),
		ExpectedHosts:   splitEnvList(os.Getenv(EnvExpectedHosts)),
		DevelopmentRole: os.Getenv(EnvDevelopmentRole),
	}

	if _, err := parseDBURL(cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func SafeDBURL(cfg Config) (string, error) {
	parsed, err := parseDBURL(cfg)
	if err != nil {
		return "", err
	}

	query := url.Values{}
	query.Set("application_name", cloneApplicationName)
	query.Set("default_transaction_read_only", "on")
	query.Set("statement_timeout", "30s")
	query.Set("lock_timeout", "2s")
	query.Set("idle_in_transaction_session_timeout", "30s")
	var user *url.Userinfo
	if username := parsed.User.Username(); username != "" {
		user = url.User(username)
	}
	safe := url.URL{
		Scheme:   parsed.Scheme,
		User:     user,
		Host:     parsed.Host,
		Path:     parsed.Path,
		RawPath:  parsed.RawPath,
		RawQuery: query.Encode(),
	}

	return safe.String(), nil
}

func TargetPolicyFromConfig(cfg Config, allowDevRole bool) (TargetPolicy, error) {
	parsed, err := parseDBURL(cfg)
	if err != nil {
		return TargetPolicy{}, err
	}

	port := defaultTargetPort
	if parsed.Port() != "" {
		port, err = strconv.Atoi(parsed.Port())
		if err != nil {
			return TargetPolicy{}, fmt.Errorf("%s port must be numeric", EnvDBURL)
		}
	}
	hosts := append([]string(nil), cfg.ExpectedHosts...)
	if len(hosts) == 0 {
		hosts = []string{parsed.Hostname()}
	}
	developmentRole := cfg.DevelopmentRole
	if developmentRole == "" {
		developmentRole = defaultTargetDevelopmentRole
	}

	return TargetPolicy{
		ExpectedDatabase:     strings.TrimPrefix(parsed.Path, "/"),
		ExpectedHosts:        hosts,
		ExpectedPort:         port,
		DevelopmentRole:      developmentRole,
		ExpectedReadOnlyRole: cfg.ReadOnlyRole,
		RequireReadOnlyRole:  true,
		AllowDevRole:         allowDevRole,
	}, nil
}

func ServerEnv(base []string, cfg Config, addr string) ([]string, error) {
	if err := validateLoopbackAddr(addr); err != nil {
		return nil, err
	}

	safeDBURL, err := SafeDBURL(cfg)
	if err != nil {
		return nil, err
	}

	env := make([]string, 0, 3)
	var pathEntry string
	for _, entry := range base {
		name, _, ok := strings.Cut(entry, "=")
		if !ok {
			continue
		}
		if name == "PATH" {
			pathEntry = entry
		}
	}
	if pathEntry != "" {
		env = append(env, pathEntry)
	}

	env = append(env, "CONBENCH_DB_URL="+safeDBURL, "CONBENCH_ADDR="+addr)
	return env, nil
}

func parseDBURL(cfg Config) (*url.URL, error) {
	if cfg.RawDBURL == "" {
		return nil, fmt.Errorf("%s must be set", EnvDBURL)
	}
	if cfg.Confirm != ConfirmReadOnly {
		return nil, fmt.Errorf("%s must equal %q", EnvConfirm, ConfirmReadOnly)
	}

	parsed, err := url.Parse(cfg.RawDBURL)
	if err != nil {
		return nil, fmt.Errorf("%s must be a valid URL", EnvDBURL)
	}
	if parsed.Host == "" || parsed.Hostname() == "" {
		return nil, fmt.Errorf("%s must include a host", EnvDBURL)
	}
	if err := validateTargetDBURL(parsed); err != nil {
		return nil, err
	}

	copied := *parsed
	return &copied, nil
}

func validateTargetDBURL(parsed *url.URL) error {
	if parsed.Scheme != "postgres" && parsed.Scheme != "postgresql" {
		return fmt.Errorf("%s scheme must be postgres or postgresql", EnvDBURL)
	}
	if port := parsed.Port(); port != "" {
		portNumber, err := strconv.Atoi(port)
		if err != nil || portNumber < 1 || portNumber > 65535 {
			return fmt.Errorf("%s port must be a valid TCP port", EnvDBURL)
		}
	}
	if parsed.Path == "" || parsed.Path == "/" {
		return fmt.Errorf("%s must include a database name", EnvDBURL)
	}
	return nil
}

func splitEnvList(value string) []string {
	parts := strings.FieldsFunc(value, func(r rune) bool { return r == ',' })
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

func validateLoopbackAddr(addr string) error {
	host, port, err := net.SplitHostPort(addr)
	if err != nil {
		return fmt.Errorf("server address must be a loopback host: %w", err)
	}
	if host == "" || port == "" {
		return fmt.Errorf("server address must be a loopback host")
	}
	portNumber, err := strconv.Atoi(port)
	if err != nil || portNumber < 1 || portNumber > 65535 {
		return fmt.Errorf("server address must use a numeric loopback port")
	}
	if strings.EqualFold(host, "localhost") {
		return nil
	}
	ip := net.ParseIP(host)
	if ip != nil && ip.IsLoopback() {
		return nil
	}
	return fmt.Errorf("server address must be a loopback host")
}
