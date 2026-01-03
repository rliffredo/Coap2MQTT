docker build -t coap2mqtt:latest .
docker tag coap2mqtt:latest ghcr.io/rliffredo/coap2mqtt:latest
docker push ghcr.io/rliffredo/coap2mqtt:latest