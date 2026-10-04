# Kubernetes Observability Demo

Воспроизводимое развертывание демонстрационного веб-приложения в Kubernetes с использованием Gateway API, Prometheus и Fluentd.

## Компоненты

- Kubernetes
- Envoy Gateway
- Nginx
- Prometheus
- Fluentd
- Python smoke tests

## Архитектура

```text
Client
  |
  v
Gateway API
  |
  v
Nginx Service
  |
  v
Nginx Pods

Prometheus ---> application metrics
Fluentd    ---> application access/error logs
```

## Среды

Основная поддерживаемая среда:

- Ubuntu 24.04
- kubeadm
- containerd

Среда разработки:

- Docker Desktop Kubernetes

## Статус

Проект находится в разработке.
