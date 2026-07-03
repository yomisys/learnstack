"""Channel-agnostic conversation engine.

One state machine drives WhatsApp, SMS, and USSD. The engine takes an inbound
text message and returns outbound messages; channel capabilities decide how
lesson blocks render:

  whatsapp — real media messages (video/audio/image/document) + text
  sms      — text, media degraded to a link line
  ussd     — text only, media summarized; the handler adds CON/END framing

Every reply is a list of dicts:
  {"type": "text", "body": ...}
  {"type": "video"|"audio"|"image"|"document", "url": ..., "caption": ...}
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (Certificate, Conversation, Curriculum,
                        CurriculumStatus, Enrollment, Lesson, LessonProgress,
                        Tenant, User, UserRole)
from app.routers.learning import _maybe_complete
from app.security import hash_password


@dataclass(frozen=True)
class ChannelCaps:
    media: bool
    max_len: int
    terse: bool = False


CAPS = {
    "whatsapp": ChannelCaps(media=True, max_len=3800),
    "sms": ChannelCaps(media=False, max_len=450),
    "ussd": ChannelCaps(media=False, max_len=500, terse=True),
}

MEDIA_BLOCK_TYPES = {"video", "audio", "image", "file"}


def text_msg(body: str) -> dict:
    return {"type": "text", "body": body}


def chunk_text(body: str, max_len: int) -> list[str]:
    """Split on paragraph boundaries so no chunk exceeds max_len."""
    if len(body) <= max_len:
        return [body]
    chunks, current = [], ""
    for para in body.split("\n\n"):
        while len(para) > max_len:  # single paragraph longer than a screen
            chunks.append(para[:max_len])
            para = para[max_len:]
        if len(current) + len(para) + 2 > max_len:
            if current:
                chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


# ---- content rendering ----
def render_block(block: dict, caps: ChannelCaps) -> list[dict]:
    btype, data = block.get("type"), block.get("data", {})
    if btype == "text":
        return [text_msg(c) for c in chunk_text(data.get("body", ""), caps.max_len)]
    if btype in MEDIA_BLOCK_TYPES:
        url = data.get("url", "")
        caption = data.get("caption") or data.get("name") or data.get("alt") or ""
        if caps.media:
            kind = "document" if btype == "file" else btype
            return [{"type": kind, "url": url, "caption": caption}]
        if caps.terse:  # USSD: no links on feature phones
            label = caption or f"{btype} content"
            return [text_msg(f"[{label} - available on the web version]")]
        label = caption or btype.capitalize()
        return [text_msg(f"{label}: {url}")]
    if btype == "embed":
        url = data.get("url", "")
        return [text_msg(f"Interactive content: {url}")] if url and not caps.terse else []
    return []  # quiz blocks are driven by the state machine, not rendered inline


def lesson_sequence(curriculum: Curriculum) -> list[Lesson]:
    return [lesson for module in curriculum.modules for lesson in module.lessons]


def quiz_block_index(lesson: Lesson) -> int | None:
    for i, b in enumerate(lesson.blocks or []):
        if b.get("type") == "quiz":
            return i
    return None


def format_question(lesson: Lesson, block_idx: int, q_idx: int) -> str:
    q = lesson.blocks[block_idx]["data"]["questions"][q_idx]
    total = len(lesson.blocks[block_idx]["data"]["questions"])
    lines = [f"Question {q_idx + 1}/{total}: {q['question']}"]
    lines += [f"{i + 1}. {opt}" for i, opt in enumerate(q.get("options", []))]
    lines.append("Reply with the number of your answer.")
    return "\n".join(lines)


# ---- engine ----
class Engine:
    def __init__(self, db: Session, tenant: Tenant, channel: str, address: str):
        self.db = db
        self.tenant = tenant
        self.channel = channel
        self.address = address
        self.caps = CAPS[channel]
        self.branding = tenant.effective_branding()
        self.convo = self._get_or_create_conversation()

    # -- persistence helpers --
    def _get_or_create_conversation(self) -> Conversation:
        convo = (self.db.query(Conversation)
                 .filter(Conversation.tenant_id == self.tenant.id,
                         Conversation.channel == self.channel,
                         Conversation.address == self.address)
                 .first())
        if not convo:
            convo = Conversation(tenant_id=self.tenant.id, channel=self.channel,
                                 address=self.address, state="menu", data={})
            self.db.add(convo)
            self.db.flush()
        return convo

    def _get_or_create_user(self) -> User:
        if self.convo.user_id:
            return self.db.get(User, self.convo.user_id)
        email = f"{self.address.lstrip('+')}@{self.channel}.channel"
        user = (self.db.query(User)
                .filter(User.tenant_id == self.tenant.id, User.email == email)
                .first())
        if not user:
            user = User(tenant_id=self.tenant.id, email=email,
                        password_hash=hash_password(f"channel-{self.address}-no-login"),
                        full_name=self.address, role=UserRole.LEARNER.value)
            self.db.add(user)
            self.db.flush()
        self.convo.user_id = user.id
        return user

    def _published(self) -> list[Curriculum]:
        return (self.db.query(Curriculum)
                .filter(Curriculum.tenant_id == self.tenant.id,
                        Curriculum.status == CurriculumStatus.PUBLISHED.value)
                .order_by(Curriculum.id).all())

    def _progress_ids(self, enrollment: Enrollment) -> set[int]:
        return {p.lesson_id for p in enrollment.progress}

    # -- message flows --
    def show_menu(self) -> list[dict]:
        self.convo.state = "menu"
        curricula = self._published()
        name = self.branding.get("product_name") or self.tenant.name
        if not curricula:
            return [text_msg(f"Welcome to {name}! No courses are available yet - check back soon.")]
        lines = [f"Welcome to {name}!", "", "Available courses:"]
        lines += [f"{i + 1}. {c.title}" for i, c in enumerate(curricula)]
        lines += ["", "Reply with a course number to start.",
                  "Commands: PROGRESS, MENU, HELP"]
        return [text_msg("\n".join(lines))]

    def show_help(self) -> list[dict]:
        return [text_msg("Commands:\nMENU - course list\nNEXT - continue learning\n"
                         "PROGRESS - your progress\nHELP - this message")]

    def show_progress(self) -> list[dict]:
        if not self.convo.enrollment_id:
            return [text_msg("You're not enrolled yet. Reply MENU to pick a course.")]
        enr = self.db.get(Enrollment, self.convo.enrollment_id)
        lessons = lesson_sequence(enr.curriculum)
        done = len(self._progress_ids(enr) & {l.id for l in lessons})
        status = "COMPLETED" if enr.completed_at else "in progress"
        return [text_msg(f"{enr.curriculum.title}\nLessons: {done}/{len(lessons)} ({status})\n"
                         "Reply NEXT to continue.")]

    def enroll(self, curriculum: Curriculum) -> list[dict]:
        user = self._get_or_create_user()
        enr = (self.db.query(Enrollment)
               .filter(Enrollment.user_id == user.id,
                       Enrollment.curriculum_id == curriculum.id).first())
        if not enr:
            enr = Enrollment(tenant_id=self.tenant.id, user_id=user.id,
                             curriculum_id=curriculum.id)
            self.db.add(enr)
            self.db.flush()
        self.convo.enrollment_id = enr.id
        return [text_msg(f"You're enrolled in \"{curriculum.title}\"!")] + self.deliver_next_lesson()

    def deliver_next_lesson(self) -> list[dict]:
        enr = self.db.get(Enrollment, self.convo.enrollment_id)
        lessons = lesson_sequence(enr.curriculum)
        done = self._progress_ids(enr)
        pending = [l for l in lessons if l.id not in done]
        if not pending:
            return self.finish_course(enr)
        lesson = pending[0]
        self.convo.lesson_id = lesson.id
        number = lessons.index(lesson) + 1
        out = [text_msg(f"Lesson {number}/{len(lessons)}: {lesson.title}")]
        for block in lesson.blocks or []:
            out += render_block(block, self.caps)
        q_idx = quiz_block_index(lesson)
        if q_idx is not None:
            self.convo.state = "quiz"
            self.convo.data = {"quiz_block_idx": q_idx, "quiz_q_idx": 0, "answers": []}
            out.append(text_msg(format_question(lesson, q_idx, 0)))
        else:
            self.convo.state = "lesson"
            self.convo.data = {}
            out.append(text_msg("Reply NEXT when you're done with this lesson."))
        return out

    def finish_course(self, enr: Enrollment) -> list[dict]:
        self.convo.state = "menu"
        self.convo.lesson_id = None
        cert = (self.db.query(Certificate)
                .filter(Certificate.user_id == enr.user_id,
                        Certificate.curriculum_id == enr.curriculum_id).first())
        msg = f"Congratulations! You completed \"{enr.curriculum.title}\"."
        if cert:
            msg += (f"\nYour certificate code: {cert.code}"
                    f"\nAnyone can verify it on the {self.branding.get('product_name', '')} website.")
        msg += "\nReply MENU to explore more courses."
        return [text_msg(msg)]

    def complete_current_lesson(self) -> list[dict]:
        enr = self.db.get(Enrollment, self.convo.enrollment_id)
        lesson_id = self.convo.lesson_id
        if lesson_id and lesson_id not in self._progress_ids(enr):
            self.db.add(LessonProgress(enrollment_id=enr.id, lesson_id=lesson_id))
            self.db.flush()
            self.db.refresh(enr)
            _maybe_complete(self.db, enr, self.tenant)
            self.db.flush()
        if enr.completed_at:
            return self.finish_course(enr)
        return self.deliver_next_lesson()

    def handle_quiz_answer(self, message: str) -> list[dict]:
        enr = self.db.get(Enrollment, self.convo.enrollment_id)
        lesson = self.db.get(Lesson, self.convo.lesson_id)
        state = dict(self.convo.data or {})
        block_idx, q_idx = state["quiz_block_idx"], state["quiz_q_idx"]
        questions = lesson.blocks[block_idx]["data"]["questions"]
        options = questions[q_idx].get("options", [])

        answer = self._parse_answer(message, len(options))
        if answer is None:
            return [text_msg(f"Please reply with a number between 1 and {len(options)}."),
                    text_msg(format_question(lesson, block_idx, q_idx))]

        answers = state["answers"] + [answer]
        if q_idx + 1 < len(questions):
            self.convo.data = {**state, "quiz_q_idx": q_idx + 1, "answers": answers}
            return [text_msg(format_question(lesson, block_idx, q_idx + 1))]

        # last question answered — grade
        correct = [int(q.get("correct", 0)) for q in questions]
        score = sum(1 for a, c in zip(answers, correct) if a == c)
        pass_score = int(lesson.blocks[block_idx]["data"].get("pass_score", 0))
        passed = (score * 100 / len(questions) >= pass_score) if questions else True

        prog = next((p for p in enr.progress if p.lesson_id == lesson.id), None)
        if prog is None:
            prog = LessonProgress(enrollment_id=enr.id, lesson_id=lesson.id)
            self.db.add(prog)
            self.db.flush()
            self.db.refresh(enr)
        prog.quiz_score, prog.quiz_total = score, len(questions)
        _maybe_complete(self.db, enr, self.tenant)
        self.db.flush()

        result = f"You scored {score}/{len(questions)}." + (" Well done!" if passed else " Keep practicing!")
        self.convo.data = {}
        if enr.completed_at:
            return [text_msg(result)] + self.finish_course(enr)
        self.convo.state = "lesson"
        return [text_msg(result), text_msg("Reply NEXT for your next lesson.")]

    @staticmethod
    def _parse_answer(message: str, n_options: int) -> int | None:
        token = message.strip().upper()
        if token.isdigit() and 1 <= int(token) <= n_options:
            return int(token) - 1
        if len(token) == 1 and "A" <= token <= "Z" and ord(token) - 65 < n_options:
            return ord(token) - 65
        return None

    # -- entry point --
    def handle(self, message: str) -> list[dict]:
        text = (message or "").strip()
        command = text.upper()
        try:
            if command in ("MENU", "COURSES", "START", "HI", "HELLO", ""):
                return self.show_menu()
            if command == "HELP":
                return self.show_help()
            if command == "PROGRESS":
                return self.show_progress()

            if self.convo.state == "quiz" and self.convo.enrollment_id:
                return self.handle_quiz_answer(text)
            if command in ("NEXT", "CONTINUE", "DONE") and self.convo.enrollment_id:
                if self.convo.state == "lesson":
                    return self.complete_current_lesson()
                return self.deliver_next_lesson()
            if self.convo.state == "menu":
                curricula = self._published()
                if text.isdigit() and 1 <= int(text) <= len(curricula):
                    return self.enroll(curricula[int(text) - 1])
                return self.show_menu()
            # unknown input mid-lesson
            return [text_msg("Sorry, I didn't understand that. Reply NEXT to continue or MENU for courses.")]
        finally:
            self.convo.updated_at = datetime.utcnow()
            self.db.commit()


def handle_inbound(db: Session, tenant: Tenant, channel: str, address: str,
                   message: str) -> list[dict]:
    """Process one inbound message; returns outbound messages to deliver."""
    if channel not in CAPS:
        raise ValueError(f"Unknown channel '{channel}'")
    return Engine(db, tenant, channel, address).handle(message)
