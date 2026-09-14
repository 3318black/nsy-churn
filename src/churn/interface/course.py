"""The beginner course of ``docs/cours``, read as it stands for the course application.

The course is written once, in Markdown. Every lot keeps editing those files and
nothing else: the application parses their fixed shapes instead of holding a copy.
``tests/test_course.py`` checks these shapes against the real files, so a change
of format fails a test rather than a page.

Plan
    ``README.md`` lists each part under ``### Partie N. Title``, with one table
    row per lesson: ``| [label](file.md) | 20 min |``.
Chapter
    One ``<details>`` block holds the correction of the exercise, diagrams are
    ``mermaid`` code blocks, and the last line links to the neighbouring lessons.
Quiz
    Questions ``**N. prompt**``, each followed by ``- A. option`` lines, then the
    answers inside ``<details>``: ``N. **B.** explanation``.
Glossary
    One table row per term: ``| **Term** | Definition | Chapter |``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import pandas as pd

from churn.config import PROJECT_ROOT

__all__ = [
    "COURSE_DIR",
    "PASS_MARK",
    "Course",
    "Diagram",
    "Fold",
    "Lesson",
    "Part",
    "Prose",
    "Question",
    "Quiz",
    "Segment",
    "lesson_segments",
    "load_course",
    "mermaid_to_dot",
    "parse_glossary",
    "parse_quiz",
    "score",
    "unlink_local",
]

#: Where the course lives in the repository.
COURSE_DIR = PROJECT_ROOT / "docs" / "cours"

#: The plan of the course, and the glossary.
PLAN_FILE = "README.md"
GLOSSARY_FILE = "glossaire.md"

#: Correct answers out of ten a quiz asks for before the next part, as every quiz says.
PASS_MARK = 8

#: Sections of the plan the application does not show: its plan becomes the menu,
#: the application needs no introduction to itself, and the writing rules are for
#: the authors of the course.
HIDDEN_SECTIONS = ("Suivre le cours dans l'application", "Plan du cours", "Règles d'écriture")

_PART = re.compile(r"^### Partie (?P<number>\d+)\. (?P<title>.+)$")
_ROW = re.compile(r"^\| \[(?P<label>[^\]]+)\]\((?P<slug>[\w-]+)\.md\) \| (?P<minutes>\d+) min \|$")
_LOCAL_LINK = re.compile(r"\[(?P<label>[^\]]+)\]\([\w-]+\.md\)")
_NAVIGATION = re.compile(r"(?m)^\*\*(?:Chapitre précédent|Chapitre suivant|Retour au)\b.*$")
_BLOCK = re.compile(
    r"<details>\s*<summary>(?P<summary>.*?)</summary>(?P<body>.*?)</details>"
    r"|```mermaid\n(?P<source>.*?)```",
    re.DOTALL,
)
_QUESTION = re.compile(r"^\*\*(?P<number>\d+)\. (?P<prompt>.+)\*\*$")
_OPTION = re.compile(r"^- (?P<letter>[A-D])\. (?P<text>.+)$")
_ANSWER = re.compile(r"^(?P<number>\d+)\. \*\*(?P<letter>[A-D])\.\*\* (?P<explanation>.+)$")
_ADVICE = re.compile(r"^\*\*Votre score :\*\* (?P<advice>.+)$")
_TERM = re.compile(r"^\| \*\*(?P<term>.+?)\*\* \| (?P<definition>.+) \| (?P<chapters>[\d, ]+) \|$")


@dataclass(frozen=True, slots=True)
class Lesson:
    """One chapter or quiz of the course.

    Attributes:
        slug: file name without its extension, for instance ``07-evaluer-honnetement``.
        label: title as the plan writes it.
        minutes: reading time the plan announces.
        part: number of the part the lesson belongs to.
    """

    slug: str
    label: str
    minutes: int
    part: int

    @property
    def is_quiz(self) -> bool:
        """Whether the lesson is the quiz closing its part."""
        return self.slug.startswith("quiz-")

    @property
    def short_label(self) -> str:
        """The label up to its subtitle, short enough for a menu."""
        return self.label.split(" : ", 1)[0]


@dataclass(frozen=True, slots=True)
class Part:
    """One part of the course and its lessons, in reading order."""

    number: int
    title: str
    lessons: tuple[Lesson, ...]


@dataclass(frozen=True, slots=True)
class Course:
    """The plan of the course and where its files are.

    Attributes:
        directory: folder of the Markdown files.
        title: title of the course.
        welcome: the sections of the plan meant for learners, as Markdown.
        parts: the parts, in reading order.
    """

    directory: Path
    title: str
    welcome: str
    parts: tuple[Part, ...]

    @property
    def lessons(self) -> tuple[Lesson, ...]:
        """Every lesson, in reading order."""
        return tuple(lesson for part in self.parts for lesson in part.lessons)

    def lesson(self, slug: str) -> Lesson:
        """Return the lesson of a slug."""
        for lesson in self.lessons:
            if lesson.slug == slug:
                return lesson
        message = f"no lesson '{slug}' in the plan of the course"
        raise KeyError(message)

    def text(self, lesson: Lesson) -> str:
        """Return the Markdown of a lesson."""
        return (self.directory / f"{lesson.slug}.md").read_text(encoding="utf-8")

    def glossary(self) -> pd.DataFrame:
        """Return the glossary, one row per term."""
        return parse_glossary((self.directory / GLOSSARY_FILE).read_text(encoding="utf-8"))

    def neighbours(self, slug: str) -> tuple[Lesson | None, Lesson | None]:
        """Return the lessons read just before and just after a lesson."""
        lessons = self.lessons
        position = lessons.index(self.lesson(slug))
        previous = lessons[position - 1] if position > 0 else None
        following = lessons[position + 1] if position + 1 < len(lessons) else None
        return previous, following


@dataclass(frozen=True, slots=True)
class Prose:
    """Markdown the application displays as it is."""

    text: str


@dataclass(frozen=True, slots=True)
class Fold:
    """A block the learner unfolds on purpose, such as the correction of an exercise."""

    summary: str
    body: str


@dataclass(frozen=True, slots=True)
class Diagram:
    """A Mermaid diagram, which Markdown alone does not draw."""

    source: str


type Segment = Prose | Fold | Diagram


@dataclass(frozen=True, slots=True)
class Question:
    """One question of a quiz.

    Attributes:
        number: position in the quiz, starting at one.
        prompt: the question.
        options: the choices, as ``(letter, text)`` pairs.
        answer: letter of the right choice.
        explanation: why it is right, and where the course explains it.
    """

    number: int
    prompt: str
    options: tuple[tuple[str, str], ...]
    answer: str
    explanation: str


@dataclass(frozen=True, slots=True)
class Quiz:
    """A quiz closing a part of the course."""

    title: str
    introduction: str
    questions: tuple[Question, ...]
    advice: str


def unlink_local(text: str) -> str:
    """Replace links to other course files by their label.

    Inside the application, lessons are reached through its own navigation. A link
    to a Markdown file would open the raw file instead.
    """
    return _LOCAL_LINK.sub(r"\g<label>", text)


def _learner_sections(plan: str) -> str:
    """Return the plan without its title and without the sections the application hides."""
    body = plan.split("\n", 1)[1] if "\n" in plan else ""
    chunks = re.split(r"(?m)^(?=## )", body)
    hidden = tuple(f"## {section}" for section in HIDDEN_SECTIONS)
    kept = [chunk for chunk in chunks if not chunk.startswith(hidden)]
    return unlink_local("".join(kept)).strip()


def load_course(directory: Path = COURSE_DIR) -> Course:
    """Read the plan of the course.

    Args:
        directory: folder of the Markdown files.

    Returns:
        The course, its parts and their lessons in reading order.

    Raises:
        ValueError: when the plan lists no lesson, which means its shape changed.
    """
    plan = (directory / PLAN_FILE).read_text(encoding="utf-8")
    lines = plan.splitlines()
    parts: list[Part] = []
    number, title, lessons = 0, "", list[Lesson]()
    for line in [*lines, "### "]:
        heading = _PART.match(line)
        if heading or line.startswith("### "):
            if lessons:
                parts.append(Part(number, title, tuple(lessons)))
            lessons = []
            number, title = (int(heading["number"]), heading["title"]) if heading else (0, "")
            continue
        row = _ROW.match(line.strip())
        if row and number:
            lessons.append(Lesson(row["slug"], row["label"], int(row["minutes"]), number))
    if not parts:
        message = f"the plan {directory / PLAN_FILE} lists no lesson"
        raise ValueError(message)
    return Course(
        directory=directory,
        title=lines[0].removeprefix("# ").strip(),
        welcome=_learner_sections(plan),
        parts=tuple(parts),
    )


def _append_prose(segments: list[Segment], text: str) -> None:
    """Keep a stretch of Markdown, unless nothing but blank lines and rules remain."""
    if text.strip().strip("-").strip():
        segments.append(Prose(unlink_local(text).strip()))


def lesson_segments(text: str) -> list[Segment]:
    """Cut a chapter into what the application displays differently.

    The navigation line at the bottom is dropped: the application has its own.

    Args:
        text: the Markdown of a chapter.

    Returns:
        The prose, folds and diagrams, in their order.
    """
    text = _NAVIGATION.sub("", text)
    segments: list[Segment] = []
    position = 0
    for match in _BLOCK.finditer(text):
        _append_prose(segments, text[position : match.start()])
        if match["source"] is not None:
            segments.append(Diagram(match["source"].strip()))
        else:
            segments.append(Fold(match["summary"].strip(), unlink_local(match["body"]).strip()))
        position = match.end()
    _append_prose(segments, text[position:])
    return segments


def parse_quiz(text: str) -> Quiz:
    """Read a quiz, its questions and their answers.

    Args:
        text: the Markdown of a quiz.

    Returns:
        The quiz.

    Raises:
        ValueError: when a question has no answer, or an answer names no option.
    """
    lines = [line.strip() for line in text.splitlines()]
    prompts: dict[int, str] = {}
    options: dict[int, list[tuple[str, str]]] = {}
    answers: dict[int, tuple[str, str]] = {}
    advice = ""
    current = 0
    for line in lines:
        if question := _QUESTION.match(line):
            current = int(question["number"])
            prompts[current] = question["prompt"]
            options[current] = []
        elif (option := _OPTION.match(line)) and current:
            options[current].append((option["letter"], option["text"]))
        elif answer := _ANSWER.match(line):
            answers[int(answer["number"])] = (answer["letter"], answer["explanation"])
        elif found := _ADVICE.match(line):
            advice = found["advice"]

    questions: list[Question] = []
    for number, prompt in prompts.items():
        if number not in answers:
            message = f"question {number} has no answer"
            raise ValueError(message)
        letter, explanation = answers[number]
        if letter not in {choice for choice, _ in options[number]}:
            message = f"the answer {letter} of question {number} is not one of its options"
            raise ValueError(message)
        questions.append(Question(number, prompt, tuple(options[number]), letter, explanation))

    introduction = next((line.removeprefix("> ") for line in lines if line.startswith("> ")), "")
    return Quiz(
        title=lines[0].removeprefix("# ") if lines else "",
        introduction=introduction,
        questions=tuple(questions),
        advice=advice,
    )


def score(quiz: Quiz, responses: Mapping[int, str | None]) -> int:
    """Count the right answers, a missing response counting as wrong."""
    return sum(responses.get(question.number) == question.answer for question in quiz.questions)


def parse_glossary(text: str) -> pd.DataFrame:
    """Read the glossary.

    Args:
        text: the Markdown of the glossary.

    Returns:
        One row per term, with its definition and the chapters explaining it.
    """
    rows = [
        {
            "terme": term["term"],
            "definition": term["definition"],
            "chapitres": term["chapters"].strip(),
        }
        for line in text.splitlines()
        if (term := _TERM.match(line.strip()))
    ]
    return pd.DataFrame(rows, columns=["terme", "definition", "chapitres"])


_FLOWCHART = re.compile(r"^flowchart (?P<direction>LR|RL|TB|TD|BT)$")
_SUBGRAPH = re.compile(r"^subgraph (?P<id>[^\s\[\]]+)\[(?P<label>[^\]]*)\]$")
_MERMAID_NODE = re.compile(r"^(?P<id>[^\s\[\]]+)(?:\[(?P<label>[^\]]*)\])?$")


def _dot_string(text: str) -> str:
    """Quote a Mermaid name or label for Graphviz, its line breaks included."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("<br/>", "\\n")
    return f'"{escaped}"'


