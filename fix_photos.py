"""Fix file extensions and clean up photos directory."""
from pathlib import Path
import json

photos = Path(__file__).resolve().parent / "new_project" / "assets" / "photos"

# Remove bad files
for f in list(photos.iterdir()):
    if "org&" in f.name or f.stat().st_size > 1_000_000:
        print(f"Remove: {f.name}")
        f.unlink()

# Rename .jpg files with correct names if needed
print("\nRemaining photos:")
for f in sorted(photos.iterdir()):
    print(f"  {f.stat().st_size:>10,}  {f.name}")

# Fix actors.json to match actual filenames
actors_path = Path(__file__).resolve().parent / "new_project" / "actors.json"
actors = json.loads(actors_path.read_text())
valid = []
for a in actors:
    then_file = photos / a["then_photo"].replace("org&", "jpg")
    now_file = photos / a["now_photo"].replace("org&", "jpg")
    # Check if .jpg version exists
    if not then_file.exists():
        then_file = photos / a["then_photo"]
    if not now_file.exists():
        now_file = photos / a["now_photo"]
    if then_file.exists() and now_file.exists():
        a["then_photo"] = then_file.name
        a["now_photo"] = now_file.name
        valid.append(a)
        print(f"  OK: {a['name']}")
    else:
        print(f"  SKIP: {a['name']} (missing files)")

actors_path.write_text(json.dumps(valid, indent=2, ensure_ascii=False))
print(f"\nFinal: {len(valid)} actors in actors.json")
