# syntax=docker/dockerfile:1
# ---- Stage 1: build codeanalyzer-go from its feature branch ------------------
# The Go analyzer is not yet merged/released (codeanalyzer-go#5); the image builds
# it from source so Go analysis works out of the box. Override the ref to pin a SHA.
FROM golang:1.25-bookworm AS gobuild
ARG CODEANALYZER_GO_REF=feat/initial-implementation
RUN git clone --depth 1 --branch "${CODEANALYZER_GO_REF}" \
      https://github.com/codellm-devkit/codeanalyzer-go /src \
 && cd /src && CGO_ENABLED=0 go build -o /out/codeanalyzer-go ./cmd/codeanalyzer

# ---- Stage 2: runtime ---------------------------------------------------------
FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/codellm-devkit/cocoa"
LABEL org.opencontainers.image.description="COCOA: precise static system graphs for AI agents"

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# helm + kubectl: optional static renderers for k8s wiring (binary-gated features)
ARG TARGETARCH=amd64
ARG HELM_VERSION=v3.16.4
ARG KUBECTL_VERSION=v1.31.4
RUN curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" \
      | tar -xz --strip-components=1 -C /usr/local/bin "linux-${TARGETARCH}/helm" \
 && curl -fsSL -o /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
 && chmod +x /usr/local/bin/kubectl

COPY --from=gobuild /out/codeanalyzer-go /usr/local/bin/codeanalyzer-go

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY cocoa ./cocoa
RUN pip install --no-cache-dir .

# python-sdk#236 workaround: the cldk 1.4.0 wheel ships WITHOUT its bundled
# codeanalyzer jar, so Java analysis fails on a clean install. Fetch the pinned
# release asset into the path cldk's _locate_jar() expects. Remove once a fixed
# cldk release lands.
RUN JAR_DIR="$(python -c 'import cldk.analysis.java.codeanalyzer as m, pathlib; print(pathlib.Path(m.__file__).parent / "jar")')" \
 && mkdir -p "${JAR_DIR}" \
 && curl -fsSL -o "${JAR_DIR}/codeanalyzer-2.4.1.jar" \
      "https://github.com/codellm-devkit/codeanalyzer-java/releases/download/v2.4.1/codeanalyzer-2.4.1.jar"

# NOTE: cldk downloads a Temurin JDK into each project's analysis cache on first
# Java use (network required once per analyzed project). Pre-baking is not possible
# until cldk honors a global JDK path — tracked upstream.

ENTRYPOINT ["cocoa"]
CMD ["--help"]
