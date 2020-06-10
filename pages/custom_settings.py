import json
import flask
from flask_babel import gettext as _
from flask import session

from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import dash_html_components as html

from .base import Page


def generate_custom_settings_list():
    if not flask.has_request_context():
        return html.Pre()

    customized_variables = {key: val for key, val in session.items() if not key.startswith('_')}
    var_str = json.dumps(customized_variables, ensure_ascii=False, indent=4)
    return html.Pre(var_str)


def custom_settings_content():
    out = []
    out.append(dbc.Row([
        dbc.Col([generate_custom_settings_list()], id='custom-settings-list'),
    ]))
    out.append(dbc.Button(_('Clear'), id='custom-settings-clear-button'))

    return html.Div(out)


page = Page(id='custom-settings', name='Omat asetukset', content=custom_settings_content, path='/omat-asetukset')


@page.callback(
    outputs=[Output('custom-settings-list', 'children')],
    inputs=[Input('custom-settings-clear-button', 'n_clicks')]
)
def custom_settings_clear(n_clicks):
    if n_clicks is not None:
        session.clear()
    return [generate_custom_settings_list()]
