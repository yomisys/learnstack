r"""Import an MNAIR-style YAML curriculum into a LearnStack tenant.

MNAIR format: <root>/day{N}/{topic}_{lang}.yaml with keys
  id, day, topic, language, title, content, quiz[{question, options, correct}]

Each day becomes a module; each lesson becomes a text block + optional quiz block.
One curriculum is created per language found (use --language to restrict).

Usage (from backend/):
  python -m scripts.import_mnair_yaml --root C:\Users\yomis\mnair\curriculum \
      --tenant demo --slug-prefix mnair --title "Make Nigeria AI Ready" --language en
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

import yaml

from app.database import Base, SessionLocal, engine
from app.models import Curriculum, CurriculumStatus, Lesson, Module, Tenant

LANG_NAMES = {"en": "English", "pid": "Pidgin", "ha": "Hausa", "yo": "Yoruba", "ig": "Igbo"}


def load_lessons(root: Path, language: str | None):
    """Yield parsed lesson dicts grouped by (language, day)."""
    grouped: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for path in sorted(root.glob("day*/*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"  SKIP {path.name}: invalid YAML ({exc})")
            continue
        if not isinstance(doc, dict) or "title" not in doc:
            print(f"  SKIP {path.name}: not a lesson file")
            continue
        lang = doc.get("language", "en")
        if language and lang != language:
            continue
        day_match = re.search(r"day(\d+)", str(doc.get("day", path.parent.name)))
        day = int(doc["day"]) if isinstance(doc.get("day"), int) else int(day_match.group(1)) if day_match else 0
        grouped[lang][day].append(doc)
    return grouped


def lesson_blocks(doc: dict) -> list[dict]:
    blocks = [{"type": "text", "data": {"body": doc.get("content", "")}}]
    quiz = doc.get("quiz") or []
    if quiz:
        questions = []
        for q in quiz:
            questions.append({
                "question": q.get("question", ""),
                "options": q.get("options", []),
                "correct": int(q.get("correct", 0)),
            })
        blocks.append({"type": "quiz", "data": {"pass_score": 0, "questions": questions}})
    return blocks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Curriculum root containing day1..dayN folders")
    parser.add_argument("--tenant", required=True, help="Tenant slug to import into")
    parser.add_argument("--slug-prefix", default="imported", help="Curriculum slug prefix")
    parser.add_argument("--title", default="Imported Curriculum")
    parser.add_argument("--language", default=None, help="Only import this language code")
    parser.add_argument("--publish", action="store_true", help="Publish immediately")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        raise SystemExit(f"Root not found: {root}")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == args.tenant).first()
        if not tenant:
            raise SystemExit(f"Tenant '{args.tenant}' not found. Create it first (scripts.seed or API).")

        grouped = load_lessons(root, args.language)
        if not grouped:
            raise SystemExit("No lessons found — check --root and --language.")

        for lang, days in sorted(grouped.items()):
            slug = f"{args.slug_prefix}-{lang}"
            if db.query(Curriculum).filter(Curriculum.tenant_id == tenant.id,
                                           Curriculum.slug == slug).first():
                print(f"SKIP curriculum '{slug}': already exists")
                continue
            lang_name = LANG_NAMES.get(lang, lang)
            cur = Curriculum(
                tenant_id=tenant.id, slug=slug,
                title=f"{args.title} ({lang_name})",
                description=f"Imported from {root} — language: {lang_name}",
                language=lang, tags=["imported"],
                status=CurriculumStatus.PUBLISHED.value if args.publish else CurriculumStatus.DRAFT.value)
            db.add(cur)
            db.flush()
            total = 0
            for day in sorted(days):
                mod = Module(curriculum_id=cur.id, title=f"Day {day}", sort_order=day)
                db.add(mod)
                db.flush()
                for idx, doc in enumerate(sorted(days[day], key=lambda d: d.get("id", ""))):
                    db.add(Lesson(module_id=mod.id, title=doc["title"], sort_order=idx,
                                  blocks=lesson_blocks(doc)))
                    total += 1
            print(f"Imported '{slug}': {len(days)} modules, {total} lessons")
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
