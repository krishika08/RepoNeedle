import os

def walk_dir(path, max_depth=3, current_depth=0):
    if current_depth > max_depth:
        return
    try:
        entries = os.listdir(path)
    except Exception as e:
        return
    for e in entries:
        full = os.path.join(path, e)
        if os.path.isdir(full):
            print("  " * current_depth + "[D] " + e)
            walk_dir(full, max_depth, current_depth + 1)
        else:
            if current_depth <= 2:
                print("  " * current_depth + "[F] " + e + f" ({os.path.getsize(full)} bytes)")

print("=== external/agent-retrieval-bench/data ===")
walk_dir('external/agent-retrieval-bench/data', 3)
