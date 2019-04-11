# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

from collections import OrderedDict

from pages.district_heating import page as district_heating_page
from pages.population import page as population_page
from pages.buildings import page as buildings_page
from pages.emissions import page as emissions_page

from flask_caching import Cache
from flask_session import Session


app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True

server = app.server

cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(server)

sess = Session()
sess.init_app(server)


navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Linkki 1", href="#")),
        dbc.DropdownMenu(
            children=[
                dbc.DropdownMenuItem("More pages", header=True),
                dbc.DropdownMenuItem("Page 2", href="#"),
                dbc.DropdownMenuItem("Page 3", href="#"),
            ],
            nav=True,
            in_navbar=True,
            label="More",
        ),
    ],
    brand="Hiilineutraali Helsinki 2035",
    brand_href="/",
    color="primary",
    dark=True,
    fluid= True,
)

left_nav = dbc.Nav(id='left-nav', vertical='md', pills=True)


app.layout = html.Div([
    # represents the URL bar, doesn't render anything
    dcc.Location(id='url', refresh=False),

    navbar,

    dbc.Row([
        dbc.Col(left_nav, md=2),
        dbc.Col([
            dbc.Container(id='page-content')
        ]),
    ], className='mt-3')
])


routes = OrderedDict([
    ('', emissions_page),
    ('kaukolampo', district_heating_page),
    ('vaesto', population_page),
    ('rakennukset', buildings_page),
])


@app.callback([Output('left-nav', 'children'), Output('page-content', 'children')],
              [Input('url', 'pathname')])
def display_page(current_path):
    if current_path:
        current_path = current_path.strip('/')

    navitems = []
    current_page = None
    for page_path, page in routes.items():
        attr = {}
        if current_path is not None and current_path == page_path:
            attr['active'] = True
            current_page = page
        item = dbc.NavItem(dbc.NavLink(page.name, href='/%s' % page_path, **attr))
        navitems.append(item)

    if current_page is not None:
        page_content = html.Div([
            html.H2(current_page.name),
            current_page.content
        ])
    else:
        page_content = html.H2('Sivua ei löydy')

    return [navitems, page_content]


for page in routes.values():
    # Register the callbacks to Dash
    for callback in page.callbacks:
        wrap_callback = app.callback(callback.output, callback.inputs, callback.state)
        wrap_callback(callback)


if __name__ == '__main__':
    app.run_server(debug=True)
