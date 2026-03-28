FROM freeradius/freeradius-server:latest-3.2

# PostgreSQL ve REST modulleri icin gerekli paketleri yukle
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        freeradius-postgresql \
        freeradius-rest \
    && rm -rf /var/lib/apt/lists/*

# FreeRADIUS config dizinini bul ve symlink olustur
# Image'a gore /etc/freeradius/3.0/ veya /etc/raddb/ olabilir
RUN RADDB=$(find /etc -type d -name "mods-enabled" 2>/dev/null | head -1 | sed 's|/mods-enabled||') && \
    echo "FreeRADIUS config dir: $RADDB" && \
    ln -sf $RADDB/mods-available/sql $RADDB/mods-enabled/sql && \
    ln -sf $RADDB/mods-available/rest $RADDB/mods-enabled/rest

# Config dizinini tekrar bul ve kendi dosyalarimizi kopyala
# Once dizini ogren
RUN RADDB=$(find /etc -type d -name "mods-enabled" 2>/dev/null | head -1 | sed 's|/mods-enabled||') && \
    echo "$RADDB" > /tmp/raddb_path

# Kendi konfigurasyonlarimizi kopyala
COPY clients.conf /tmp/clients.conf
COPY mods-available/sql /tmp/sql
COPY mods-available/rest /tmp/rest
COPY sites-available/default /tmp/default

# Dosyalari dogru dizine tasi
RUN RADDB=$(cat /tmp/raddb_path) && \
    cp /tmp/clients.conf $RADDB/clients.conf && \
    cp /tmp/sql $RADDB/mods-available/sql && \
    cp /tmp/rest $RADDB/mods-available/rest && \
    cp /tmp/default $RADDB/sites-available/default && \
    chown -R freerad:freerad $RADDB/

EXPOSE 1812/udp 1813/udp

CMD ["freeradius", "-f"]
