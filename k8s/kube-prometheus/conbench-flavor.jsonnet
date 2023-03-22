// Note(JP): Starting point was a raw copy of
// https://github.com/prometheus-operator/kube-prometheus/blob/v0.12.0/example.jsonnet
// I then tried to understand some of
// https://github.com/prometheus-operator/kube-prometheus/tree/main/docs/customizations
// to do some modifications (mainly: inject custom dashboard)
// I use use auto-format in VSCode with the 'jsonnet Formatter' extension
local kp =
  (import 'kube-prometheus/main.libsonnet') +
  // Uncomment the following imports to enable its patches
  // (import 'kube-prometheus/addons/anti-affinity.libsonnet') +
  // (import 'kube-prometheus/addons/managed-cluster.libsonnet') +
  (import 'kube-prometheus/addons/node-ports.libsonnet') +
  // (import 'kube-prometheus/addons/static-etcd.libsonnet') +
  // (import 'kube-prometheus/addons/custom-metrics.libsonnet') +
  // (import 'kube-prometheus/addons/external-metrics.libsonnet') +
  // (import 'kube-prometheus/addons/pyrra.libsonnet') +
  // (import "kube-prom-no-req-no-lim.jsonnet") +  // auto-uncommented-by-ci
  {
    values+:: {
      prometheus+: {
        externalLabels: {
          cluster: 'PROM_REMOTE_WRITE_CLUSTER_LABEL_VALUE',
        },
      },
      common+: {
        namespace: 'monitoring',
      },
      grafana+: {
        rawDashboards+:: {
          // This expects the file `conbench-grafana-dashboard.json` to be
          // present in the current working directory when running
          // `bash build.sh conbench-flavor.jsonnet`
          'conbench-grafana-dashboard.json': (importstr 'conbench-grafana-dashboard.json'),
        },
        config: {
          // http://docs.grafana.org/installation/configuration/
          sections: {
            // "auth.anonymous": { enabled: true },  // auto-uncommented-by-ci
            // Configure Grafana to be available under sub path instead of
            // root.
            server: {
              domain: 'conbench.local',
              serve_from_sub_path: true,
              // root_url: 'http://conbench.local/grafana/',
              root_url: '%(protocol)s://%(domain)s:%(http_port)s/grafana/',
            },
          },
        },
      },
    },
    prometheus+: {
      prometheus+: {
        spec+: {
          // Required for de-duplicating (and preventing double billing) on
          // the receivind end (Grafana Cloud) when sending from more than one
          // Prometheus replica.
          replicaExternalLabelName: '__replica__',
          remoteWrite: [{
            // If left as-is then Prometheus starts and periodically shows
            // a log line saying that this is an invalid URL. That's fine!
            // That is: replace this, if you want the k8s cluster to send
            // metrics to an external system. Leave this as-is when this
            // capabily is not needed.
            url: 'PROM_REMOTE_WRITE_ENDPOINT_URL',
            basicAuth: {
              username: {
                name: 'kubepromsecret',
                key: 'username',
              },
              password: {
                name: 'kubepromsecret',
                key: 'password',
              },
            },
            // Build up allowlist for the metrics to send. This is important
            // to control cost: active series count is what mainly influences the
            // cost storing metrics in e.g. Grafana Cloud.
            // Reference docs for the mechanism used here:
            // https://prometheus.io/docs/prometheus/latest/configuration/configuration/#relabel_config
            // https://github.com/prometheus-operator/prometheus-operator/blob/c237d26b62ee5e29087e01f173e94886ada5b2ec/Documentation/api.md#relabelconfig
            // Note: maybe it's easiest to allowlist by specific label
            // key/value pairs? For example, we know that kube-prometheus
            // stack magic adds a `container=conbench` k/v pair to all
            // metrics it scraped from conbench webapp containers.
            writeRelabelConfigs: [
              {
                // The "keep" strategy is documented with
                // "Drop targets for which regex does not match the concatenated source_labels."
                action: 'keep',
                regex: 'flask_.*|conbench_.*',
                sourceLabels: [
                  // In the Prometheus ecosystem this is a special label name.
                  // The value of this label contains the name of the metric.
                  '__name__',
                ],
              },
            ],
          }],
        },
      },
    },
  };

{ 'setup/0namespace-namespace': kp.kubePrometheus.namespace } +
{
  ['setup/prometheus-operator-' + name]: kp.prometheusOperator[name]
  for name in std.filter((function(name) name != 'serviceMonitor' && name != 'prometheusRule'), std.objectFields(kp.prometheusOperator))
} +
// { 'setup/pyrra-slo-CustomResourceDefinition': kp.pyrra.crd } +
// serviceMonitor and prometheusRule are separated so that they can be created after the CRDs are ready
{ 'prometheus-operator-serviceMonitor': kp.prometheusOperator.serviceMonitor } +
{ 'prometheus-operator-prometheusRule': kp.prometheusOperator.prometheusRule } +
{ 'kube-prometheus-prometheusRule': kp.kubePrometheus.prometheusRule } +
{ ['alertmanager-' + name]: kp.alertmanager[name] for name in std.objectFields(kp.alertmanager) } +
{ ['blackbox-exporter-' + name]: kp.blackboxExporter[name] for name in std.objectFields(kp.blackboxExporter) } +
{ ['grafana-' + name]: kp.grafana[name] for name in std.objectFields(kp.grafana) } +
// { ['pyrra-' + name]: kp.pyrra[name] for name in std.objectFields(kp.pyrra) if name != 'crd' } +
{ ['kube-state-metrics-' + name]: kp.kubeStateMetrics[name] for name in std.objectFields(kp.kubeStateMetrics) } +
{ ['kubernetes-' + name]: kp.kubernetesControlPlane[name] for name in std.objectFields(kp.kubernetesControlPlane) }
{ ['node-exporter-' + name]: kp.nodeExporter[name] for name in std.objectFields(kp.nodeExporter) } +
{ ['prometheus-' + name]: kp.prometheus[name] for name in std.objectFields(kp.prometheus) } +
{ ['prometheus-adapter-' + name]: kp.prometheusAdapter[name] for name in std.objectFields(kp.prometheusAdapter) }
