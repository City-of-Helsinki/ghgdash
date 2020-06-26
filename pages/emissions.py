import pandas as pd
import dash_bootstrap_components as dbc
import dash_html_components as html

from common.locale import lazy_gettext as _, get_active_locale
from components.cards import GraphCard
from components.graphs import PredictionFigure
from components.stickybar import StickyBar
from variables import get_variable
from calc.emissions import predict_emissions, SECTORS
from utils.colors import generate_color_scale
from pages.routing import get_page_for_emission_sector
from .base import Page


def make_sector_fig(df, name, metadata):
    language = get_active_locale()
    title = metadata.get('name_%s' % language, metadata['name'])
    fig = PredictionFigure(
        sector_name=name,
        unit_name='kt',
        title=title,
        smoothing=True,
        # allow_nonconsecutive_years=True,
        fill=True,
        stacked=True,
    )
    if len(df.columns) == 2:
        fig.add_series(df=df, trace_name=_('Emissions'), column_name='')
    else:
        fig.legend = True
        fig.legend_x = 0.8
        column_names = list(df.columns)
        column_names.remove('Forecast')
        colors = generate_color_scale(metadata['color'], len(column_names))
        for idx, col_name in enumerate(column_names):
            subsector = metadata['subsectors'][col_name]
            title = subsector.get('name_%s' % language, subsector['name'])
            fig.add_series(
                df=df, trace_name=title, column_name=col_name,
                historical_color=colors[idx]
            )
    return fig.get_figure()


def render_page():
    language = get_active_locale()
    cols = []
    edf = predict_emissions().dropna(axis=1, how='all')
    forecast = edf.pop('Forecast')
    graph = PredictionFigure(
        sector_name=None,
        unit_name='kt',
        title=_('Total emissions'),
        smoothing=True,
        fill=True,
        stacked=True,
        legend=True,
        legend_x=0.8
    )
    for sector_name, sector_metadata in SECTORS.items():
        df = pd.DataFrame(edf[sector_name])
        df['Forecast'] = forecast

        fig = make_sector_fig(df, sector_name, sector_metadata)
        sector_page = get_page_for_emission_sector(sector_name, None)
        card = GraphCard(id='emissions-%s' % sector_name, graph=dict(figure=fig), link_to_page=sector_page)
        cols.append(dbc.Col(card.render(), md=6))

        # Add the summed sector to the all emissions graph
        df = df.drop(columns=['Forecast'])
        s = df.sum(axis=1)
        s.name = 'Emissions'
        df = pd.DataFrame(s)
        df['Forecast'] = forecast
        name = sector_metadata.get('name_%s' % language, sector_metadata['name'])
        graph.add_series(
            df=df, trace_name=name, column_name='Emissions',
            historical_color=sector_metadata['color']
        )

    target_year = get_variable('target_year')
    ref_year = get_variable('ghg_reductions_reference_year')
    perc_off = get_variable('ghg_reductions_percentage_in_target_year')

    last_hist_year = edf.loc[~forecast].index.max()
    last_hist = edf.loc[last_hist_year].sum()
    end_emissions = edf.loc[target_year].sum()
    ref_emissions = edf.loc[ref_year].sum()
    target_emissions = ref_emissions * (1 - perc_off / 100)

    target_year_emissions = edf.loc[target_year].sum()
    sticky = StickyBar(
        label=_('Total emission reductions'),
        goal=last_hist - target_emissions,
        value=last_hist - end_emissions,
        unit='kt',
        below_goal_good=False,
    )

    card = GraphCard(id='emissions-total', graph=dict(figure=graph.get_figure()))

    return html.Div([
        dbc.Row(dbc.Col(card.render())),
        dbc.Row(cols),
        sticky.render()
    ])


page = Page(
    id='emissions',
    name=_('Total GHG emissions'),
    content=render_page,
    path='/',
)


if __name__ == '__main__':
    render_page()