@dataclass(frozen=True, slots=True)
class _Flowchart:
    """A Mermaid flowchart, as far as the course uses it.

    Attributes:
        direction: Graphviz direction, ``LR`` or ``TB`` for instance.
        labels: label of each node, by name.
        clusters: label and member nodes of each subgraph, by name.
        edges: ``(tail, head)`` pairs, each end a node or a subgraph.
    """

    direction: str
    labels: dict[str, str]
    clusters: dict[str, tuple[str, list[str]]]
    edges: list[tuple[str, str]]


def _declare(chart: _Flowchart, part: str, cluster: str | None, line: str) -> str:
    """Register the node one end of a Mermaid line names, and return its name."""
    node = _MERMAID_NODE.match(part.strip())
    if node is None:
        message = f"unsupported Mermaid line: {line}"
        raise ValueError(message)
    name = node["id"]
    if name not in chart.labels and name not in chart.clusters:
        chart.labels[name] = node["label"] if node["label"] is not None else name
        if cluster is not None:
            chart.clusters[cluster][1].append(name)
    return name


def _parse_flowchart(source: str) -> _Flowchart:
    """Read the direction, nodes, subgraphs and edges of a Mermaid flowchart."""
    lines = [line.strip() for line in source.strip().splitlines() if line.strip()]
    header = _FLOWCHART.match(lines[0]) if lines else None
    if header is None:
        message = f"only Mermaid flowcharts are supported, got {lines[:1]}"
        raise ValueError(message)
    direction = "TB" if header["direction"] == "TD" else header["direction"]
    chart = _Flowchart(direction, {}, {}, [])
    current: str | None = None
    for line in lines[1:]:
        if subgraph := _SUBGRAPH.match(line):
            current = subgraph["id"]
            chart.clusters[current] = (subgraph["label"], [])
        elif line == "end":
            current = None
        else:
            ends = [_declare(chart, part, current, line) for part in line.split("-->")]
            chart.edges.extend(pairwise(ends))
    return chart


