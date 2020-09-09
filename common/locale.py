import flask
from flask import request, session
from flask_babel import Babel, gettext, lazy_gettext  # noqa
from flask_babel.speaklater import LazyString
from plotly import utils as plotly_utils


class JSONEncoder(plotly_utils.PlotlyJSONEncoder):
    def default(self, o):
        if isinstance(o, LazyString):
            return str(o)

        return super().default(o)


def get_active_locale():
    if not flask.has_request_context():
        return 'fi'

    language = session.get('_language')
    if language:
        return language
    return request.accept_languages.best_match(['fi', 'en'])


def change_language(lang):
    if lang in ('fi', 'en'):
        session['_language'] = lang
    return flask.redirect('/')


def init_locale(server):
    babel = Babel(default_locale='fi')
    babel.init_app(server)

    server.add_url_rule('/language/<lang>', 'change_language', view_func=change_language)

    # Monkeypatch Plotly to accept lazystrings
    plotly_utils.PlotlyJSONEncoder = JSONEncoder
    babel.localeselector(get_active_locale)
