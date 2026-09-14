"""Tests of the course application, run headless with Streamlit's AppTest."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from churn.config import PROJECT_ROOT
from churn.interface.course import Course, Quiz, load_course, parse_quiz

APP = PROJECT_ROOT / "app" / "cours_app.py"


@pytest.fixture(scope="module")
def course() -> Course:
    """The course of the repository."""
    return load_course()


def _open(lesson: str | None = None) -> AppTest:
    """Run the application, on a lesson when one is named in the link."""
    app = AppTest.from_file(str(APP), default_timeout=60)
    if lesson is not None:
        app.query_params["lecon"] = lesson
    app.run()
    assert not app.exception
    return app


def _markdown(app: AppTest) -> str:
    """Return every Markdown block of the page, joined."""
    return "\n".join(element.value for element in app.markdown)


def _menu(app: AppTest) -> list[str]:
    """Return the labels of the menu, as the learner reads them."""
    return list(app.sidebar.radio[0].options)


def test_the_course_opens_on_its_welcome_page(course: Course) -> None:
    """The welcome page, and a menu holding every lesson and the glossary."""
    app = _open()
    assert app.title[0].value == course.title
    assert len(_menu(app)) == len(course.lessons) + 2
    assert "Pour qui ?" in _markdown(app)


def test_a_link_opens_a_chapter_with_its_correction_folded() -> None:
    """``?lecon=`` opens the chapter, and no raw HTML reaches the page."""
    app = _open("07-evaluer-honnetement")
    assert "Chapitre 7" in _markdown(app)
    assert [expander.label for expander in app.expander] == ["Voir la correction"]
    assert "<details>" not in _markdown(app)


def test_an_unknown_link_falls_back_to_the_welcome_page(course: Course) -> None:
    """A broken link is a welcome page, never an error."""
    app = _open("n-existe-pas")
    assert app.title[0].value == course.title


def test_diagrams_are_drawn() -> None:
    """Chapter 1 shows its diagram, not its Mermaid code."""
    app = _open("01-application")
    assert app.get("graphviz_chart")
    assert "```mermaid" not in _markdown(app)


def test_the_next_button_opens_the_following_lesson() -> None:
    """Lessons read in order, without going back to the menu."""
    app = _open("01-application")
    app.button(key="suivant").click().run()
    assert "Chapitre 2" in _markdown(app)


def test_a_finished_chapter_stays_ticked_in_the_menu() -> None:
    """Progress survives moving to another lesson."""
    app = _open("01-application")
    app.checkbox(key="case-01-application").check().run()
    assert _menu(app)[1].startswith("✓")
    app.sidebar.radio[0].set_value("02-methode").run()
    assert _menu(app)[1].startswith("✓")


def _answer_every_question(app: AppTest, course: Course, slug: str, *, right: bool) -> Quiz:
    """Answer a whole quiz, rightly or wrongly, then ask for the correction."""
    quiz = parse_quiz(course.text(course.lesson(slug)))
    for question in quiz.questions:
        wrong = next(letter for letter, _ in question.options if letter != question.answer)
        app.radio(key=f"{slug}-{question.number}").set_value(question.answer if right else wrong)
    app.run()
    app.button(key="corriger").click().run()
    assert not app.exception
    return quiz


def test_the_correction_waits_for_every_answer() -> None:
    """A quiz half answered cannot be marked."""
    app = _open("quiz-partie-3")
    assert app.button(key="corriger").disabled


def test_a_perfect_quiz_validates_its_part(course: Course) -> None:
    """Ten right answers: the score, and the quiz ticked in the menu."""
    app = _open("quiz-partie-1")
    quiz = _answer_every_question(app, course, "quiz-partie-1", right=True)
    total = len(quiz.questions)
    assert app.metric[0].value == f"{total} / {total}"
    position = [lesson.slug for lesson in course.lessons].index("quiz-partie-1") + 1
    assert _menu(app)[position].startswith("✓")


def test_a_failed_quiz_explains_every_answer(course: Course) -> None:
    """No right answer: the advice of the quiz, and the right answer to each question."""
    app = _open("quiz-partie-2")
    quiz = _answer_every_question(app, course, "quiz-partie-2", right=False)
    assert app.metric[0].value == f"0 / {len(quiz.questions)}"
    assert len(app.error) == len(quiz.questions)
    assert any(quiz.advice in warning.value for warning in app.warning)

    app.button(key="recommencer").click().run()
    assert app.button(key="corriger").disabled


def test_the_glossary_can_be_searched() -> None:
    """A word narrows the glossary down to the terms that mention it."""
    app = _open("glossaire")
    everything = len(app.dataframe[0].value)
    app.text_input[0].set_value("embargo").run()
    found = app.dataframe[0].value
    assert 0 < len(found) < everything
    assert "Embargo" in set(found["terme"])
