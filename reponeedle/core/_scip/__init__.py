"""
Vendored Python bindings for the official SCIP Protobuf schema (see README.md in this directory).

Importing this package does not import Protobuf. ``scip_pb2`` requires the optional ``scip`` extra
(``protobuf>=5.29.0,<8``) and is imported lazily by ``reponeedle.core.scip_ingestion``.
"""

SCHEMA_REPOSITORY = "https://github.com/scip-code/scip"
SCHEMA_TAG = "v0.10.0"
SCHEMA_COMMIT = "1c2b6db7e560d5233c944f36e4ac1377cc6963fc"
SCHEMA_SHA256 = "b38021b65ef90cbbf6af9c829ff75192859ad9b5da05439ef154bea4ceb2bf03"
GENERATOR = "grpcio-tools 1.71.0 (libprotoc 29.0); gencode version 5.29.0"
