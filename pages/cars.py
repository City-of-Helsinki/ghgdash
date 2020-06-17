import dash_html_components as html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from flask_babel import lazy_gettext as _

from variables import set_variable, get_variable
from components.stickybar import StickyBar
from components.graphs import PredictionFigure
from components.card_description import CardDescription
from components.cards import GraphCard, ConnectedCardGrid
from .base import Page

from calc.transportation.cars import predict_cars_emissions
from utils.colors import GHG_MAIN_SECTOR_COLORS, ENGINE_TYPE_COLORS

CARS_GOAL = 119  # kt CO2e


ENGINE_TYPES = {
    'electric': dict(name=_('Electric'), color=ENGINE_TYPE_COLORS['BEV']),
    'PHEV (gasoline)': dict(name=_('PHEV'), color=ENGINE_TYPE_COLORS['PHEV']),
    'gasoline': dict(name=_('Gasoline'), color=ENGINE_TYPE_COLORS['gasoline']),
    'diesel': dict(name=_('Diesel'), color=ENGINE_TYPE_COLORS['diesel']),
}


class CarEmissionPage(Page):
    id = 'cars'
    path = '/autot'
    emission_sector = ('Transportation', 'Cars')
    name = 'Henkilöautoilun päästöt',

    def get_summary_vars(self):
        return dict(label=self.name, value=self.last_emissions, unit='kt/a')

    def draw_bev_chart(self, df):
        engines = ['electric', 'PHEV (gasoline)', 'gasoline', 'diesel']
        df = df.dropna()[[*engines, 'Forecast']].copy()
        graph = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            legend=True,
            legend_x=0.8,
            y_max=100,
        )

        for col in engines:
            et = ENGINE_TYPES[col]
            df[col] *= 100
            graph.add_series(
                df=df, column_name=col, trace_name=et['name'], historical_color=et['color']
            )

        return graph.get_figure()

    def get_content(self):
        from .modal_share import ModalSharePage
        from .car_fleet import CarFleetPage

        grid = ConnectedCardGrid()
        bev_perc_card = GraphCard(
            id='cars-bev-percentage',
            title='Sähköautojen ajosuoriteosuus',
            title_i18n=dict(en='BEV mileage share'),
            link_to_page=CarFleetPage,
        )
        per_resident_card = GraphCard(
            id='cars-mileage-per-resident',
            title='Ajokilometrit asukasta kohti',
            title_i18n=dict(en='Car mileage per resident'),
            link_to_page=ModalSharePage,
        )
        mileage_card = GraphCard(
            id='cars-total-mileage',
            title='%s ajetut henkilöautokilometrit' % get_variable('municipality_locative'),
            title_i18n=dict(en='%s ajetut henkilöautokilometrit' % get_variable('municipality_name')),
        )
        emission_factor_card = GraphCard(
            id='cars-emission-factor',
            title='Henkilöautojen päästökerroin',
            title_i18n=dict(en='Emission factor of cars'),
        )
        emissions_card = GraphCard(
            id='cars-emissions',
            title='Henkilöautoilun päästöt',
            title_i18n=dict(en='Emissions from car transport'),
        )
        """
        biofuel_card = GraphCard(
            id='cars-biofuel-percentage',
        )
        """
        grid.make_new_row()
        grid.add_card(bev_perc_card)
        # grid.add_card(biofuel_card)
        grid.add_card(per_resident_card)
        grid.make_new_row()
        grid.add_card(emission_factor_card)
        grid.add_card(mileage_card)
        grid.make_new_row()
        grid.add_card(emissions_card)

        bev_perc_card.connect_to(emission_factor_card)
        # biofuel_card.connect_to(emission_factor_card)
        emission_factor_card.connect_to(emissions_card)

        per_resident_card.connect_to(mileage_card)
        mileage_card.connect_to(emissions_card)

        return grid.render()

    def refresh_graph_cards(self):
        df = predict_cars_emissions()
        df['Mileage'] /= 1000000

        bev_chart = self.draw_bev_chart(df)

        """
        graph = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            title='Biopolttoaineiden osuus myydyissä polttoaineissa',
        )
        graph.add_series(
            df=df, column_name='electric', trace_name='Bion osuus'
        )
        biofuel_chart = graph.get_figure()
        """

        graph = PredictionFigure(
            sector_name='Transportation',
            unit_name='km/as.',
        )
        graph.add_series(
            df=df, column_name='PerResident', trace_name='Suorite/as.',
        )
        per_resident_chart = graph.get_figure()

        # Total mileage
        graph = PredictionFigure(
            sector_name='Transportation',
            unit_name='milj. km',
            fill=True,
        )
        graph.add_series(
            df=df, column_name='Mileage', trace_name='Ajosuorite',
        )
        mileage_chart = graph.get_figure()

        # Total emissions
        graph = PredictionFigure(
            sector_name='Transportation',
            unit_name='g/km',
        )
        graph.add_series(
            df=df, column_name='EmissionFactor', trace_name='Päästökerroin',
        )
        emission_factor_chart = graph.get_figure()

        # Total emissions
        graph = PredictionFigure(
            sector_name='Transportation',
            unit_name='kt (CO₂e.)',
            fill=True,
        )
        graph.add_series(
            df=df, column_name='Emissions', trace_name='Päästöt',
        )
        emissions_chart = graph.get_figure()

        cd = CardDescription()
        first_forecast = df[df.Forecast].iloc[0]
        last_forecast = df[df.Forecast].iloc[-1]
        last_history = df[~df.Forecast].iloc[-1]

        mileage_change = ((last_forecast.PerResident / last_history.PerResident) - 1) * 100
        cd.set_values(
            bev_percentage=last_forecast.electric * 100,
            phev_percentage=last_forecast['PHEV (gasoline)'] * 100,
            bev_mileage=last_forecast.Mileage * last_forecast.electric,
            phev_mileage=last_forecast.Mileage * last_forecast['PHEV (gasoline)'],
            per_resident_adjustment=mileage_change,
            target_population=last_forecast.Population,
            urban_mileage=last_forecast.UrbanPerResident,
            highway_mileage=last_forecast.HighwaysPerResident,
        )
        bev_desc = cd.render("""
            Skenaariossa polttomoottorihenkilöautot korvautuvat sähköautoilla siten,
            että vuonna {target_year} {municipality_genitive} kaduilla ja teillä
            ajetaan täyssähköautoilla {bev_percentage} % kaikista ajokilometreistä
            ({bev_mileage} milj. km) ja ladattavilla hybridisähköautoilla {phev_percentage}
            % ajokilometreistä ({phev_mileage} milj. km).
        """)
        pr_desc = cd.render("""
            Vuonna {target_year} {municipality_locative} asuu {target_population} ihmistä.
            Skenaariossa ajokilometrit asukasta kohti muuttuvat vuoteen {target_year} mennessä
            {per_resident_adjustment} %. Yksi asukas ajaa keskimäärin {urban_mileage} km kaduilla
            ja {highway_mileage} km maanteillä vuodessa.
        """)

        self.last_emissions = df.iloc[-1].loc['Emissions']
