# MongoDB Community Edition 8.x for Home Assistant
FROM mongo:8

# Install jq and bash for Home Assistant integration
RUN apt-get update && apt-get install -y \
    jq \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /data/db

# MongoDB data will be stored in /data which is mapped to the add-on's data directory
# This ensures data is included in Home Assistant backups
VOLUME /data

# Expose MongoDB port
EXPOSE 27017

# Copy custom run script
COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
