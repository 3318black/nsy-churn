"""Tests of the course reader, on the real files of ``docs/cours``.

The course application parses the Markdown as the lots keep writing it. These
tests fail as soon as a file drifts from the shape the application reads.
"""

from __future__ import annotations

import pytest

from churn.interface.course import (
    PASS_MARK,
    Course,
    Diagram,
    Fold,
    Prose,
    lesson_segments,
    load_course,
    mermaid_to_dot,
    parse_quiz,
    score,
)


@pytest.fixture(scope="module")
def course() -> Course:
    """The course of the repository."""
    return load_course()


def test_the_plan_lists_every_chapter_and_its_quizzes(course: Course) -> None:
    """Four parts, twelve chapters, one quiz closing each part, every file present."""
    assert [part.number for part in course.parts] == [1, 2, 3, 4]
    chapters = [lesson for lesson in course.lessons if not lesson.is_quiz]
    assert [lesson.slug[:2] for lesson in chapters] == [f"{n:02d}" for n in range(1, 13)]
    for part in course.parts:
        assert part.lessons[-1].slug == f"quiz-partie-{part.number}"
        assert all(lesson.minutes > 0 for lesson in part.lessons)
    for lesson in course.lessons:
        assert (course.directory / f"{lesson.slug}.md").is_file(), lesson.slug


def test_the_welcome_page_keeps_only_what_learners_need(course: Course) -> None:
    """The plan becomes the navigation, and the authoring rules stay out."""
    assert "## Pour qui ?" in course.welcome
    assert "## Plan du cours" not in course.welcome
    assert "Règles d'écriture" not in course.welcome
    assert "Suivre le cours dans l'application" not in course.welcome
    assert ".md)" not in course.welcome


@pytest.mark.parametrize("slug", [f"{n:02d}" for n in range(1, 13)])
def test_every_chapter_holds_one_correction_and_no_raw_html(course: Course, slug: str) -> None:
    """The correction becomes a fold, and nothing the page cannot render is left."""
    lesson = next(lesson for lesson in course.lessons if lesson.slug.startswith(slug))
    segments = lesson_segments(course.text(lesson))
    folds = [segment for segment in segments if isinstance(segment, Fold)]
    assert [fold.summary for fold in folds] == ["Voir la correction"]
    for segment in segments:
        text = segment.text if isinstance(segment, Prose) else ""
        text += segment.body if isinstance(segment, Fold) else ""
        assert "<details>" not in text
        assert "```mermaid" not in text
        assert ".md)" not in text, "a link to a course file would open the raw file"
        assert "Chapitre précédent" not in text


def test_diagrams_are_set_apart(course: Course) -> None:
    """The two Mermaid diagrams of the course are drawn, not shown as code."""
    drawn = {
        lesson.slug: [s for s in lesson_segments(course.text(lesson)) if isinstance(s, Diagram)]
        for lesson in course.lessons
        if not lesson.is_quiz
    }
    assert {slug for slug, diagrams in drawn.items() if diagrams} == {
        "01-application",
        "03-outils",
    }
    assert drawn["01-application"][0].source.startswith("flowchart LR")


@pytest.mark.parametrize("part", [1, 2, 3, 4])
def test_every_quiz_has_ten_answered_questions(course: Course, part: int) -> None:
    """Each question offers four options, one of which is its answer."""
    quiz = parse_quiz(course.text(course.lesson(f"quiz-partie-{part}")))
    assert len(quiz.questions) == 10
    for question in quiz.questions:
        assert [letter for letter, _ in question.options] == ["A", "B", "C", "D"]
        assert question.explanation
    assert f"{PASS_MARK} bonnes réponses" in quiz.advice
    assert quiz.title.startswith(f"Quiz de la partie {part}")


def test_a_quiz_scores_right_answers_only(course: Course) -> None:
    """A wrong or missing response counts for nothing."""
    quiz = parse_quiz(course.text(course.lesson("quiz-partie-1")))
    perfect = {question.number: question.answer for question in quiz.questions}
    assert score(quiz, perfect) == 10
    assert score(quiz, {**perfect, 1: None, 2: "Z"}) == 8
    assert score(quiz, {}) == 0


def test_an_answer_outside_the_options_is_refused() -> None:
    """A typo in the answers would silently mark every learner wrong."""
    text = "# Quiz\n\n**1. Question ?**\n\n- A. Oui\n- B. Non\n\n1. **C.** Explication.\n"
    with pytest.raises(ValueError, match="not one of its options"):
        parse_quiz(text)


def test_the_neighbours_follow_the_reading_order(course: Course) -> None:
    """The first lesson has nothing before it, the last nothing after it."""
    first, last = course.lessons[0], course.lessons[-1]
    assert course.neighbours(first.slug)[0] is None
    assert course.neighbours(last.slug)[1] is None
    assert course.neighbours(course.lessons[1].slug) == (first, course.lessons[2])


def _diagram(course: Course, slug: str) -> str:
    """Return the source of the first diagram of a chapter."""
    segments = lesson_segments(course.text(course.lesson(slug)))
    return next(segment.source for segment in segments if isinstance(segment, Diagram))


def test_a_flowchart_becomes_a_graphviz_diagram(course: Course) -> None:
    """Chapter 1: a left to right chain of labelled steps, line breaks kept."""
    dot = mermaid_to_dot(_diagram(course, "01-application"))
    assert "rankdir=LR;" in dot
    assert '"A" -> "B";' in dot
    assert '"Données brutes\\nabonnements et écoutes"' in dot
    assert dot.count(" -> ") == 5


def test_subgraphs_become_clusters_linked_to_each_other(course: Course) -> None:
    """Chapter 3: four groups of tools, the edges between groups kept."""
    dot = mermaid_to_dot(_diagram(course, "03-outils"))
    assert dot.count("subgraph ") == 4
    assert 'subgraph "cluster_Préparer"' in dot
    assert '"K" -> "Z";' in dot
    assert 'lhead="cluster_Préparer"' in dot
    assert 'ltail="cluster_Apprendre"' in dot


def test_an_unsupported_diagram_is_refused() -> None:
    """A new kind of diagram must fail here, not be drawn wrong online."""
    with pytest.raises(ValueError, match="only Mermaid flowcharts"):
        mermaid_to_dot("sequenceDiagram\n    A->>B: bonjour")
    with pytest.raises(ValueError, match="unsupported Mermaid line"):
        mermaid_to_dot("flowchart LR\n    A -.-> B")


def test_the_glossary_lists_each_term_with_its_chapter(course: Course) -> None:
    """Every term the course defines can be looked up."""
    glossary = course.glossary()
    assert len(glossary) >= 60
    assert glossary.set_index("terme").loc["Délai de constat", "chapitres"] == "7"
    assert not glossary["terme"].str.contains(r"\*\*").any()
