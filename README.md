# Kubernetes Observability Demo

Воспроизводимый стенд: веб-приложение в Kubernetes, доступ через **Gateway API**, метрики в **Prometheus**, логи через **Fluentd** в Elasticsearch. Развёртывание и проверка автоматизированы Python-скриптами.

## Содержание

- [Состав и версии](#состав-и-версии)
- [Архитектура](#архитектура)
- [Требования](#требования)
- [Быстрый старт: Ubuntu 24.04 + kubeadm](#быстрый-старт-ubuntu-2404--kubeadm)
- [Быстрый старт: Docker Desktop](#быстрый-старт-docker-desktop)
- [Проверка работоспособности](#проверка-работоспособности)
- [Дополнительные возможности](#дополнительные-возможности)
- [Структура репозитория](#структура-репозитория)
- [Идемпотентность и удаление](#идемпотентность-и-удаление)
- [Безопасность](#безопасность)
- [Известные ограничения](#известные-ограничения)

## Состав и версии

Версии приложений и чартов зафиксированы в `cluster/versions.env`.
Версии компонентов кластера задаются переменными в `scripts/ubuntu/bootstrap-kubeadm.sh`.

| Компонент | Версия / образ | Назначение |
|---|---|---|
| Kubernetes | 1.34 (kubeadm, `v1.34.x`) | Кластер |
| Docker Desktop Kubernetes | 1.34.1 | Среда разработки |
| containerd | из репозитория Ubuntu 24.04 | Container runtime |
| Calico | v3.30.3 | CNI |
| local-path-provisioner | v0.0.31 | StorageClass по умолчанию |
| MetalLB | v0.14.9 | LoadBalancer для Gateway |
| Envoy Gateway | v1.9.2 | Реализация Gateway API |
| kube-prometheus-stack | 91.9.0 | Prometheus, Operator, Grafana, node-exporter |
| Nginx | `nginxinc/nginx-unprivileged:1.28-alpine-slim` | Демо-приложение |
| nginx-prometheus-exporter | 1.5.1 | Метрики Nginx |
| Fluentd | `fluent/fluentd-kubernetes-daemonset:v1.19.3-debian-elasticsearch8-1.1` | Сбор логов |
| Elasticsearch | 8.15.0 | Хранилище и поиск логов |
| Helm | 4.3.0 (проверено) | Установка чартов |
| Python | 3.11+ | Скрипты развёртывания и проверки |

Используемые ресурсы Gateway API: `GatewayClass`, `Gateway`, `HTTPRoute`.
Сторонние Python-зависимости не требуются: используется только стандартная библиотека.

## Архитектура

```text
                      ┌─────────────────────── Kubernetes ───────────────────────┐
                      │                                                          │
 Клиент ──HTTP:80──►  │  Envoy Gateway (GatewayClass → Gateway → HTTPRoute)      │
  (curl/Python)       │            │                                             │
                      │            ├── /, /split(80%) ──► Service demo-web ─► Nginx ×2 + exporter
                      │            └── /canary, /split(20%),                     │
                      │                X-Canary, canary.demo.local ─► demo-web-canary
                      │                                                          │
                      │  Prometheus ◄── ServiceMonitor ── nginx-exporter :9113   │
                      │      ▲      ◄── PodMonitor ────── Envoy proxy            │
                      │      └── Grafana (kube-prometheus-stack)                 │
                      │                                                          │
                      │  Fluentd (DaemonSet) ── /var/log/containers ──► Elasticsearch
                      └──────────────────────────────────────────────────────────┘
```

| Namespace | Содержимое |
|---|---|
| `platform-demo` | Nginx, canary, Service, PDB, Gateway, HTTPRoute |
| `envoy-gateway-system` | Контроллер Envoy Gateway, Envoy proxy, PodMonitor |
| `monitoring` | Prometheus, Grafana, Operator, exporters |
| `logging` | Fluentd, Elasticsearch, setup Job |
| `metallb-system` | MetalLB (только на kubeadm) |

Поток запроса: клиент → Service Envoy (LoadBalancer) → Envoy proxy → маршрут `HTTPRoute` → Service приложения → Pod Nginx.

## Требования

| Среда | Требования |
|---|---|
| Ubuntu 24.04 | Чистая VM, 2+ vCPU, 6+ ГБ RAM, 20+ ГБ диска, `sudo`, доступ в интернет |
| Docker Desktop | Включённый Kubernetes, `kubectl`, `helm`, Python 3.11+ |

Образы и манифесты загружаются из публичных источников. Платные и облачные сервисы не нужны.

## Быстрый старт: Ubuntu 24.04 + kubeadm

```bash
git clone <URL_РЕПОЗИТОРИЯ> k8s-observability-demo
cd k8s-observability-demo

sudo -E ./scripts/ubuntu/bootstrap-kubeadm.sh
python3 scripts/deploy.py
python3 scripts/verify.py
python3 scripts/verify_gateway.py --url http://<GATEWAY_IP>
```

Скрипт `bootstrap-kubeadm.sh` выполняет следующее:

1. Проверяет ОС (требуется Ubuntu 24.04) и права root.
2. Отключает swap и включает `overlay`, `br_netfilter` и sysctl.
3. Устанавливает containerd с `SystemdCgroup=true`.
4. Устанавливает `kubelet`, `kubeadm`, `kubectl` из `pkgs.k8s.io` и фиксирует их версии.
5. Выполняет `kubeadm init`, если кластер ещё не создан, и копирует kubeconfig пользователю.
6. Снимает taint с control-plane (кластер из одного узла).
7. Устанавливает Calico, local-path-provisioner и MetalLB с пулом из одного адреса узла.
8. Устанавливает Helm.

Переопределяемые переменные: `K8S_MINOR`, `CALICO_VERSION`, `LOCAL_PATH_VERSION`, `METALLB_VERSION`, `POD_CIDR`, `LB_ADDRESS`.

Адрес Gateway:

```bash
kubectl -n platform-demo get gateway demo-gateway \
  -o jsonpath='{.status.addresses.value}{"\n"}'
```

## Быстрый старт: Docker Desktop

1. Включите Kubernetes в Docker Desktop.
2. Установите `kubectl`, `helm` и Python 3.11+.
3. Выполните:

```powershell
python scripts/deploy.py --docker-desktop
python scripts/verify.py
```

Флаг `--docker-desktop` отключает монтирование корневой ФС для node-exporter.
Вместо `python` на Windows можно использовать `py -3.14`.
Эквиваленты через Make: `make deploy`, `make deploy-docker-desktop`, `make verify`, `make destroy`.

## Проверка работоспособности

### Автоматическая

```bash
python3 scripts/verify.py          # приложение, Prometheus, логи
python3 scripts/verify_gateway.py  # расширенная маршрутизация
```

`verify.py` временно открывает port-forward к Envoy Service на `127.0.0.1:18080`.
Ожидаемый итог:

```text
Summary:
  OK: application
  OK: prometheus
  OK: logging
```

### 1. Приложение через Gateway API

```bash
kubectl get gatewayclass envoy-gateway
kubectl -n platform-demo get gateway,httproute
kubectl -n platform-demo wait gateway/demo-gateway --for=condition=Programmed --timeout=180s

GATEWAY_IP=$(kubectl -n platform-demo get gateway demo-gateway -o jsonpath='{.status.addresses.value}')
curl -i http://${GATEWAY_IP}/
```

Ожидается `HTTP/1.1 200 OK` и тело `Hello World!`.
Без доступа к адресу Gateway (например, на Docker Desktop) используйте port-forward:

```bash
python3 scripts/check_app.py --url http://127.0.0.1:18080/
```

### 2. Мониторинг

Автоматически:

```bash
python3 scripts/check_prometheus.py
```

Скрипт выполняет четыре PromQL-запроса. Все значения должны быть больше нуля.

| Проверка | PromQL |
|---|---|
| Targets Nginx в состоянии up | `count(up{job="demo-web"} == 1)` |
| Nginx работает | `min(nginx_up)` |
| Запросы Nginx | `sum(nginx_http_requests_total)` |
| Envoy proxy жив | `sum(envoy_server_live)` |

Вручную:

```bash
kubectl -n monitoring port-forward --address 127.0.0.1 svc/kps-prometheus 9090:9090
```

Откройте `http://127.0.0.1:9090/targets` и найдите targets `demo-web` и `envoy-proxy`.
Примеры запросов в `http://127.0.0.1:9090/graph`:

```promql
nginx_up
rate(nginx_http_requests_total[1m])
nginx_connections_active
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="platform-demo"}[5m]))
sum by (pod) (container_memory_working_set_bytes{namespace="platform-demo"})
```

Grafana:

```bash
kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo
kubectl -n monitoring port-forward --address 127.0.0.1 svc/kps-grafana 3000:80
```

Логин `admin`, пароль генерируется при первом развёртывании и не хранится в репозитории.

### 3. Логирование

Автоматически:

```bash
python3 scripts/check_logging.py
```

Скрипт делает запрос с уникальным `?probe=<uuid>` через Gateway и ждёт запись с этим значением в Elasticsearch. Ожидаемый вывод: `OK: pod=... container=nginx status=200 uri=/?probe=...`.

Вручную:

```bash
curl http://${GATEWAY_IP}/?manual=check
kubectl -n logging port-forward --address 127.0.0.1 svc/elasticsearch 9200:9200

curl -s 'http://127.0.0.1:9200/demo-web-*/_search?q=uri:manual&pretty'
```

Собираются stdout и stderr контейнера `nginx` подов `demo-web-*`: JSON access-логи и error-логи.
Логи контейнера `nginx-exporter` исключены.
Индексы называются `demo-web-YYYY.MM.DD`. К записям добавляются поля `pod`, `namespace`, `container`.

## Дополнительные возможности

| Возможность | Реализация | Как проверить |
|---|---|---|
| Несколько backend | `demo-web` и `demo-web-canary` | `scripts/verify_gateway.py` |
| Маршрутизация по path | `/canary` → canary с `URLRewrite` | `curl http://${GATEWAY_IP}/canary` → `Hello from canary!` |
| Маршрутизация по header | `X-Canary: true` → canary | `curl -H 'X-Canary: true' http://${GATEWAY_IP}/` |
| Маршрутизация по hostname | `canary.demo.local` (`http-route-host.yaml`) | `curl -H 'Host: canary.demo.local' http://${GATEWAY_IP}/` |
| Traffic splitting | `/split` с весами 80/20 | `verify_gateway.py` проверяет долю canary в пределах 10–30% |
| Метрики Envoy | `PodMonitor` на Envoy proxy | Запрос `envoy_server_live` |
| Метрики Nginx | exporter + `ServiceMonitor` | Запрос `nginx_up` |
| Grafana и метрики кластера | kube-prometheus-stack | Dashboards в Grafana |
| Централизованный поиск логов | Fluentd → Elasticsearch | `check_logging.py` |
| Структурированные JSON-логи | `log_format json_combined` с `request_id` | Поля записи в Elasticsearch |
| Надёжность приложения | 2 реплики, RollingUpdate `maxUnavailable: 0`, probes, requests/limits, PDB | `kubectl -n platform-demo get deploy,pdb` |
| Безопасность Pod | non-root, `readOnlyRootFilesystem`, `drop ALL`, `seccomp RuntimeDefault`, без service account token | `kubectl -n platform-demo get deploy demo-web -o yaml` |
| CI | валидация манифестов, синтаксис Python, shellcheck, e2e на kubeadm | `.github/workflows/ci.yml` |
| Идемпотентный деплой | `helm upgrade --install`, `kubectl apply`, повторный запуск в CI | см. раздел ниже |

Проверка маршрутов:

```bash
curl http://${GATEWAY_IP}/split
for i in $(seq 1 20); do curl -s http://${GATEWAY_IP}/split; done | sort | uniq -c
```

## Структура репозитория

```text
.
├── .github/workflows/ci.yml        # CI: валидация и e2e на kubeadm
├── cluster/versions.env            # Версии компонентов
├── scripts/
│   ├── ubuntu/bootstrap-kubeadm.sh # Создание кластера на Ubuntu 24.04
│   ├── deploy.py                   # Полное развёртывание
│   ├── deploy_monitoring.py        # kube-prometheus-stack и Secret Grafana
│   ├── destroy.py                  # Удаление
│   ├── verify.py                   # Общая проверка
│   ├── verify_gateway.py           # Проверка маршрутов и traffic split
│   ├── check_app.py                # HTTP-проверка приложения
│   ├── check_prometheus.py         # PromQL-проверки
│   ├── check_logging.py            # Проверка записи в Elasticsearch
│   ├── check_prerequisites.py      # Проверка kubectl, helm, Python
│   └── k8s_utils.py                # Общие функции (port-forward)
├── kubernetes/base/                # Приложение, canary, Service, PDB
├── gateway/                        # GatewayClass, Gateway, HTTPRoute
├── monitoring/                     # values, ServiceMonitor, PodMonitor
├── logging/                        # Fluentd, Elasticsearch, setup Job
└── Makefile
```

## Идемпотентность и удаление

Порядок `deploy.py`: приложение → Envoy Gateway и Gateway API → kube-prometheus-stack → логирование.
Повторный запуск безопасен:

- Манифесты применяются через `kubectl apply -k`.
- Helm-релизы ставятся через `helm upgrade --install`.
- Secret Grafana создаётся только если его нет, существующий пароль сохраняется.
- Setup Job в `logging` пересоздаётся перед применением.

```bash
python3 scripts/deploy.py   # повторный запуск
python3 scripts/destroy.py  # удаление всех компонентов проекта
```

`destroy.py` удаляет ресурсы проекта и Helm-релизы, но не удаляет сам кластер. CRD Gateway API и Prometheus Operator, которые ставятся вместе с чартами, могут остаться в кластере.

## Безопасность

- Секреты в репозитории отсутствуют. Пароль Grafana генерируется через `secrets.token_urlsafe` при развёртывании и хранится только в Kubernetes Secret.
- Образы приложения запускаются без root и с минимальными привилегиями.
- Все версии образов и чартов зафиксированы.
- `.gitignore` исключает `.env`, kubeconfig, ключи и сертификаты.

## Известные ограничения

- Стенд одноузловой, без высокой доступности control plane.
- Elasticsearch работает в одном экземпляре, с отключённой безопасностью (`xpack.security.enabled=false`), без TLS и хранит данные в `emptyDir`. После перезапуска Pod логи теряются.
- Fluentd запускается от root (`FLUENT_UID=0`) для чтения логов узла. Буфер находится в памяти, при падении Pod часть записей может быть потеряна.
- Gateway слушает только HTTP на порту 80, TLS не настроен.
- Не настроены NetworkPolicy, Alertmanager и правила алертинга. Alertmanager отключён.
- Retention Prometheus — 24 часа, персистентное хранилище метрик не настроено.
- Метрики `etcd`, `kube-controller-manager`, `kube-scheduler`, `kube-proxy` отключены.
- Пул MetalLB состоит из одного IP-адреса узла, поэтому на узле должен быть свободен порт 80.
- Скрипты используют `kubectl port-forward` и локальные порты 18080, 19090 и 19200.
- Дашборды Grafana — стандартные из kube-prometheus-stack, собственных нет.