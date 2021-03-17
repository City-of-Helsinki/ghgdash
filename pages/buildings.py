from common.locale import get_active_locale
import pandas as pd
import dash_bootstrap_components as dbc
import plotly.graph_objs as go

from common.locale import lazy_gettext as _
from calc.buildings import generate_building_floor_area_forecast
from components.graphs import make_layout
from components.cards import GraphCard
from utils.colors import HELSINKI_COLORS
from .base import Page


BUILDING_USES = {
    'Asuinkerrostalot': dict(
        types=['Asuinkerrostalot'], color='brick'),
    'Muut asuinrakennukset': dict(types=['Erilliset pientalot', 'Rivi- tai ketjutalot'], color='metro'),
    'Julkiset palvelurakennukset': dict(
        types=['Liikenteen rakennukset', 'Opetusrakennukset', 'Hoitoalan rakennukset', 'Kokoontumisrakennukset'],
        color='summer'),
    'Liikerakennukset': dict(types=['Liikerakennukset'], color='coat'),
    'Teollisuusrakennukset': dict(types=['Teollisuusrakennukset'], color='fog'),
    'Toimistorakennukset': dict(types=['Toimistorakennukset'], color='gold'),
    'Muut rakennukset': dict(types=['Varastorakennukset', 'Muu tai tuntematon käyttötarkoitus'], color='silver'),
}
BUILDINGS_EN = {
    'Asuinkerrostalot': 'Residential apartment buildings',
    'Muut asuinrakennukset': 'Other residential buildings',
    'Julkiset palvelurakennukset': 'Public service buildings',
    'Liikerakennukset': 'Commercial buildings',
    'Teollisuusrakennukset': 'Industrial buildings',
    'Toimistorakennukset': 'Office buildings',
    'Muut rakennukset': 'Other buildings',
}

for building_name, attrs in BUILDING_USES.items():
    attrs['color'] = HELSINKI_COLORS[attrs['color']]


def generate_buildings_forecast_graph():
    df = generate_building_floor_area_forecast()

    cdf = pd.DataFrame(index=df.index)
    for name, attrs in BUILDING_USES.items():
        cdf[name] = df[attrs['types']].sum(axis=1) / 1000000

    # Sort columns based on the amounts in the last measured year
    last_year = cdf.loc[cdf.index.max()]
    columns = list(last_year.sort_values(ascending=False).index.values)

    traces = []
    lang = get_active_locale()
    for name in columns:
        attrs = BUILDING_USES[name]
        val = df[attrs['types']].sum(axis=1) / 1000000
        label = name
        if lang == 'en':
            label = BUILDINGS_EN[name]
        trace = go.Bar(
            x=df.index,
            y=val,
            name=label,
            marker=dict(color=attrs['color']),
            hoverinfo='name',
            hovertemplate='%{x}: %{y} Mkem²'
        )
        traces.append(trace)

    last_hist_year = df[~df.Forecast].index.max()
    forecast_divider = dict(
        type='line',
        x0=last_hist_year + 0.5,
        x1=last_hist_year + 0.5,
        xref='x',
        y0=0,
        y1=1,
        yref='paper',
        line=dict(dash='dot', color='grey')
    )

    layout = make_layout(
        barmode='stack',
        yaxis=dict(
            title='1 000 000 kem²',
        ),
        xaxis=dict(title=_('Year')),
        title=_('Floor area by building purpose'),
        shapes=[forecast_divider],
        showlegend=True,
        autosize=True,
    )
    return dict(data=traces, layout=layout)


def render_page():
    fig = generate_buildings_forecast_graph()
    ret = dbc.Row([
        dbc.Col([
            GraphCard(id='buildings', graph=dict(figure=fig)).render()
        ], md=8)
    ])

    return ret


page = Page(id='rakennukset', path='/rakennukset', name=_('Buildings'), content=render_page)


if __name__ == '__main__':
    generate_buildings_forecast_graph()
