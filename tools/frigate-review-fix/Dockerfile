FROM ghcr.io/blakeblackshear/frigate:0.18.3@sha256:52ee4a7b4aa403347c1f31974d4faafc7157f97933c08c905c08ec6599f4f27a
COPY patch_review.py /tmp/pet-feeder-patch-review.py
RUN python3 /tmp/pet-feeder-patch-review.py /opt/frigate/frigate/review/maintainer.py
