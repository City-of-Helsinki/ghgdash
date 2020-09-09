from calc.transportation.cars import predict_cars_emissions
from components.card_description import CardDescription
from components.cards import ConnectedCardGrid
from components.graphs import PredictionFigure
from flask_babel import lazy_gettext as _
from utils.colors import ENGINE_TYPE_COLORS
from variables import get_variable

from .base import Page

ENGINE_TYPES = {
    'electric': dict(name=_('BEV'), color=ENGINE_TYPE_COLORS['BEV']),
    'BEV': dict(name=_('BEV'), color=ENGINE_TYPE_COLORS['BEV']),
    'PHEV (gasoline)': dict(name=_('PHEV'), color=ENGINE_TYPE_COLORS['PHEV']),
    'PHEV': dict(name=_('PHEV'), color=ENGINE_TYPE_COLORS['PHEV']),
    'gasoline': dict(name=_('Gasoline'), color=ENGINE_TYPE_COLORS['gasoline']),
    'diesel': dict(name=_('Diesel'), color=ENGINE_TYPE_COLORS['diesel']),
    'other': dict(name=_('Other'), color=ENGINE_TYPE_COLORS['other']),
}


class CarEmissionPage(Page):
    id = 'cars'
    path = '/cars'
    emission_sector = ('Transportation', 'Cars')
    name = _('Emissions from cars')
    is_main_page = True

    def get_summary_vars(self):
        return dict(label=self.name, value=self.last_emissions, unit='kt/a')

    def draw_bev_chart(self, df):
        engines = ['electric', 'PHEV (gasoline)', 'gasoline', 'diesel']
        df = df.dropna()[[*engines, 'Forecast']].copy()
        df.loc[df.index == df.index.min(), 'Forecast'] = False
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            legend=True,
            legend_x=0.8,
            y_max=100,
        )

        for col in engines:
            et = ENGINE_TYPES[col]
            df[col] *= 100
            fig.add_series(
                df=df, column_name=col, trace_name=et['name'], historical_color=et['color']
            )

        return fig

    def make_cards(self):
        from .modal_share import ModalSharePage
        from .car_fleet import CarFleetPage

        self.add_graph_card(
            id='bev-percentage',
            title='Sähköautojen ajosuoriteosuus',
            title_i18n=dict(en='BEV mileage share'),
            link_to_page=CarFleetPage,
        )
        self.add_graph_card(
            id='mileage-per-resident',
            title='Ajokilometrit asukasta kohti',
            title_i18n=dict(en='Car mileage per resident'),
            link_to_page=ModalSharePage,
        )
        self.add_graph_card(
            id='total-mileage',
            title='%s ajetut henkilöautokilometrit' % get_variable('municipality_locative'),
            title_i18n=dict(en='Car mileage driven in %s' % get_variable('municipality_name')),
        )
        self.add_graph_card(
            id='emission-factor',
            title='Henkilöautojen päästökerroin',
            title_i18n=dict(en='Emission factor of cars'),
        )
        self.add_graph_card(
            id='emissions',
            title='Henkilöautoilun päästöt',
            title_i18n=dict(en='Emissions from car transport'),
        )

    def get_content(self):
        grid = ConnectedCardGrid()
        """
        biofuel_card = GraphCard(
            id='cars-biofuel-percentage',
        )
        """
        grid.make_new_row()
        c1a = self.get_card('bev-percentage')
        c1b = self.get_card('mileage-per-resident')
        grid.add_card(c1a)
        grid.add_card(c1b)

        grid.make_new_row()
        c2a = self.get_card('emission-factor')
        c2b = self.get_card('total-mileage')
        grid.add_card(c2a)
        grid.add_card(c2b)
        c1a.connect_to(c2a)
        c1b.connect_to(c2b)

        grid.make_new_row()
        c3 = self.get_card('emissions')
        grid.add_card(c3)
        c2a.connect_to(c3)
        c2b.connect_to(c3)

        return grid.render()

    def refresh_graph_cards(self):
        df = predict_cars_emissions()
        df['Mileage'] /= 1000000

        fig = self.draw_bev_chart(df)
        bev_card = self.get_card('bev-percentage')
        bev_card.set_figure(fig)

        mpr_card = self.get_card('mileage-per-resident')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='km/as.',
        )
        fig.add_series(
            df=df, column_name='PerResident', trace_name=_('Vehicle mileage/res.'),
        )
        mpr_card.set_figure(fig)

        card = self.get_card('emission-factor')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='g/km',
        )
        fig.add_series(
            df=df, column_name='EmissionFactor', trace_name=_('Emission factor'),
        )
        card.set_figure(fig)

        card = self.get_card('total-mileage')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='milj. km',
            fill=True,
        )
        fig.add_series(
            df=df, column_name='Mileage', trace_name=_('Vehicle mileage'),
        )
        card.set_figure(fig)

        card = self.get_card('emissions')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='kt (CO₂e.)',
            fill=True,
        )
        fig.add_series(
            df=df, column_name='Emissions', trace_name=_('Emissions'),
        )
        card.set_figure(fig)

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

        cd = CardDescription()
        last_forecast = df[df.Forecast].iloc[-1]
        last_history = df[~df.Forecast].iloc[-1]
        self.last_emissions = df.iloc[-1].loc['Emissions']

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

        bev_card.set_description(cd.render("""
            Skenaariossa polttomoottorihenkilöautot korvautuvat sähköautoilla siten,
            että vuonna {target_year} {municipality_genitive} kaduilla ja teillä
            ajetaan täyssähköautoilla {bev_percentage} % kaikista ajokilometreistä
            ({bev_mileage} milj. km) ja ladattavilla hybridisähköautoilla {phev_percentage}
            % ajokilometreistä ({phev_mileage} milj. km).
        """))

        mpr_card.set_description(cd.render("""
            Vuonna {target_year} {municipality_locative} asuu {target_population} ihmistä.
            Skenaariossa ajokilometrit asukasta kohti muuttuvat vuoteen {target_year} mennessä
            {per_resident_adjustment} %. Yksi asukas ajaa keskimäärin {urban_mileage} km kaduilla
            ja {highway_mileage} km maanteillä vuodessa.
        """))
