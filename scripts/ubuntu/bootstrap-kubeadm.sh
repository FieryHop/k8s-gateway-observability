#!/usr/bin/env bash
set -euo pipefail

K8S_MINOR="${K8S_MINOR:-v1.34}"
CALICO_VERSION="${CALICO_VERSION:-v3.30.3}"
LOCAL_PATH_VERSION="${LOCAL_PATH_VERSION:-v0.0.31}"
METALLB_VERSION="${METALLB_VERSION:-v0.14.9}"
POD_CIDR="${POD_CIDR:-192.168.0.0/16}"
LB_ADDRESS="${LB_ADDRESS:-$(hostname -I | awk '{print $1}')/32}"
KUBE_USER="${SUDO_USER:-root}"

log() { printf '\n==> %s\n' "$*"; }

require_environment() {
  . /etc/os-release
  [[ "${ID}" == "ubuntu" && "${VERSION_ID}" == "24.04" ]] \
    || { echo "Ubuntu 24.04 is required" >&2; exit 1; }
  [[ ${EUID} -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
}

prepare_host() {
  log "Preparing host"
  swapoff -a
  sed -ri '/\sswap\s/ s/^([^#])/#\1/' /etc/fstab
  printf 'overlay\nbr_netfilter\n' >/etc/modules-load.d/k8s.conf
  modprobe overlay
  modprobe br_netfilter
  cat >/etc/sysctl.d/99-k8s.conf <<'EOF'
net.bridge.bridge-nf-call-iptables=1
net.bridge.bridge-nf-call-ip6tables=1
net.ipv4.ip_forward=1
EOF
  sysctl --system >/dev/null
}

install_containerd() {
  log "Installing containerd"
  if ! command -v containerd >/dev/null; then
    apt-get update -qq
    apt-get install -y -qq containerd
  fi
  mkdir -p /etc/containerd
  containerd config default >/etc/containerd/config.toml
  sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
  systemctl enable containerd
  systemctl restart containerd
}

install_kubernetes_packages() {
  log "Installing kubeadm, kubelet, kubectl ${K8S_MINOR}"
  apt-get install -y -qq apt-transport-https ca-certificates curl gpg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/Release.key" \
    | gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
  echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/ /" \
    >/etc/apt/sources.list.d/kubernetes.list
  apt-get update -qq
  apt-get install -y -qq kubelet kubeadm kubectl
  apt-mark hold kubelet kubeadm kubectl
  systemctl enable kubelet
}

init_cluster() {
  log "Initializing control plane"
  if [[ ! -f /etc/kubernetes/admin.conf ]]; then
    kubeadm init --pod-network-cidr="${POD_CIDR}"
  fi
  local home
  home="$(getent passwd "${KUBE_USER}" | cut -d: -f6)"
  install -d -o "${KUBE_USER}" -g "${KUBE_USER}" "${home}/.kube"
  install -m 600 -o "${KUBE_USER}" -g "${KUBE_USER}" /etc/kubernetes/admin.conf "${home}/.kube/config"
  export KUBECONFIG=/etc/kubernetes/admin.conf
  kubectl taint nodes --all node-role.kubernetes.io/control-plane- 2>/dev/null || true
}

install_addons() {
  export KUBECONFIG=/etc/kubernetes/admin.conf
  log "Installing Calico ${CALICO_VERSION}"
  kubectl apply --server-side -f "https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VERSION}/manifests/calico.yaml"
  kubectl wait --for=condition=Ready node --all --timeout=300s

  log "Installing local-path-provisioner ${LOCAL_PATH_VERSION}"
  kubectl apply -f "https://raw.githubusercontent.com/rancher/local-path-provisioner/${LOCAL_PATH_VERSION}/deploy/local-path-storage.yaml"
  kubectl patch storageclass local-path \
    -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

  log "Installing MetalLB ${METALLB_VERSION} (${LB_ADDRESS})"
  kubectl apply -f "https://raw.githubusercontent.com/metallb/metallb/${METALLB_VERSION}/config/manifests/metallb-native.yaml"
  kubectl -n metallb-system rollout status deployment/controller --timeout=300s
  kubectl apply -f - <<EOF
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default
  namespace: metallb-system
spec:
  addresses:
    - ${LB_ADDRESS}
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
spec:
  ipAddressPools:
    - default
EOF
}

install_helm() {
  command -v helm >/dev/null || snap install helm --classic
}

require_environment
prepare_host
install_containerd
install_kubernetes_packages
init_cluster
install_addons
install_helm
log "Cluster is ready. Next: python3 scripts/deploy.py && python3 scripts/verify.py"