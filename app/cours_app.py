"""Course application of nsy-churn: the beginner course, to read and to practise.

    uv run streamlit run app/cours_app.py

The course is written once, in ``docs/cours``, and every lot keeps editing those
Markdown files only. This application reads them as they stand, through
``churn.interface.course``, and adds what a page of Markdown cannot do: a menu
with progress, corrections to unfold, diagrams drawn, quizzes that check the
answers, and a glossary to search.

Progress lives in the browser session and is lost when the page is closed. A
lesson can be linked to directly with ``?lecon=`` followed by its file name
without the extension, for instance ``?lecon=07-evaluer-honnetement``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn.interface.course import (
    PASS_MARK,
    Course,
    Diagram,
    Fold,
    Lesson,
    Prose,
    Quiz,
    lesson_segments,
    load_course,
    mermaid_to_dot,
    parse_quiz,
    score,
)

HOME = "accueil"
GLOSSARY = "glossaire"

#: Query parameter naming the page on screen, so that a lesson can be linked to.
QUERY_KEY = "lecon"

#: Session keys: the page on screen, the lessons finished, the responses of a quiz.
PAGE_KEY = "page"
DONE_KEY = "faits"
RESPONSES_PREFIX = "reponses-"

REPOSITORY_URL = "https://github.com/3318black/nsy-churn"


def _done() -> set[str]:
    """Return the lessons finished during this session."""
    done: set[str] = st.session_state.setdefault(DONE_KEY, set())
    return done


def _go(key: str) -> None:
    """Open a page, from a button."""
    st.session_state[PAGE_KEY] = key


def _toggle(slug: str) -> None:
    """Tick or untick a chapter as finished."""
    _done().symmetric_difference_update({slug})


def _label(course: Course, key: str) -> str:
    """Name a page in the menu, ticked once finished."""
    if key == HOME:
        return "Accueil"
    if key == GLOSSARY:
        return "Glossaire"
    mark = "✓ " if key in _done() else ""
    return f"{mark}{course.lesson(key).short_label}"


def _sidebar(course: Course, keys: list[str]) -> str:
    """Show the progress and the menu, and return the page chosen."""
    st.sidebar.title("Cours nsy-churn")
    lessons = {lesson.slug for lesson in course.lessons}
    finished = len(_done() & lessons)
    st.sidebar.progress(
        finished / len(lessons), text=f"{finished} leçons terminées sur {len(lessons)}"
    )
    if PAGE_KEY not in st.session_state:
        wanted = st.query_params.get(QUERY_KEY, HOME)
        st.session_state[PAGE_KEY] = wanted if wanted in keys else HOME
    page = st.sidebar.radio(
        "Aller à", keys, key=PAGE_KEY, format_func=lambda key: _label(course, key)
    )
    st.sidebar.caption("La progression est gardée tant que la page reste ouverte.")
    st.sidebar.markdown(f"[Le code du projet]({REPOSITORY_URL})")
    return str(page)


def _show_home(course: Course) -> None:
    """The welcome page: who the course is for, how to follow it, and its plan."""
    st.title(course.title)
    st.button(
        "Commencer le cours",
        key="commencer",
        type="primary",
        on_click=_go,
        args=(course.lessons[0].slug,),
    )
    st.markdown(course.welcome)
    st.header("Le plan du cours")
    for part in course.parts:
        st.subheader(f"Partie {part.number}. {part.title}")
        for lesson in part.lessons:
            mark = "✓ " if lesson.slug in _done() else ""
            columns = st.columns([6, 1, 1], vertical_alignment="center")
            columns[0].markdown(f"{mark}{lesson.label}")
            columns[1].caption(f"{lesson.minutes} min")
            columns[2].button(
                "Ouvrir", key=f"ouvrir-{lesson.slug}", on_click=_go, args=(lesson.slug,)
            )


def _show_chapter(course: Course, lesson: Lesson) -> None:
    """A chapter, its correction folded, its diagrams drawn."""
    part = next(part for part in course.parts if part.number == lesson.part)
    st.caption(f"Partie {part.number}. {part.title}")
    for segment in lesson_segments(course.text(lesson)):
        match segment:
            case Prose(text):
                st.markdown(text)
            case Fold(summary, body):
                with st.expander(summary):
                    st.markdown(body)
            case Diagram(source):
                st.graphviz_chart(mermaid_to_dot(source))
    st.divider()
    st.checkbox(
        "J'ai terminé ce chapitre",
        value=lesson.slug in _done(),
        key=f"case-{lesson.slug}",
        on_change=_toggle,
        args=(lesson.slug,),
    )


def _correct(slug: str, quiz: Quiz) -> None:
    """Keep the responses of a quiz, and validate its part when enough are right."""
    responses = {
        question.number: st.session_state.get(f"{slug}-{question.number}")
        for question in quiz.questions
    }
    st.session_state[RESPONSES_PREFIX + slug] = responses
    if score(quiz, responses) >= PASS_MARK:
        _done().add(slug)


def _restart(slug: str, quiz: Quiz) -> None:
    """Forget the responses of a quiz, to take it again."""
    st.session_state.pop(RESPONSES_PREFIX + slug, None)
    for question in quiz.questions:
        st.session_state.pop(f"{slug}-{question.number}", None)


def _show_quiz(course: Course, lesson: Lesson) -> None:
    """A quiz: the questions, then the score and an explanation for each answer."""
    quiz = parse_quiz(course.text(lesson))
    st.title(quiz.title)
    st.caption(quiz.introduction)

    kept = st.session_state.get(RESPONSES_PREFIX + lesson.slug)
    if kept is None:
        answered = 0
        for question in quiz.questions:
            options = dict(question.options)
            choice = st.radio(
                f"**{question.number}. {question.prompt}**",
                list(options),
                index=None,
                key=f"{lesson.slug}-{question.number}",
                format_func=lambda letter, options=options: f"{letter}. {options[letter]}",
            )
            answered += choice is not None
        missing = len(quiz.questions) - answered
        if missing:
            plural = "s" if missing > 1 else ""
            st.caption(f"Encore {missing} question{plural} sans réponse.")
        st.button(
            "Corriger mes réponses",
            key="corriger",
            type="primary",
            disabled=bool(missing),
            on_click=_correct,
            args=(lesson.slug, quiz),
        )
        return

    total = score(quiz, kept)
    st.metric("Votre score", f"{total} / {len(quiz.questions)}")
    if total >= PASS_MARK:
        st.success("Partie validée : le quiz est coché dans le menu.")
    else:
        st.warning(quiz.advice)
    for question in quiz.questions:
        options = dict(question.options)
        right = f"{question.answer}. {options[question.answer]}"
        given = kept.get(question.number)
        st.markdown(f"**{question.number}. {question.prompt}**")
        if given == question.answer:
            st.success(f"Bonne réponse : {right}  \n{question.explanation}")
        else:
            st.error(
                f"Votre réponse : {given}. {options.get(given, '')}  \n"
                f"La bonne réponse : {right}  \n{question.explanation}"
            )
    st.button("Recommencer le quiz", key="recommencer", on_click=_restart, args=(lesson.slug, quiz))


def _show_neighbours(course: Course, lesson: Lesson) -> None:
    """Buttons to the lessons read just before and just after."""
    previous, following = course.neighbours(lesson.slug)
    columns = st.columns(2)
    if previous is not None:
        columns[0].button(
            f"Précédent : {previous.short_label}",
            key="precedent",
            on_click=_go,
            args=(previous.slug,),
        )
    if following is not None:
        columns[1].button(
            f"Suivant : {following.short_label}",
            key="suivant",
            on_click=_go,
            args=(following.slug,),
        )


def _show_glossary(course: Course) -> None:
    """The glossary, searchable by term or by a word of the definition."""
    st.title("Glossaire")
    table = course.glossary()
    query = st.text_input("Chercher un terme ou un mot de sa définition").strip()
    if query:
        found = table["terme"].str.contains(query, case=False, regex=False) | table[
            "definition"
        ].str.contains(query, case=False, regex=False)
        table = table.loc[found]
    st.caption(f"{len(table)} termes")
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "terme": st.column_config.TextColumn("Terme"),
            "definition": st.column_config.TextColumn("Définition", width="large"),
            "chapitres": st.column_config.TextColumn("Chapitre"),
        },
    )


def main() -> None:
    """Render the page chosen in the menu."""
    st.set_page_config(page_title="Cours nsy-churn", page_icon="📘", layout="centered")
    course = load_course()
    keys = [HOME, *(lesson.slug for lesson in course.lessons), GLOSSARY]
    page = _sidebar(course, keys)
    st.query_params[QUERY_KEY] = page

    if page == HOME:
        _show_home(course)
    elif page == GLOSSARY:
        _show_glossary(course)
    else:
        lesson = course.lesson(page)
        if lesson.is_quiz:
            _show_quiz(course, lesson)
        else:
            _show_chapter(course, lesson)
        _show_neighbours(course, lesson)


main()
