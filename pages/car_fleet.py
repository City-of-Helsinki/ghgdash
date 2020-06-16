import pandas as pd

from common.locale import lazy_gettext as _, get_active_locale
from components.cards import ConnectedCardGrid
from components.graphs import PredictionFigure
from components.card_description import CardDescription
from variables import get_variable, override_variable
from calc.transportation.modal_share import predict_passenger_kms, predict_road_mileage
from calc.transportation.parking import predict_parking_fee_impact
from calc.transportation.cars import predict_cars_emissions
from calc.population import predict_population
from calc.transportation.car_fleet import (
    predict_newly_registered_cars, predict_cars_in_use, predict_cars_in_use_by_engine_type
)
from utils.colors import ENGINE_TYPE_COLORS
from .base import Page


class CarFleetPage(Page):
    id = 'car-fleet'
    path = '/car-fleet'
    emission_sector = ('Transportation',)
    name = 'Ajoneuvokanta'

    def make_cards(self):
        self.add_graph_card(
            id='ev-parking-fee-discount',
            title='Sähköautolle myönnetty pysäköintietuus',
            title_i18n=dict(en='Parking fee discount given to EVs'),
            slider=dict(
                min=0,
                max=1000,
                step=50,
                value=get_variable('parking_subsidy_for_evs'),
                marks={x: '%d €' % x for x in range(0, 1001, 100)},
            ),
        )
        self.add_graph_card(
            id='newly-registered-evs',
            title='Ladattavien sähköautojen osuus ensirekisteröidyistä autoista',
            title_i18n=dict(en='Share of pluggable EVs in newly registered cars'),
        )
        self.add_graph_card(
            id='yearly-fleet-turnover',
            title='Autokannan vuosittainen uudistuminen',
            title_i18n=dict(en='Yearly turnover of car fleet'),
        )
        self.add_graph_card(
            id='cars-per-resident',
            title='Liikennekäytössä olevat henkilöautot asukasta kohti',
            title_i18n=dict(en='Cars registered for transportation per resident'),
        )
        self.add_graph_card(
            id='car-fleet',
            title='Liikennekäytössä olevat henkilöautot',
            title_i18n=dict(en='Cars registered for transportation'),
        )

    def get_content(self):
        grid = ConnectedCardGrid()

        grid.make_new_row()
        c1a = self.get_card('ev-parking-fee-discount')
        c1b = self.get_card('cars-per-resident')
        grid.add_card(c1a)
        grid.add_card(c1b)

        grid.make_new_row()
        c2a = self.get_card('newly-registered-evs')
        c2b = self.get_card('yearly-fleet-turnover')
        grid.add_card(c2a)
        grid.add_card(c2b)
        c1a.connect_to(c2a)
        c1b.connect_to(c2b)

        grid.make_new_row()
        c3 = self.get_card('car-fleet')
        grid.add_card(c3)
        c2a.connect_to(c3)
        c2b.connect_to(c3)

        return grid.render()

    def get_summary_vars(self):
        return dict()

    def refresh_graph_cards(self):
        card = self.get_card('ev-parking-fee-discount')
        self.set_variable('parking_subsidy_for_evs', card.get_slider_value())

        df = pd.DataFrame(data=[0.5] * 13, index=range(2010, 2023), columns=['Discount'])
        df['Forecast'] = False
        df['Discount'] *= 100
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('€/year'),
        )
        fig.add_series(df=df, column_name='Discount', trace_name=_('Discount'))
        card.set_figure(fig)

        card = self.get_card('yearly-fleet-turnover')
        df = predict_cars_in_use()
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            smoothing=True,
        )
        df['YearlyTurnover'] *= 100
        fig.add_series(df=df, column_name='YearlyTurnover', trace_name=_('Turnover'))
        card.set_figure(fig)

        card = self.get_card('cars-per-resident')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('cars/1,000 res.'),
            smoothing=True,
        )
        df['CarsPerResident'] *= 1000
        fig.add_series(df=df, column_name='CarsPerResident', trace_name=_('Cars'))
        card.set_figure(fig)

        card = self.get_card('newly-registered-evs')
        df = predict_newly_registered_cars()
        fc = df.pop('Forecast')
        total = df.sum(axis=1)
        df = df.div(total, axis=0)
        df *= 100
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            smoothing=True,
            color_scale=4,
            legend=True,
        )
        for engine_type in ('BEV', 'PHEV', 'gasoline', 'diesel', 'other'):
            fig.add_series(
                df=df, forecast=fc, column_name=engine_type,
                trace_name=_(engine_type), historical_color=ENGINE_TYPE_COLORS[engine_type]
            )
        card.set_figure(fig)

        card = self.get_card('car-fleet')
        df = predict_cars_in_use_by_engine_type()
        df = df.sum(axis=1, level='EngineType')
        df['Forecast'] = True
        fc = df.pop('Forecast')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('cars'),
            fill=True,
            stacked=True,
            legend=True,
        )
        for engine_type in ('BEV', 'PHEV', 'gasoline', 'diesel', 'other'):
            fig.add_series(
                df=df, forecast=fc, column_name=engine_type, trace_name=_(engine_type),
                forecast_color=ENGINE_TYPE_COLORS[engine_type]
            )
        card.set_figure(fig)
