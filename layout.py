import flask
from flask import request
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State

from utils.perf import PerfCounter
from pages.routing import load_pages, all_pages, page_instance
from pages.base import Page


load_pages()


def page_callback_func(*inputs):
    inputs = list(inputs)
    page_path = inputs.pop()
    page = page_instance(all_pages[page_path])
    return page.handle_callback(inputs)


_all_page_contents = []


def generate_layout():
    global _all_page_contents

    if not flask.has_request_context():
        fixed_contents = _all_page_contents
    else:
        _all_page_contents = None
        fixed_contents = []

    return html.Div(children=[
        dcc.Location(id='url', refresh=False),
        html.Div(id='app-content'),
        *fixed_contents,
    ])


def display_page(current_path, href):
    if current_path is None:
        return [None]

    pc = PerfCounter('Page %s' % current_path)
    pc.display('start')

    if current_path.endswith('/') and len(current_path) > 1:
        current_path = current_path.lstrip('/')

    page_or_class = all_pages.get(current_path)
    if not page_or_class:
        return [html.H2('Sivua ei löydy')]

    if isinstance(page_or_class, Page):
        page = page_or_class
    elif issubclass(page_or_class, Page):
        page = page_or_class()
    else:
        return html.H2('Sisäinen virhe')

    ret = [page.render(), dcc.Store(id=page.make_id('path-store'), data=page.path)]

    pc.display('finished')
    return [ret]


def register_callbacks(app, pages):
    install_callback = app.callback(
        [Output('app-content', 'children')],
        [Input('url', 'pathname'), Input('url', 'href')]
    )
    install_callback(display_page)

    for page in pages:
        # Register the callbacks to Dash
        if hasattr(page, 'get_content'):
            inputs, outputs = page.get_callback_info()
            if not inputs:
                continue
            install_callback = app.callback(outputs, inputs, [State(page.make_id('path-store'), 'data')])
            install_callback(page_callback_func)
            continue

        for callback in page.callbacks:
            install_callback = app.callback(callback.outputs, callback.inputs, callback.state)
            install_callback(callback)


def initialize_app(app):
    from utils.perf import PerfCounter

    app.layout = generate_layout

    page_contents = []

    pc = PerfCounter('pages')
    pc.display('Rendering all')

    # Generate all pages for checking input and output callbacks
    pages = []
    for page in all_pages.values():
        if isinstance(page, Page):
            pass
        elif issubclass(page, Page):
            page = page()
        else:
            raise Exception('Invalid page: %s' % page)

        pc.display(page.path)

        page_contents.append(page.render())
        page_contents.append(dcc.Store(id=page.make_id('path-store')))
        pages.append(page)

    pc.display('done')

    global _all_page_contents
    _all_page_contents = page_contents

    register_callbacks(app, pages)
