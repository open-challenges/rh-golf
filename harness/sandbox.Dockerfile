# The build sandbox: a plain Ubuntu with git (Lake checks the pinned revisions of the packages).
# scripts/verify.py runs it with no network, no capabilities and a read-only root; the toolchain and
# Mathlib come in as read-only mounts.
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
