import flask
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from common.locale import get_active_locale
from components.cards import GraphCard
from components.stickybar import StickyBar

from dash.dependencies import Output, Input
from flask import session

from calc.emissions import SECTORS
from variables import get_variable, set_variable


class Page:
    id: str
    name: str
    path: str
    emission_sector: tuple = None

    def __init__(self, id=None, name=None, content=None, path=None, emission_sector=None):
        if id:
            self.id = id
        if name:
            self.name = name
        if content:
            self.content = content
        if path:
            self.path = path
        if emission_sector:
            assert isinstance(emission_sector, (tuple, list, str))
            self.emission_sector = emission_sector
        if self.emission_sector and isinstance(self.emission_sector, str):
            self.emission_sector = (self.emission_sector,)
        if self.emission_sector:
            subsectors = SECTORS
            sector = None
            for sector_name in self.emission_sector:
                sector = subsectors[sector_name]
                subsectors = sector.get('subsectors', {})
            assert sector is not None
            self.sector_metadata = sector
            if not hasattr(self, 'name') or not self.name:
                self.name = sector['name']

        self.callbacks = []
        self.graph_cards = {}

    def get_variable(self, name):
        return get_variable(name)

    def set_variable(self, name, val):
        return set_variable(name, val)

    def get_callback_info(self):
        outputs = []
        inputs = []
        for card_id, card in self.graph_cards.items():
            if card.slider:
                inputs.append(Input(card_id + '-slider', 'value'))
            outputs.append(Output(card_id + '-description', 'children'))
            outputs.append(Output(card_id + '-graph', 'figure'))

        outputs.append(Output(self.make_id('left-nav'), 'children'))
        outputs.append(Output(self.make_id('summary-bar'), 'children'))

        return (inputs, outputs)

    def handle_callback(self, inputs):
        self.make_cards()

        slider_cards = []
        output_cards = []
        for card_id, card in self.graph_cards.items():
            if card.slider:
                slider_cards.append(card)
            output_cards.append(card)

        for card, val in zip(slider_cards, inputs):
            card.set_slider_value(val)

        self.refresh_graph_cards()
        outputs = []
        for card in output_cards:
            desc = card.get_description()
            if desc is not None:
                desc = dbc.Col(desc, style=dict(minHeight='8rem'))
            outputs.append(desc)
            fig = card.get_figure()
            outputs.append(fig)

        outputs.append(self._make_emission_nav())
        outputs.append(self._make_summary_bar())

        return outputs

    def __str__(self):
        return self.name

    def make_id(self, name):
        return '%s-%s' % (self.id, name)

    def _make_emission_nav(self):
        from components.emission_nav import make_emission_nav
        return make_emission_nav(self)

    def _make_navbar(self):
        if flask.has_request_context():
            custom_setting_count = len([k for k in session.keys() if not k.startswith('_')])
        else:
            custom_setting_count = 0
        badge_el = None
        if custom_setting_count:
            badge_el = dbc.Badge(f'{custom_setting_count} ', className='badge-danger')

        els = [
            dbc.DropdownMenu(
                [
                    dbc.DropdownMenuItem("Väestö", href='/vaesto'),
                    dbc.DropdownMenuItem("Rakennukset", href='/rakennukset')
                ],
                nav=True,
                in_navbar=True,
                label="Oletukset",
                # id="dropdown-nav"
            ),
            dbc.NavItem(dbc.NavLink(href='/omat-asetukset', children=[
                "Omat asetukset",
                badge_el,
            ])),
            dbc.NavItem(html.Span(html.I(className='language-icon')), className='nav-link pr-0'),
            dbc.DropdownMenu(
                [
                    dbc.DropdownMenuItem("Suomi", href='/language/fi', external_link=True),
                    dbc.DropdownMenuItem("English", href='/language/en', external_link=True)
                ],
                nav=True,
                in_navbar=True,
                label=get_active_locale().upper(),
                right=True,
            ),
        ]
        return dbc.NavbarSimple(
            brand="Päästöskenaario %s" % self.get_variable('target_year'),
            brand_href="/",
            color="primary",
            dark=True,
            fluid=True,
            children=els
        )

    def _make_summary_bar(self):
        bar = StickyBar(current_page=self, **self.get_summary_vars())
        return bar.render()

    def _make_page_contents(self):
        if hasattr(self, 'get_content'):
            # Class-based (new-style) page
            content = self.get_content()
        else:
            if callable(self.content):
                content = self.content()
            else:
                content = self.content

        page_content = html.Div([
            html.H2(self.name), content
        ])

        inputs, _ = self.get_callback_info()
        if not inputs and hasattr(self, 'get_summary_vars'):
            summary_el = self._make_summary_bar()
        else:
            summary_el = None

        ret = html.Div([
            # represents the URL bar, doesn't render anything
            self._make_navbar(),
            dbc.Container(
                dbc.Row([
                    dbc.Col(id=self.make_id('left-nav'), md=2, children=self._make_emission_nav()),
                    dbc.Col(md=10, children=page_content),
                    html.Div(id=self.make_id('summary-bar'), children=summary_el),
                ]),
                className="app-content",
                fluid=True
            )
        ])
        return ret

    def make_cards(self):
        pass

    def render(self):
        self.make_cards()
        return html.Div(self._make_page_contents(), id=self.make_id('page-content'))

    def add_graph_card(self, id, **kwargs):
        card_id = self.make_id(id)
        assert card_id not in self.graph_cards
        card = GraphCard(id=card_id, **kwargs)
        self.graph_cards[card_id] = card
        return card

    def get_card(self, id):
        return self.graph_cards[self.make_id(id)]

    def set_graph_figure(self, card_id, figure):
        self.graph_cards[card_id].set_grap

    def callback(self, inputs, outputs):
        assert isinstance(inputs, list)
        assert isinstance(outputs, list)

        def wrap_func(func):
            def call_func(*args):
                ret = func(*args)
                assert isinstance(ret, list)
                if self.emission_sector:
                    ret += [self._make_emission_nav()]
                return ret

            self.callbacks.append(call_func)

            extra_outputs = []
            if self.emission_sector:
                extra_outputs += [Output(self.make_id('left-nav'), 'children')]

            call_func.outputs = outputs + extra_outputs
            call_func.inputs = inputs
            call_func.state = []

            return call_func

        return wrap_func
