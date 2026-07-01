"""Object storage (MinIO / S3) for generated media artifacts.

Local outputs/ stays the pipeline's working directory; finished artifacts are
published here and served from here. See plans/07-minio-object-store.md.
"""

from . import object_store  # noqa: F401
