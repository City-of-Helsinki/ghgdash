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
from .base import Page


MAX_PARKING_FEE_INCREASE_PERC = 400


MODE_TRANSLATIONS = {
    'Rail': dict(fi='Raide'),
    'Bus': dict(fi='Bussit'),
    'Walking': dict(fi='Kävely'),
    'Cycling': dict(fi='Pyöräily'),
}


class ModalSharePage(Page):
    id = 'transportation-modal-share'
    path = '/modal-share'
    emission_sector = ('Transportation',)
    name = 'Kulkumuoto-osuudet'

    def make_cards(self):
        from .car_fleet import CarFleetPage

        self.add_graph_card(
            id='residential-parking-fee',
            title='Asukaspysäköinnin hinta',
            title_i18n=dict(en='Cost of residential parking'),
            slider=dict(
                min=0,
                max=MAX_PARKING_FEE_INCREASE_PERC,
                step=10,
                value=get_variable('residential_parking_fee_increase'),
                marks={x: '+%d %%' % x for x in range(0, (MAX_PARKING_FEE_INCREASE_PERC) + 1, 50)},
            ),
        )

        self.add_graph_card(
            id='cars-affected-by-residential-parking-fee',
            title='Osuus autokannasta, johon asukaspysäköintimaksun korotus kohdistuu',
            title_i18n=dict(en='Share of cars affected by the residential parking fee increase'),
            slider=dict(
                min=0,
                max=100,
                step=5,
                value=get_variable('residential_parking_fee_share_of_cars_impacted'),
                marks={x: '%d %%' % x for x in range(0, 101, 10)},
            ),
        )

        self.add_graph_card(
            id='modal-share-car',
            title='Henkilöautoilun osuus matkustajakilometreistä',
            title_i18n=dict(en='Passenger mileage share of cars'),
        )

        self.add_graph_card(
            id='modal-shares-rest',
            title='Muiden kulkumuotojen osuudet matkustajakilometreistä',
            title_i18n=dict(en='Shares of passenger mileage for other modes'),
        )

        self.add_graph_card(
            id='number-of-passenger-kms',
            title='Matkustajakilometrien määrä asukasta kohti',
            title_i18n=dict(en='Number of passenger kms per resident per year'),
        )

        self.add_graph_card(
            id='car-mileage-per-resident',
            title='Henkilöautoilla ajetut kilometrit asukasta kohti',
            title_i18n=dict(en='Mileage driven with cars per resident'),
        )

        self.add_graph_card(
            id='car-mileage',
            title='Henkilöautoilla ajetut kilometrit',
            title_i18n=dict(en='Mileage driven with cars'),
        )

        self.add_graph_card(
            id='car-emission-factor',
            title='Henkilöautojen päästökerroin',
            title_i18n=dict(en='Emission factor of cars'),
            link_to_page=CarFleetPage,
        )

        self.add_graph_card(
            id='parking-emission-reductions',
            title='Pysäköintimaksun korotuksen päästövaikutukset',
            title_i18n=dict(en='Emission impact of parking fee increase'),
        )

    def get_content(self):
        grid = ConnectedCardGrid()

        grid.make_new_row()
        c1a = self.get_card('residential-parking-fee')
        c1b = self.get_card('cars-affected-by-residential-parking-fee')
        grid.add_card(c1a)
        grid.add_card(c1b)

        grid.make_new_row()
        c2a = self.get_card('modal-share-car')
        grid.add_card(c2a)
        c2b = self.get_card('modal-shares-rest')
        grid.add_card(c2b)
        c2c = self.get_card('number-of-passenger-kms')
        grid.add_card(c2c)
        c1a.connect_to(c2a)
        c1a.connect_to(c2b)
        c1b.connect_to(c2a)
        c1b.connect_to(c2b)

        grid.make_new_row()
        c3 = self.get_card('car-mileage-per-resident')
        grid.add_card(c3)
        c2a.connect_to(c3)
        c2c.connect_to(c3)

        grid.make_new_row()
        c4a = self.get_card('car-mileage')
        c4b = self.get_card('car-emission-factor')
        grid.add_card(c4a)
        grid.add_card(c4b)
        c3.connect_to(c4a)

        grid.make_new_row()
        c5 = self.get_card('parking-emission-reductions')
        grid.add_card(c5)
        c4a.connect_to(c5)
        c4b.connect_to(c5)

        return grid.render()

    def get_summary_vars(self):
        return dict(label=_('Emission reductions'), value=self.yearly_emissions_impact, unit='kt/a')

    def _refresh_parking_fee_cards(self):
        pcard = self.get_card('residential-parking-fee')
        self.set_variable('residential_parking_fee_increase', pcard.get_slider_value())
        icard = self.get_card('cars-affected-by-residential-parking-fee')
        self.set_variable('residential_parking_fee_share_of_cars_impacted', icard.get_slider_value())

        cd = CardDescription()
        df = predict_parking_fee_impact()

        last_hist_year = df[~df.Forecast].index.max()
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('€/year'),
            smoothing=False,
            # y_min=df['Fees'].min(),
            y_max=df.loc[last_hist_year]['ResidentialFees'] * (1 + MAX_PARKING_FEE_INCREASE_PERC / 100)
        )
        fig.add_series(df=df, column_name='ResidentialFees', trace_name='Asukaspysäköinnin hinta')
        pcard.set_figure(fig)

        pcard.set_description(cd.render("""
        Oletuksena on Wienin tutkimus maksullisen pysäköinnin vaikutuksesta, jonka mukaan pysäköintimaksun
        kaksinkertaistaminen vähentää pysäköintiä ja siten autoliikennettä siihen kohdistuvilla alueilla
        noin 8,8 %. Asukaspysäköintimaksujen korotus alkoi vuonna 2015 ja vuosimaksu nousee
        120 eurosta 360 euroon vuoteen 2021 mennessä. Asukaspysäköintitunnusten määrä on vuosina 2014–2019
        vähentynyt noin 600 kpl vaikka asukasluku on kasvanut kantakaupungissa."""))

        """{municipality_locative} lyhytaikainen pysäköinti on vähentynyt vuoden 2017 pysäköintimaksujen korotuksen
        jälkeen noin 10%."""

        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            smoothing=False,
            y_max=100
        )
        df['ResidentialShareOfCarsImpacted'] *= 100
        cd.set_values(
            residential_share_target=df['ResidentialShareOfCarsImpacted'].iloc[-1],
            residential_share=df[~df.Forecast]['ResidentialShareOfCarsImpacted'].iloc[-1],
        )
        fig.add_series(df=df, column_name='ResidentialShareOfCarsImpacted', trace_name='Osuus')
        icard.set_figure(fig)
        icard.set_description(cd.render("""
        Tarkastelussa on mukana vain keskustan asukaspysäköintivyöhykkeet.
        Asukaspysäköintilupia on myönnetty nyt n. {residential_share} % {municipality_genitive}
        liikennekäytössä olevalle henkilöautokannalle.
        Skenaariossa vuonna {target_year} asukaspysäköinnin piirissä on {residential_share_target} %
        auton omistajista.
        """))

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

        # df['Other'] += df.pop('Taxi')
        df['Rail'] = df.pop('Metro') + df.pop('Tram') + df.pop('Train')

        ccard = self.get_card('modal-share-car')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
        )
        fig.add_series(df=df, forecast=fc, column_name='Car', trace_name='Henkilöautot')
        ccard.set_figure(fig)
        df.pop('Car')

        mcard = self.get_card('modal-shares-rest')
        color_scale = len(df.columns)
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='%',
            legend=True,
            color_scale=color_scale,
        )
        last_hist_year = fc[~fc].index.max()
        columns = list(df.loc[last_hist_year].sort_values(ascending=False).index)
        for idx, col in enumerate(columns):
            name = MODE_TRANSLATIONS.get(col)
            if name is not None:
                name = name.get(get_active_locale())
            if name is None:
                name = col
            fig.add_series(df=df, forecast=fc, column_name=col, trace_name=name, color_idx=idx)

        mcard.set_figure(fig)

    def _refresh_mileage_cards(self):
        card = self.get_card('car-mileage-per-resident')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='km',
            color_scale=2,
            legend=True,
        )
        mdf = predict_road_mileage()
        pop = predict_population()

        cd = CardDescription()
        card.set_description(cd.render("""
        Henkilöautojen kilometrisuorite on saatu VTT:ltä ja se pitää sisällään henkilöautoliikenteen
        Helsingin aluerajojen sisäpuolella. Henkilöautojen käyttäjämääräksi on oletettu keskimäärin
        1,2 henkilöä autossa. Joukkoliikenteen matkustajakilometrit on saatu HSL:n tilastoista. Näiden
        lisäksi Helsingin katuverkossa liikkuu pitkän matkan busseja sekä turistibusseja, jotka muodostavat
        noin neljäsosan linja-autoliikenteestä Helsingissä. Kävelyn ja pyöräilyn oletukset henkilökilometreistä
        perustuvat HSL:n liikkumistutkimukseen matkamääristä ja keskimääräisistä pituuksista. Pyörällä
        oletuksena on keskipituus 3,7 km ja kävelymatkalla 1,2 km.
        """))

        fc = mdf.pop('Forecast')
        df = pd.DataFrame(fc)
        for vehicle, road in list(mdf.columns):
            if vehicle == 'Cars':
                df[road] = mdf[(vehicle, road)]
                df[road + 'PerResident'] = df[road] / pop['Population']
                df[road] /= 1000000

        fig.add_series(df=df, column_name='UrbanPerResident', trace_name='Katuajo', color_idx=0)
        fig.add_series(df=df, column_name='HighwaysPerResident', trace_name='Maantieajo', color_idx=1)
        card.set_figure(fig)

        card = self.get_card('car-mileage')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='M km',
            color_scale=2,
            stacked=True,
            fill=True,
            legend=True,
        )

        fig.add_series(df=df, column_name='Urban', trace_name='Katusuorite', color_idx=0)
        fig.add_series(df=df, column_name='Highways', trace_name='Maantiesuorite', color_idx=1)
        card.set_figure(fig)

    def _refresh_emission_cards(self):
        card = self.get_card('parking-emission-reductions')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='kt (CO2e.)/a',
            fill=True,
            smoothing=True,
        )

        with override_variable('residential_parking_fee_share_of_cars_impacted', 0):
            df0 = predict_cars_emissions()

        df1 = predict_cars_emissions()

        df1['Emissions'] -= df0['Emissions']
        self.yearly_emissions_impact = df1['Emissions'].iloc[-1]
        df_forecast = df1[df1.Forecast]

        fig.add_series(df=df_forecast, column_name='Emissions', trace_name=_('Emissions'))
        card.set_figure(fig)

        card = self.get_card('car-emission-factor')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='g/km',
        )
        fig.add_series(df=df1, column_name='EmissionFactor', trace_name=_('Emission factor'))
        card.set_figure(fig)

    def refresh_graph_cards(self):
        self._refresh_parking_fee_cards()
        self._refresh_trip_cards()
        self._refresh_mileage_cards()
        self._refresh_emission_cards()