def _edge(chart: _Flowchart, tail: str, head: str) -> str:
    """Write one edge. An end that is a subgraph is drawn from its first node."""
    attributes: list[str] = []
    drawn: list[str] = []
    for end, side in ((tail, "ltail"), (head, "lhead")):
        name = end
        if end in chart.clusters:
            members = chart.clusters[end][1]
            if not members:
                message = f"the subgraph {end} holds no node to draw an edge from"
                raise ValueError(message)
            attributes.append(f"{side}={_dot_string('cluster_' + end)}")
            name = members[0]
        drawn.append(_dot_string(name))
    suffix = f" [{', '.join(attributes)}]" if attributes else ""
    return f"  {drawn[0]} -> {drawn[1]}{suffix};"


def mermaid_to_dot(source: str) -> str:
    """Translate a Mermaid flowchart into the Graphviz language Streamlit draws.

    Streamlit draws Graphviz natively, where Mermaid would need a script loaded
    from outside the application. Only what the course uses is understood: a
    direction, labelled nodes, ``-->`` chains, and subgraphs, which may be the
    ends of an edge.

    Args:
        source: the Mermaid code, without its fences.

    Returns:
        The same diagram in the DOT language.

    Raises:
        ValueError: on any other Mermaid construction, so that a new diagram fails
            a test rather than being drawn wrong.
    """
    chart = _parse_flowchart(source)
    dot = [
        "digraph {",
        f"  rankdir={chart.direction};",
        "  compound=true;",
        '  node [shape=box, style="rounded,filled", fillcolor="#eef2f8", color="#5b6b82"];',
        '  edge [color="#5b6b82"];',
    ]
    for name, (label, members) in chart.clusters.items():
        dot.append(f"  subgraph {_dot_string('cluster_' + name)} {{")
        dot.append(f"    label={_dot_string(label)};")
        dot.extend(f"    {_dot_string(member)};" for member in members)
        dot.append("  }")
    dot.extend(
        f"  {_dot_string(name)} [label={_dot_string(label)}];"
        for name, label in chart.labels.items()
    )
    dot.extend(_edge(chart, tail, head) for tail, head in chart.edges)
    dot.append("}")
    return "\n".join(dot)
