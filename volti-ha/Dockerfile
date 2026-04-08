ARG BUILD_FROM
FROM ${BUILD_FROM}

# Dipendenze di sistema per compilare dlib e face_recognition
RUN apk add --no-cache \
    cmake \
    make \
    g++ \
    openblas-dev \
    lapack-dev \
    jpeg-dev \
    zlib-dev \
    libffi-dev \
    python3-dev \
    py3-numpy \
    py3-pillow

# Dipendenze Python
RUN pip3 install --no-cache-dir --break-system-packages \
    flask==3.1.* \
    paho-mqtt==2.1.* \
    requests==2.32.* \
    scikit-learn==1.6.* \
    dlib==19.24.* \
    face_recognition==1.3.*

# Pulizia strumenti di compilazione per ridurre la dimensione finale
RUN apk del cmake make g++ python3-dev

# Copia l'intera struttura del rootfs nel container
COPY rootfs/ /

# Permessi di esecuzione
RUN chmod a+x /run.sh

# Crea directory dati
RUN mkdir -p /data/models /data/snapshots /data/config /data/cropped_faces

# Labels necessari
LABEL \
    io.hass.version="1.0.0" \
    io.hass.type="addon" \
    io.hass.arch="amd64|aarch64"

CMD [ "/run.sh" ]
