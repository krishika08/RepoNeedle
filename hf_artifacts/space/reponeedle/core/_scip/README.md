# Vendored SCIP schema and generated Python bindings

| File | Origin |
| :--- | :--- |
| `scip.proto` | Unmodified copy of `scip.proto` from <https://github.com/scip-code/scip>, tag **v0.10.0**, commit `1c2b6db7e560d5233c944f36e4ac1377cc6963fc` (identical to `main` at `be1d9f7`, 2026-11-10). SHA-256 `b38021b65ef90cbbf6af9c829ff75192859ad9b5da05439ef154bea4ceb2bf03`. |
| `scip_pb2.py`, `scip_pb2.pyi` | Generated from that file; not edited. |
| `LICENSE` | The SCIP project's license (Apache License 2.0), which covers `scip.proto` and the code generated from it. |

The SCIP project publishes no Python bindings, and RepoNeedle must not need `protoc` at runtime. The generated code is therefore checked in, which is a deliberate exception to Protobuf's general "do not check in gencode" advice.

The generated code is stamped **gencode 5.29.0**. That version determines the supported runtime range, `protobuf>=5.29.0,<8`:
- Runtime 5.29.x requires the same major version and a runtime no older than the gencode.
- Runtimes 6.x and 7.x require only a runtime no older than the gencode.
- These runtimes were verified on Python 3.11 and 3.12 (both the upb and the pure-Python backends): 5.29.0, 5.29.5, 6.33.6 and 7.36.2.
- Runtime 5.28.3 is rejected by Protobuf's own version check.

## Regenerating

```bash
python -m venv gen && gen/bin/pip install grpcio-tools==1.71.0   # bundles libprotoc 29.0
curl -L -o scip.proto https://raw.githubusercontent.com/scip-code/scip/1c2b6db7e560d5233c944f36e4ac1377cc6963fc/scip.proto
gen/bin/python -m grpc_tools.protoc --proto_path=. --python_out=. --pyi_out=. scip.proto
```

`tests/test_scip_parsing.py` checks that the vendored `scip.proto` has the SHA-256 above, and that the generated module was built from it.
