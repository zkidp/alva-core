# E3 formal-run isolation container (final image).
#
# Builds the alva binary from the FROZEN source commit and packages it with
# the isolation entrypoint. The image digest is NOT invented here: it must
# be produced by `docker build` on a Docker-capable host and frozen after
# push (see BUILD-AND-FREEZE.md).
#
# The build stage uses rockylinux:8 (glibc 2.28) so the produced binary runs
# on older-glibc hosts (Alibaba Alinux 8, glibc 2.28) as well as inside any
# newer container (Debian bookworm = glibc 2.36). Building on bookworm
# produced a glibc-2.36 binary that the Alinux host could not execute.

FROM rockylinux:8 AS build
RUN dnf install -y gcc ca-certificates curl \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
       | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"
WORKDIR /src
COPY alva/Cargo.toml ./alva/Cargo.toml
COPY alva/src ./alva/src
WORKDIR /src/alva
RUN cargo build --release --bin alva

FROM debian:bookworm-slim
# No apt step: the CA bundle is copied from the build stage so image
# assembly does not depend on external package mirrors (Alibaba/China hosts
# observed very slow deb.debian.org access during the first build attempt).
COPY --from=build /etc/ssl/certs/ca-certificates.crt \
    /etc/ssl/certs/ca-certificates.crt
COPY --from=build /src/alva/target/release/alva /usr/local/bin/alva
COPY tests/e3/runner/container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
