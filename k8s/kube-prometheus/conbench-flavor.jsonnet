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
  // Pretend to almost not need any resources. Of course this can be dangerous.
  // This is to make it easier to get going with testing in k8s environments
  // that have limited resource offers.
  (import 'kube-prom-no-req-no-lim.jsonnet') +
  {
    values+:: {
      prometheus+: {
        externalLabels: {
          cluster: 'PROM_REMOTE_WRITE_CLUSTER_LABEL_VALUE',
        },
        // Configure the namespaces that should be monitored; this is important
        // for automated privilege configuration. If a namespace not configured
        // here has a ServiceMonitor object then the scraper Prometheuses try
        // to act on it, but will fail with errors like
        // `User \"system:serviceaccount:monitoring:prometheus-k8s\" cannot list resource ...`
        // Also see https://github.com/prometheus-operator/kube-prometheus/blob/main/docs/monitoring-other-namespaces.md
        // Deployment will fail if this contains a namespace that does not exist
        // in the target environment.
        // Note(JP): once again, string templating in this file is certainly
        // not super cute. Set KUBE_PROM_ADDITIONAL_NAMESPACE_STRING, the way
        // it's written below it's not optional to replace that placeholder.
        // Minimally, replace it with e.g. "'default'" or "'default',
        // 'staging'". Also note that in Conbench's CI pipeline a Makefile
        // target is doing that replacement right before JSONNET build.
        namespaces: ['kube-system', 'monitoring', KUBE_PROM_ADDITIONAL_NAMESPACE_STRING],
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
        // The following data source config object is here "only" to set
        // isDefault: true. The other values are copy/pasted from the build
        // output. This is not ideal. Also see
        // https://github.com/prometheus-operator/kube-prometheus/issues/2131
        datasources: [{
          access: 'proxy',
          orgId: 1,
          editable: false,
          name: 'prometheus',
          type: 'prometheus',
          url: 'http://prometheus-k8s.monitoring.svc:9090',
          version: 1,
          isDefault: true,
        }],
        config: {
          // http://docs.grafana.org/installation/configuration/
          sections: {
            // "auth.anonymous": { enabled: true },  // auto-uncommented-by-ci
            // Configure Grafana to be available under sub path instead of
            // root.
            server: {
              // this was an attempt to get /grafana served locally via minikube stack
              // domain: 'conbench.local',
              // root_url: 'http://conbench.local/grafana/',
              // with the following setup 'cb-staging.xxx.run/grafana' works
              serve_from_sub_path: true,
              root_url: '%(protocol)s://%(domain)s:%(http_port)s/grafana/',
            },
          },
        },
      },
    },
    prometheus+: {
      prometheus+: {
        spec+: {
          // NOTE(JP): leave this outcommented for all environments until
          // we are ready to use the aws-ebs-csi-driver method (or comparable
          // on GCP, where persistent volumes are after all automatically
          // provisioned). Goal: do not use custom storage class anymore,
          // this was a fun exercise but is too brittle.
          // https://github.com/prometheus-operator/kube-prometheus/blob/117ce2f8b51621ccb480e8bdd712ae21e92b744e/examples/prometheus-pvc.jsonnet
          // vd-2 in mind. Almost ephemeral setup. But we want to retain
          // data across kube-prometheus updates. Use short retention and tiny
          // persistent volumes.
          // retention: '12d',
          // <comment-used-by-ci: pvc-start>
          // storage: {
          //   volumeClaimTemplate: {
          //     apiVersion: 'v1',
          //     kind: 'PersistentVolumeClaim',
          //     spec: {
          //       accessModes: ['ReadWriteOnce'],
          //       // 6 days vs 9Gi? I have no idea, but sounds roughly reasonable
          //       // given the not-too-big-data-rate we expect. But we have to
          //       // see, and measure: easy, there is a dashboard for that. Note:
          //       // think of this as an advanced buffer. This is an ephemeral
          //       // system that should write data out to a more long-term
          //       // storage-optimized system.
          //       resources: { requests: { storage: '9Gi' } },
          //       // storageClassName: 'gp2'. aws-ebs-csi-driver method was a bit
          //       // mad. EBS-backed "local storage" to on vd-2 nodes however
          //       // works. Manually exposed ext4-formatted partitions to k8s
          //       // with a rather beautiful setup using the Local Persistent
          //       // Volume CSI Driver, offering a storage class which is for
          //       // now called 'fundisk-elb-backed' because fun und such.
          //       storageClassName: 'fundisk-elb-backed',
          //     },
          //   },
          // },
          // <comment-used-by-ci: pvc-end>
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
              // these rules are processed in order:
              // https://github.com/prometheus/prometheus/issues/11120
              {
                // The "keep" strategy is documented with
                // "Drop targets for which regex does not match the
                //  concatenated source_labels."
                // Keep any metric that has 'conbench' in its name or that
                // has the container=conbench label set.
                // With more than one item in `sourceLabels` a string is built
                // from those values, separated with ';' and that is what the
                // regex is matched against.
                action: 'keep',
                regex: '.*conbench.*',
                sourceLabels: [
                  // Special label name, the name of the metric.
                  '__name__',
                  'container',
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
