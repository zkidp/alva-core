# E3 formal-run isolation container (proposed final image).
#
# Builds the alva binary from the FROZEN source commit and packages it with
# the isolation entrypoint. The image digest is NOT invented here: it must
# be produced by `docker build` on a Docker-capable host and frozen after
# push (see BUILD-AND-FREEZE.md).

FROM rust:1-bookworm AS build
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
