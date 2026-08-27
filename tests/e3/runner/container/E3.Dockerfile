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
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/alva/target/release/alva /usr/local/bin/alva
COPY tests/e3/runner/container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
