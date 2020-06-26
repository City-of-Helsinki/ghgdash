import pandas as pd
import dash_bootstrap_components as dbc
import dash_html_components as html

from components.cards import GraphCard
from common.locale import lazy_gettext as _, get_active_locale
from components.graphs import PredictionFigure
from calc.emissions import predict_emissions, SECTORS
from utils.colors import generate_color_scale
from pages.routing import get_page_for_emission_sector
from .base import Page


class MainSectorPage(Page):
    def make_sector_fig(self, df, name, metadata, base_color):
        lang = get_active_locale()
        fig = PredictionFigure(
            sector_name=name,
            unit_name='kt',
            title=metadata.get('name_%s' % lang, metadata['name']),
            smoothing=True,
            # allow_nonconsecutive_years=True,
            fill=True,
            stacked=True,
        )
        if len(df.columns) == 2:
            fig.add_series(df=df, trace_name=_('Emissions'), column_name='', historical_color=base_color)
        else:
            fig.legend = True
            fig.legend_x = 0.8
            column_names = list(df.columns)
            column_names.remove('Forecast')
            colors = generate_color_scale(base_color, len(column_names))
            for idx, col_name in enumerate(column_names):
                subsector = metadata['subsectors'][col_name]
                fig.add_series(
                    df=df, trace_name=subsector.get('name_%s' % lang, metadata['name']), column_name=col_name,
                    historical_color=colors[idx]
                )
        return fig.get_figure()

    def get_content(self):
        lang = get_active_locale()
        main_sector_name = self.emission_sector[0]
        main_sector_metadata = SECTORS[main_sector_name]

        cols = []

        edf = predict_emissions().dropna(axis=1, how='all')
        forecast = edf.pop('Forecast')
        edf = edf[main_sector_name]

        subsectors = main_sector_metadata['subsectors']
        colors = generate_color_scale(main_sector_metadata['color'], len(subsectors))

        graph = PredictionFigure(
            sector_name=main_sector_name,
            unit_name='kt',
            title=_('Total emissions'),
            smoothing=True,
            fill=True,
            stacked=True,
            legend=True,
            legend_x=0.8
        )

        for idx, (sector_name, sector_metadata) in enumerate(subsectors.items()):
            df = pd.DataFrame(edf[sector_name])
            df['Forecast'] = forecast

            fig = self.make_sector_fig(df, sector_name, sector_metadata, colors[idx])
            sector_page = get_page_for_emission_sector(main_sector_name, sector_name)
            card = GraphCard(
                id='emissions-%s-%s' % (main_sector_name, sector_name),
                graph=dict(figure=fig),
                link_to_page=sector_page
            )
            cols.append(dbc.Col(card.render(), md=6))

            # Add the summed sector to the all emissions graph
            df = df.drop(columns=['Forecast'])
            s = df.sum(axis=1)
            s.name = 'Emissions'
            df = pd.DataFrame(s)
            df['Forecast'] = forecast
            graph.add_series(
                df=df, trace_name=sector_metadata.get('name_%s' % lang, sector_metadata['name']), column_name='Emissions',
                historical_color=colors[idx]
            )

        self.total_emissions = edf.iloc[-1].sum()

        card = GraphCard(
            id='%s-emissions-total' % main_sector_name,
            graph=dict(figure=graph.get_figure())
        )

        return html.Div([
            dbc.Row(dbc.Col(card.render())),
            dbc.Row(cols),
        ])

    def get_summary_vars(self):
        return dict(label=self.emission_name, value=self.total_emissions, unit='kt')
