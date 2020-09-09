import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from dash.dependencies import Input, Output
from flask_babel import gettext
from flask_babel import lazy_gettext as _

from calc.population import predict_population
from components.card_description import CardDescription
from components.cards import GraphCard
from components.graphs import make_layout
from components.stickybar import StickyBar
from variables import get_variable, set_variable

from .base import Page


def generate_population_forecast_graph(pop_df):
    hist_df = pop_df.query('~Forecast')
    hovertemplate = '%{x}: %{y:.0f} 000'
    hist = go.Scatter(
        x=hist_df.index,
        y=hist_df.Population / 1000,
        hovertemplate=hovertemplate,
        mode='lines',
        name=gettext('Population'),
        line=dict(
            color='#9fc9eb',
        )
    )

    forecast_df = pop_df.query('Forecast')
    forecast = dict(
        type='scatter',
        x=forecast_df.index,
        y=forecast_df.Population / 1000,
        hovertemplate=hovertemplate,
        mode='lines',
        name=gettext('Population (pred.)'),
        line=dict(
            color='#9fc9eb',
            dash='dash'
        )
    )
    layout = make_layout(
        yaxis=dict(
            title=gettext('1,000 residents'),
            zeroline=True,
        ),
        showlegend=False,
        title=gettext('Population of Helsinki')
    )

    fig = go.Figure(data=[hist, forecast], layout=layout)
    return fig


def render_page():
    slider = dict(
        min=-20,
        max=20,
        step=5,
        value=get_variable('population_forecast_correction'),
        marks={x: '%d %%' % x for x in range(-20, 20 + 1, 5)},
    )
    card = GraphCard(id='population', slider=slider).render()
    return html.Div([
        dbc.Row(dbc.Col(card, md=6)),
        html.Div(id='population-summary-bar-container'),
    ])


page = Page(
    id='population',
    name=_('Population'),
    content=render_page,
    path='/vaesto'
)


@page.callback(
    inputs=[
        Input('population-slider', 'value')
    ],
    outputs=[
        Output('population-graph', 'figure'),
        Output('population-description', 'children'),
        Output('population-summary-bar-container', 'children')
    ],
)
def population_callback(value):
    set_variable('population_forecast_correction', value)
    pop_df = predict_population()
    target_year = get_variable('target_year')
    pop_in_target_year = pop_df.loc[target_year].Population
    last_hist = pop_df[~pop_df.Forecast].iloc[-1]
    fig = generate_population_forecast_graph(pop_df)
    cd = CardDescription()
    cd.set_values(
        pop_in_target_year=pop_in_target_year,
        pop_adj=get_variable('population_forecast_correction'),
        pop_diff=(1 - last_hist.Population / pop_in_target_year) * 100,
    )
    cd.set_variables(
        last_year=last_hist.name
    )
    pop_desc = cd.render("""
        The population of {municipality} in the year {target_year} will be {pop_in_target_year}.
        The difference compared to the official population forecast is {pop_adj:noround} %.
        Population change compared to {last_year} is {pop_diff} %.
    """)
    # pop_desc = cd.render("""
    #    {municipality_genitive} väkiluku vuonna {target_year} on {pop_in_target_year}.
    #    Muutos viralliseen väestöennusteeseen on {pop_adj:noround} %.
    #    Väkiluvun muutos vuoteen {last_year} verrattuna on {pop_diff} %.
    #""")

    bar = StickyBar(
        label=gettext('Population in %(municipality)s') % dict(municipality=get_variable('municipality_name')),
        value=pop_in_target_year,
        unit=gettext('residents'),
    )

    # return fig, pop_in_target_year.round()
    return [fig, dbc.Col(pop_desc), bar.render()]
