import pandas as pd

from common.locale import lazy_gettext as _
from components.cards import ConnectedCardGrid
from components.graphs import PredictionFigure
from components.card_description import CardDescription
from variables import get_variable
from calc.transportation.modal_share import predict_passenger_kms, predict_road_mileage
from calc.transportation.parking import predict_parking_fee_impact
from .base import Page


MAX_PARKING_FEE_INCREASE_PERC = 400


class ModalSharePage(Page):
    id = 'transportation-modal-share'
    path = '/modal-share'
    emission_sector = ('Transportation',)
    name = 'Kulkumuoto-osuudet'

    def make_cards(self):
        self.add_graph_card(
            id='parking-fee',
            title='Pysäköintimaksu',
            title_i18n=dict(en='Parking fee increase'),
            slider=dict(
                min=0,
                max=MAX_PARKING_FEE_INCREASE_PERC * 10,
                step=10 * 10,
                value=get_variable('parking_fee_increase') * 10,
                marks={x: '+%d %%' % (x / 10) for x in range(0, (MAX_PARKING_FEE_INCREASE_PERC * 10) + 1, 500)},
            ),
        )

        self.add_graph_card(
            id='modal-share-car',
            title='Henkilöautoilun osuus matkustajakilometreistä',
            title_i18n=dict(en='Passenger mileage share of cars'),
        )

        self.add_graph_card(
            id='modal-shares-rest',
            title='Muiden kulkumuoto-osuudet matkustajakilometreistä',
            title_i18n=dict(en='Shares of passenger mileage for other modes'),
        )

        self.add_graph_card(
            id='number-of-passenger-kms',
            title='Matkustajakilometrien määrä asukasta kohti päivässä',
            title_i18n=dict(en='Number of passenger kms per resident per year'),
        )

        self.add_graph_card(
            id='car-mileage-per-resident',
            title='Henkilöautoilla ajetut kilometrit asukasta kohti vuodessa',
            title_i18n=dict(en='Mileage driven with cars per resident per year'),
        )

    def get_content(self):
        grid = ConnectedCardGrid()

        grid.make_new_row()
        c1a = self.get_card('parking-fee')
        grid.add_card(c1a)

        grid.make_new_row()
        c2a = self.get_card('modal-share-car')
        grid.add_card(c2a)
        c2b = self.get_card('modal-shares-rest')
        grid.add_card(c2b)
        c2c = self.get_card('number-of-passenger-kms')
        grid.add_card(c2c)
        c1a.connect_to(c2a)
        c1a.connect_to(c2b)

        grid.make_new_row()
        c3 = self.get_card('car-mileage-per-resident')
        grid.add_card(c3)
        c2a.connect_to(c3)
        c2c.connect_to(c3)

        return grid.render()

    def get_summary_vars(self):
        return dict()

    def _refresh_parking_fee_card(self):
        pcard = self.get_card('parking-fee')
        self.set_variable('parking_fee_increase', pcard.get_slider_value() // 10)

        df = predict_parking_fee_impact()

        last_hist_year = df[~df.Forecast].index.max()
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='€',
            smoothing=True,
            # y_min=df['Fees'].min(),
            y_max=df.loc[last_hist_year]['Fees'] * (1 + MAX_PARKING_FEE_INCREASE_PERC / 100)
        )
        fig.add_series(df=df, column_name='Fees', trace_name='Pysäköinnin hinta')
        pcard.set_figure(fig)

    def _refresh_trip_cards(self):
        df = predict_passenger_kms()

        card = self.get_card('number-of-passenger-kms')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='km',
        )
        fig.add_series(df, column_name='KmsPerResident', trace_name=_('passenger kms (p.c.)'))
        card.set_figure(fig)
        df.pop('KmsPerResident')

        total = df.sum(axis=1)

        fc = df.pop('Forecast')
        df = df.div(total, axis=0)
        df *= 100

        df['Other'] += df.pop('Taxi')
        df['Rail'] = df.pop('Metro') + df.pop('Tram') + df.pop('Train')

        ccard = self.get_card('modal-share-car')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            smoothing=True,
        )
        fig.add_series(df=df, forecast=fc, column_name='Car', trace_name='Henkilöautot')
        ccard.set_figure(fig)
        df.pop('Car')

        mcard = self.get_card('modal-shares-rest')
        color_scale = len(df.columns)
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            smoothing=True,
            legend=True,
            color_scale=color_scale,
        )
        last_hist_year = fc[~fc].index.max()
        columns = list(df.loc[last_hist_year].sort_values(ascending=False).index)
        for idx, col in enumerate(columns):
            fig.add_series(df=df, forecast=fc, column_name=col, trace_name=col, color_idx=idx)

        mcard.set_figure(fig)

    def _refresh_mileage_card(self):
        card = self.get_card('car-mileage-per-resident')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='milj. km',
            smoothing=True,
            color_scale=2,
            legend=True,
        )
        mdf = predict_road_mileage()
        df = pd.DataFrame(mdf.pop('Forecast'))
        for vehicle, road in list(mdf.columns):
            if vehicle == 'Cars':
                df[road] = mdf[(vehicle, road)] / 1000000

        fig.add_series(df=df, column_name='Urban', trace_name='Katusuorite', color_idx=0)
        fig.add_series(df=df, column_name='Highways', trace_name='Maantiesuorite', color_idx=1)
        card.set_figure(fig)

    def refresh_graph_cards(self):
        self._refresh_parking_fee_card()
        self._refresh_trip_cards()
        self._refresh_mileage_card()
