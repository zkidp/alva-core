#!/usr/bin/env sh
set -eu

repository="${ALVA_REPOSITORY:-zkidp/alva-core}"
version="${ALVA_VERSION:-v0.14.1-preview.2}"
install_dir="${ALVA_INSTALL_DIR:-$HOME/.local/bin}"

case "$(uname -s)" in
  Linux) platform="linux-x86_64" ;;
  Darwin) platform="macos-aarch64" ;;
  *) echo "unsupported operating system: $(uname -s)" >&2; exit 1 ;;
esac

case "$(uname -m)" in
  x86_64|amd64)
    [ "$platform" = "linux-x86_64" ] || {
      echo "this preview provides macOS Apple Silicon only" >&2
      exit 1
    }
    ;;
  arm64|aarch64)
    [ "$platform" = "macos-aarch64" ] || {
      echo "this preview provides Linux x86_64 only" >&2
      exit 1
    }
    ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

command -v curl >/dev/null 2>&1 || {
  echo "curl is required" >&2
  exit 1
}

asset="alva-${version}-${platform}.tar.gz"
base_url="${ALVA_RELEASE_BASE_URL:-https://github.com/${repository}/releases/download/${version}}"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT INT TERM

curl -fsSL "${base_url}/${asset}" -o "${temporary}/${asset}"
curl -fsSL "${base_url}/SHA256SUMS.txt" -o "${temporary}/SHA256SUMS.txt"

expected="$(awk -v asset="$asset" '$2 == "./" asset || $2 == asset { print $1 }' "${temporary}/SHA256SUMS.txt")"
[ -n "$expected" ] || {
  echo "checksum entry not found for ${asset}" >&2
  exit 1
}

if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "${temporary}/${asset}" | awk '{print $1}')"
else
  actual="$(shasum -a 256 "${temporary}/${asset}" | awk '{print $1}')"
fi
[ "$actual" = "$expected" ] || {
  echo "checksum verification failed for ${asset}" >&2
  exit 1
}

tar -xzf "${temporary}/${asset}" -C "$temporary"
mkdir -p "$install_dir"
cp "${temporary}/alva-${version}-${platform}/alva" "$install_dir/alva"
chmod 755 "$install_dir/alva"

echo "installed alva ${version} to ${install_dir}/alva"
case ":$PATH:" in
  *":${install_dir}:"*) ;;
  *) echo "add ${install_dir} to PATH to run alva from a new shell" ;;
esac
