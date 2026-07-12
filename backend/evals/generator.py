import random
from pathlib import Path

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from ..rag.connectors import ObsidianConnector
from ..rag.connectors.base import SourceDocument
from .goldset import GoldItem

GENERATOR_MODEL = "claude-haiku-4-5"

# Notes shorter than this rarely support a meaningful question.
MIN_NOTE_CHARS = 80
# Cap the note text sent to the generator.
MAX_PROMPT_CHARS = 4000

MULTI_NOTE_SHARE = 0.15
NEGATIVE_SHARE = 0.10


class DraftQA(BaseModel):
    question: str = Field(description="A question a user could ask about their notes")
    expected_answer_points: list[str] = Field(
        description="2 to 4 short factual points that a correct answer must contain"
    )


class DraftNegatives(BaseModel):
    questions: list[str] = Field(
        description="Questions whose answers are clearly absent from the notes"
    )


SINGLE_NOTE_PROMPT = """\
You are building an evaluation set for a personal-notes RAG assistant.
Here is one note from the user's vault (title: {title}):

<note>
{content}
</note>

Write ONE question, in the same language as the note, that this note answers.
The question must be self-contained (understandable without seeing the note) and
its answer must be found in the note. Also list the short factual points a
correct answer must contain."""

MULTI_NOTE_PROMPT = """\
You are building an evaluation set for a personal-notes RAG assistant.
Here are two related notes from the user's vault:

<note title="{title_a}">
{content_a}
</note>

<note title="{title_b}">
{content_b}
</note>

Write ONE question, in the same language as the notes, whose complete answer
requires information from BOTH notes. Also list the short factual points a
correct answer must contain (mixing facts from the two notes)."""

NEGATIVE_PROMPT = """\
You are building an evaluation set for a personal-notes RAG assistant.
The user's vault covers these topics (note titles):

{titles}

Write {count} short questions, in the same language as the titles, about
plausible personal-notes topics that are clearly NOT covered by this vault.
The assistant should answer "I don't know" to them."""


class GoldsetGenerator:
    """LLM-assisted gold set draft generator. Output requires human review."""

    def __init__(self, llm=None):
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            self._llm = init_chat_model(
                GENERATOR_MODEL, model_provider="anthropic", temperature=0.7
            )
        return self._llm

    def _single(self, doc: SourceDocument) -> tuple[str, list[str]]:
        prompt = SINGLE_NOTE_PROMPT.format(
            title=doc.metadata["note_title"], content=doc.content[:MAX_PROMPT_CHARS]
        )
        draft = self.llm.with_structured_output(DraftQA).invoke(
            [{"role": "user", "content": prompt}]
        )
        return draft.question, draft.expected_answer_points

    def _multi(self, doc_a: SourceDocument, doc_b: SourceDocument) -> tuple[str, list[str]]:
        prompt = MULTI_NOTE_PROMPT.format(
            title_a=doc_a.metadata["note_title"],
            content_a=doc_a.content[: MAX_PROMPT_CHARS // 2],
            title_b=doc_b.metadata["note_title"],
            content_b=doc_b.content[: MAX_PROMPT_CHARS // 2],
        )
        draft = self.llm.with_structured_output(DraftQA).invoke(
            [{"role": "user", "content": prompt}]
        )
        return draft.question, draft.expected_answer_points

    def _negatives(self, titles: list[str], count: int) -> list[str]:
        prompt = NEGATIVE_PROMPT.format(titles="\n".join(f"- {t}" for t in titles), count=count)
        draft = self.llm.with_structured_output(DraftNegatives).invoke(
            [{"role": "user", "content": prompt}]
        )
        return draft.questions[:count]

    def generate(
        self, vault_path: str | Path, n: int, seed: int = 42, on_progress=None
    ) -> list[GoldItem]:
        rng = random.Random(seed)
        notes = [
            doc
            for doc in ObsidianConnector(vault_path).iter_documents()
            if len(doc.content) >= MIN_NOTE_CHARS
        ]
        if not notes:
            raise ValueError("No usable notes found in the vault")

        n_negative = round(n * NEGATIVE_SHARE)
        n_multi = round(n * MULTI_NOTE_SHARE)
        n_single = n - n_negative - n_multi

        by_title = {doc.metadata["note_title"]: doc for doc in notes}
        linked_pairs = [
            (doc, by_title[target])
            for doc in notes
            for target in doc.metadata.get("outlinks", [])
            if target in by_title and by_title[target] is not doc
        ]

        items: list[GoldItem] = []

        def _emit(question, note_paths, points, tags):
            items.append(
                GoldItem(
                    id=f"q{len(items) + 1:03d}",
                    question=question,
                    expected_note_paths=note_paths,
                    expected_answer_points=points,
                    tags=tags,
                )
            )
            if on_progress:
                on_progress(len(items))

        for doc in _weighted_sample(notes, n_single, rng):
            question, points = self._single(doc)
            _emit(question, [doc.metadata["note_path"]], points, ["factual"])

        for doc_a, doc_b in _sample_pairs(notes, linked_pairs, n_multi, rng):
            question, points = self._multi(doc_a, doc_b)
            paths = [doc_a.metadata["note_path"], doc_b.metadata["note_path"]]
            _emit(question, paths, points, ["multi-note"])

        if n_negative:
            titles = [doc.metadata["note_title"] for doc in notes][:50]
            for question in self._negatives(titles, n_negative):
                _emit(question, [], [], ["negative"])

        return items


def _weighted_sample(notes: list[SourceDocument], count: int, rng: random.Random):
    """Sample notes weighted by content length, without replacement while possible."""
    pool = list(notes)
    picked = []
    for _ in range(count):
        if not pool:
            pool = list(notes)  # fewer notes than questions: allow repeats
        weights = [len(doc.content) for doc in pool]
        choice = rng.choices(pool, weights=weights, k=1)[0]
        pool.remove(choice)
        picked.append(choice)
    return picked


def _sample_pairs(notes, linked_pairs, count: int, rng: random.Random):
    """Prefer wikilink-connected pairs; fall back to random pairs."""
    pairs = list(linked_pairs)
    rng.shuffle(pairs)
    picked = pairs[:count]
    while len(picked) < count and len(notes) >= 2:
        picked.append(tuple(rng.sample(notes, 2)))
    return picked
