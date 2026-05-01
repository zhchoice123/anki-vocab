import json
import logging
import webbrowser
from threading import Timer

from flask import Flask, jsonify, render_template, request

from anki.local_store import LocalStore
from models import ReadingMaterial

logger = logging.getLogger(__name__)

_APP: Flask | None = None
_MATERIAL: ReadingMaterial | None = None
_STORE: LocalStore | None = None


def create_app(material: ReadingMaterial, store: LocalStore) -> Flask:
    """Create and configure the Flask app."""
    global _APP, _MATERIAL, _STORE
    _MATERIAL = material
    _STORE = store
    _APP = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    _register_routes(_APP)
    return _APP


def _register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        assert _MATERIAL is not None
        return render_template("practice.html", material=_MATERIAL)

    @app.route("/api/check", methods=["POST"])
    def check():
        assert _MATERIAL is not None
        payload = request.get_json(silent=True) or {}
        user_answers = payload.get("answers", {})
        results = []
        wrong_targets = set()

        for i, q in enumerate(_MATERIAL.questions):
            key = str(i)
            user = user_answers.get(key, "")
            correct = q.answer.strip().upper()
            is_correct = user.strip().upper() == correct
            results.append({
                "index": i,
                "correct": is_correct,
                "answer": correct,
                "explanation": q.explanation,
                "user_answer": user,
            })
            if not is_correct and q.target_word:
                wrong_targets.add(q.target_word)

        # Record errors for missed target words
        if wrong_targets and _STORE is not None:
            for word in wrong_targets:
                _STORE.record_error(word)
            logger.info("Recorded errors for %d word(s): %s", len(wrong_targets), ", ".join(wrong_targets))

        score = sum(1 for r in results if r["correct"])
        return jsonify({"results": results, "score": score, "total": len(results)})


def run_server(app: Flask, port: int = 8766, open_browser: bool = True) -> None:
    """Start the Flask dev server and optionally open the browser."""
    if open_browser:
        url = f"http://127.0.0.1:{port}"
        Timer(1.0, lambda: webbrowser.open(url)).start()
    logger.info("Starting practice server on http://127.0.0.1:%d", port)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
