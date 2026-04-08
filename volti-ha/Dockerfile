ARG BUILD_FROM
FROM ${BUILD_FROM}

# ========================================
# Dipendenze di sistema (Debian Bookworm)
# ========================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    python3-numpy \
    python3-pil \
    cmake \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libpng-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# ========================================
# Dipendenze Python
# ========================================
RUN pip3 install --no-cache-dir --break-system-packages \
    flask==3.1.* \
    paho-mqtt==2.1.* \
    requests==2.32.* \
    scikit-learn==1.6.* \
    dlib \
    face_recognition

# Pulizia strumenti di compilazione
RUN apt-get update && apt-get remove -y \
    cmake \
    build-essential \
    python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# ========================================
# Applicazione
# ========================================
COPY rootfs/ /

RUN chmod a+x /run.sh

RUN mkdir -p /data/models /data/snapshots /data/config /data/cropped_faces

LABEL \
    io.hass.version="1.0.0" \
    io.hass.type="addon" \
    io.hass.arch="amd64|aarch64"

CMD [ "/run.sh" ]
