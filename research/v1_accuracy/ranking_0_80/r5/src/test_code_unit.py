import sys
import os

r5_src = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(r5_src, "..", "..", "..", ".."))
sys.path.insert(0, root)
sys.path.insert(0, r5_src)

from code_unit import CodeUnitIndexer, CodeUnitType

def test_indexer():
    indexer = CodeUnitIndexer()
    # 1. Python test
    py_code = """
import os
from math import sqrt

class DatabaseEngine:
    \"\"\"Manages database connections.\"\"\"
    def __init__(self, dsn: str):
        self.dsn = dsn

    def connect(self):
        return open_connection(self.dsn)

def open_connection(dsn: str):
    return None
"""
    units = indexer.index_file("db/engine.py", py_code)
    unit_ids = [u.unit_id for u in units]
    print(f"Python units: {unit_ids}")
    assert "db/engine.py::[module]" in unit_ids
    assert "db/engine.py::DatabaseEngine" in unit_ids
    assert "db/engine.py::DatabaseEngine.connect" in unit_ids
    assert "db/engine.py::open_connection" in unit_ids

    # 2. Incremental update
    py_updated = "def new_function(): pass\n"
    units_updated = indexer.index_file("db/engine.py", py_updated)
    updated_ids = [u.unit_id for u in units_updated]
    print(f"Updated units: {updated_ids}")
    assert "db/engine.py::DatabaseEngine" not in updated_ids
    assert "db/engine.py::new_function" in updated_ids

    # 3. Rust test
    rs_code = """
pub struct Parser {
    flags: u32,
}

impl Parser {
    pub fn parse_input(&self, input: &str) -> bool {
        true
    }
}
"""
    rs_units = indexer.index_file("src/parser.rs", rs_code)
    rs_ids = [u.unit_id for u in rs_units]
    print(f"Rust units: {rs_ids}")
    assert "src/parser.rs::[module]" in rs_ids
    assert "src/parser.rs::Parser" in rs_ids
    assert "src/parser.rs::parse_input" in rs_ids

    # 4. Fallback lexical chunker
    txt_code = "\n".join([f"line {i}" for i in range(100)])
    txt_units = indexer.index_file("data/config.txt", txt_code)
    print(f"Lexical units count: {len(txt_units)}")
    assert len(txt_units) > 1

    print("ALL CODE UNIT TESTS PASSED!")

if __name__ == "__main__":
    test_indexer()

