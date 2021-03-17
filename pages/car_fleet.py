from calc.transportation.car_fleet import (predict_cars_in_use,
                                           predict_cars_in_use_by_engine_type,
                                           predict_ev_charging_station_demand,
                                           predict_newly_registered_cars)
from calc.transportation.cars import predict_cars_emissions
from calc.transportation.parking import predict_parking_fee_impact
from common.locale import get_active_locale
from common.locale import lazy_gettext as _
from components.card_description import CardDescription
from components.cards import ConnectedCardGrid
from components.graphs import PredictionFigure
from utils.colors import ENGINE_TYPE_COLORS
from variables import get_variable, override_variable

from .base import Page
from .cars import ENGINE_TYPES


class CarFleetPage(Page):
    id = 'car-fleet'
    path = '/car-fleet'
    emission_sector = ('Transportation',)
    name = _('Car fleet')

    def make_cards(self):
        from .modal_share import ModalSharePage

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
            id='share-of-ev-charging-stations-built',
            title='Rakennettu osuus tarvittavista julkisista latausasemista',
            title_i18n=dict(en='Share of needed public EV charging stations built'),
            slider=dict(
                min=0,
                max=100,
                step=10,
                value=get_variable('share_of_ev_charging_station_demand_built'),
                marks={x: '%d %%' % x for x in range(0, 101, 10)},
            ),
        )
        self.add_graph_card(
            id='newly-registered-evs',
            title='Ensirekisteröityjen autojen osuudet käyttövoiman mukaan',
            title_i18n=dict(en='Share of newly registered cars by engine type'),
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

        self.add_graph_card(
            id='mileage',
            title='%s ajetut henkilöautokilometrit' % get_variable('municipality_locative'),
            title_i18n=dict(en='%s ajetut henkilöautokilometrit' % get_variable('municipality_name')),
            link_to_page=ModalSharePage,
        )
        self.add_graph_card(
            id='emission-factor',
            title='Henkilöautojen päästökerroin',
            title_i18n=dict(en='Emission factor of cars'),
        )

        self.add_graph_card(
            id='emission-impact',
            title='Toimenpiteiden päästövaikutukset',
            title_i18n=dict(en='Emission impact of actions'),
        )

    def get_content(self):
        grid = ConnectedCardGrid()

        grid.make_new_row()
        c1a = self.get_card('ev-parking-fee-discount')
        c1b = self.get_card('share-of-ev-charging-stations-built')
        c1c = self.get_card('cars-per-resident')
        grid.add_card(c1a)
        grid.add_card(c1b)
        grid.add_card(c1c)

        grid.make_new_row()
        c2a = self.get_card('newly-registered-evs')
        c2b = self.get_card('yearly-fleet-turnover')
        grid.add_card(c2a)
        grid.add_card(c2b)
        c1a.connect_to(c2a)
        c1b.connect_to(c2a)
        c1c.connect_to(c2b)

        grid.make_new_row()
        c3 = self.get_card('car-fleet')
        grid.add_card(c3)
        c2a.connect_to(c3)
        c2b.connect_to(c3)

        grid.make_new_row()
        c4a = self.get_card('emission-factor')
        c4b = self.get_card('mileage')
        grid.add_card(c4a)
        grid.add_card(c4b)
        c3.connect_to(c4a)

        grid.make_new_row()
        c5 = self.get_card('emission-impact')
        grid.add_card(c5)
        c4a.connect_to(c5)
        c4b.connect_to(c5)

        return grid.render()

    def get_summary_vars(self):
        return dict(label=_('Emission reductions'), value=self.yearly_emissions_impact, unit='kt/a')

    def refresh_graph_cards(self):
        card = self.get_card('ev-parking-fee-discount')
        self.set_variable('parking_subsidy_for_evs', card.get_slider_value())

        df = predict_parking_fee_impact()
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('€/year'),
            y_max=1000,
        )
        fig.add_series(df=df, column_name='ParkingSubsidyForEVs', trace_name=_('Yearly subsidy'))
        card.set_figure(fig)
        cd = CardDescription()
        cd.set_values(
            parking_subsidy_for_evs=get_variable('parking_subsidy_for_evs')
        )
        card.set_description(cd.render("""
            Skenaariossa täyssähköautoille myönnetään pysäköintietuuksia
            jatkossa yhteensä {parking_subsidy_for_evs} €/vuosi.
        """))
        card.set_description(cd.render("""
            In this scenario, BEVs will be given extra parking subsidies
            in total {parking_subsidy_for_evs} € per year.
        """), lang='en')

        card = self.get_card('share-of-ev-charging-stations-built')
        self.set_variable('share_of_ev_charging_station_demand_built', card.get_slider_value())

        df = predict_ev_charging_station_demand()
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('charging stations'),
            color_scale=2,
        )
        fig.add_series(df=df, column_name='Built', trace_name=_('Built'), color_idx=0)
        fig.add_series(df=df, column_name='Demand', trace_name=_('Demand'), color_idx=1)
        card.set_figure(fig)

        cd.set_values(
            stations_per_bev=int(get_variable('number_of_charging_stations_per_bev') * 100),
            share_stations=get_variable('share_of_ev_charging_station_demand_built'),
            built=df.iloc[-1].Built,
            demand=df.iloc[-1].Demand,
        )
        card.set_description(cd.render("""
            Täyssähköautoihin siirtyminen on nopeinta, kun julkisia latauspisteitä
            rakennetaan {stations_per_bev:noround} kpl jokaista 100 sähköautoa kohti. Skenaariossa
            tästä määrästä rakennetaan {share_stations} %. Vuonna {target_year} olisi
            tarve {demand} latauspisteelle ja rakennettuna on {built} latauspistettä.
        """))
        card.set_description(cd.render("""
            Moving to BEVs will happen the fastest when public charging stations are being
            built so that there will be {stations_per_bev:noround} stations for each 
            100 electric vehicles. In this scenario, the city will build {share_stations} %.
            In the year {target_year} there would be demand for {demand} stations and
            there will be {built} stations built.
        """), lang='en')

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
        cd.set_values(
            mean_yearly_turnover=df[~df.Forecast]['YearlyTurnover'].tail(8).mean()
        )
        card.set_description(cd.render("""
            Viime vuosina {municipality_locative} henkilöautokannasta uusittiin noin
            {mean_yearly_turnover} % vuodessa. Laskentamallissa oletataan, että
            uusiutumisnopeus ei juuri muutu.
        """))

        card = self.get_card('cars-per-resident')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('cars/1,000 res.'),
            smoothing=True,
        )
        df['CarsPerResident'] *= 1000
        fig.add_series(df=df, column_name='CarsPerResident', trace_name=_('Cars'))
        card.set_figure(fig)
        cd.set_values(
            cars_in_use=df[~df.Forecast]['NumberOfCars'].iloc[-1],
            cars_in_use_year=df[~df.Forecast].index.max(),
        )
        card.set_description(cd.render("""
            Laskentamallissa tarkastellaan ainoastaan liikennekäyttöön rekisteröityjä
            henkilöautoja. Vuonna {cars_in_use_year} {municipality_locative} oli liikennekäytössä
            {cars_in_use} henkilöautoa.
        """))

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
            et = ENGINE_TYPES[engine_type]
            fig.add_series(
                df=df, forecast=fc, column_name=engine_type,
                trace_name=et['name'], historical_color=et['color']
            )
        card.set_figure(fig)
        cd.set_values(
            bev_share=df[~fc]['BEV'].iloc[-1],
            phev_share=df[~fc]['PHEV'].iloc[-1],
            hist_year=df[~fc].index.max(),
        )
        card.set_description(cd.render("""
            Vuonna {hist_year} {municipality_genitive} ensirekisteröidyistä
            henkilöautoista {bev_share} % oli täyssähköautoja (BEV) ja
            {phev_share} % ladattavia hybridiautoja (PHEV).
        """))

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

        df = predict_cars_emissions()
        with override_variable('share_of_ev_charging_station_demand_built', 0):
            with override_variable('parking_subsidy_for_evs', 0):
                df0 = predict_cars_emissions()

        card = self.get_card('emission-factor')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name='g/km',
            color_scale=2,
            legend=True,
            legend_x=0.6,
        )
        fig.add_series(
            df=df, column_name='EmissionFactor', trace_name=_('Emission factor with actions'), color_idx=0
        )
        fig.add_series(
            df=df0, column_name='EmissionFactor', trace_name=_('Emission factor without actions'),
            color_idx=1
        )
        card.set_figure(fig)

        df.Mileage /= 1000000
        card = self.get_card('mileage')
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('M km'),
            fill=True,
        )
        fig.add_series(
            df=df, column_name='Mileage', trace_name=_('Vehicle mileage'),
        )
        card.set_figure(fig)

        card = self.get_card('emission-impact')

        df['Emissions'] -= df0['Emissions']
        df = df[df.Forecast]
        fig = PredictionFigure(
            sector_name='Transportation',
            unit_name=_('kt/a'),
            fill=True,
        )
        fig.add_series(df=df, column_name='Emissions', trace_name=_('Reductions'))
        self.net_emissions_impact = df['Emissions'].sum()
        self.yearly_emissions_impact = df['Emissions'].iloc[-1]
        card.set_figure(fig)
