FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

RUN apt-get update && apt-get install -y \
    hyperfine jq asciidoc asciidoctor source-highlight graphviz \
    gcc uuid-dev libncurses-dev flex clang bison openjdk-17-jdk parallel wget libedit-dev \
    cmake python3 python3-pip zlib1g-dev make ninja-build \
    build-essential git ca-certificates curl libzstd-dev pkg-config \
    lsb-release gnupg software-properties-common \
    libxml2-dev libffi-dev libssl-dev python3-setuptools libtool autoconf zip unzip lld \
    && rm -rf /var/lib/apt/lists/*

# Install Bazelisk (which will automatically download the right Bazel version)
RUN curl -L https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-amd64 -o /usr/local/bin/bazel \
    && chmod +x /usr/local/bin/bazel

WORKDIR /workspace

ENV USE_BAZEL_VERSION=1.x
ENV BAZELISK_CACHE=/tmp/bazelisk-cache

# Create a folder for the Bazel cache
RUN mkdir -p /tmp/bazelisk-cache

# Sanity check tools that were installed
RUN java -version && \
    python3 --version && \
    bazel version && \
    hyperfine --version && \
    jq --version

# Set default command for the Nativelink remote worker
CMD ["/bin/bash"]
