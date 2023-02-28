// Takes inspiration from
// https://github.com/prometheus-operator/kube-prometheus/blob/c5360561fa3cb52297b652c263794ca474a0ab73/jsonnet/kube-prometheus/components/prometheus-operator.libsonnet
{
  values+:: {
    alertmanager+: {
      resources+: {
        limits: {},
        requests: { cpu: '1m', memory: '10Mi' },
      },
    },

    blackboxExporter+: {
      resources+: {
        limits: {},
        requests: { cpu: '1m', memory: '10Mi' },
      },
    },

    grafana+: {
      resources+: {
        limits: {},
        requests: { cpu: '1m', memory: '10Mi' },
      },
    },

    kubeStateMetrics+: {
      resources+: {
        limits: {},
      },
    },

    nodeExporter+: {
      resources+: {
        limits: {},
      },
    },

    prometheusAdapter+: {
      resources+: {
        limits: {},
      },
    },

    prometheusOperator+: {
      resources+: {
        limits: {},
      },
    },

    prometheus+: {
      resources+: {
        limits: {},
        requests: { cpu: '1m', memory: '10Mi' },
      },
    },
  },
}
