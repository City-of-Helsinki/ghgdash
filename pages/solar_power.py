import numpy as np
from flask_babel import lazy_gettext as _

from calc.electricity import predict_electricity_emission_factor
from calc.solar_power import predict_solar_power_production
from components.card_description import CardDescription
from components.cards import ConnectedCardGrid, GraphCard
from components.graphs import PredictionFigure
from variables import get_variable, set_variable

from .base import Page

SOLAR_POWER_GOAL = 1009  # GWh
CITY_OWNED = 19.0  # %


class PVPage(Page):
    id = 'solar-electricity'
    path = '/solar-electricity'
    emission_sector = ('ElectricityConsumption', 'SolarProduction')
    name = _('Local solar power production')

    def make_cards(self):
        self.add_graph_card(
            id='existing-buildings',
            slider=dict(
                min=0,
                max=90,
                step=5,
                value=get_variable('solar_power_existing_buildings_percentage'),
                marks={x: '%d %%' % x for x in range(0, 90 + 1, 10)},
            ),
            title='Vanhan rakennuskannan aurinkopaneelien piikkiteho',
            title_i18n=dict(en='Peak power of PV panels on existing building stock')
        )
        self.add_graph_card(
            id='new-buildings',
            slider=dict(
                min=20,
                max=100,
                step=5,
                value=get_variable('solar_power_new_buildings_percentage'),
                marks={x: '%d %%' % x for x in range(20, 100 + 1, 10)},
            ),
            title='Uuden rakennuskannan aurinkopaneelien piikkiteho',
            title_i18n=dict(en='Peak power of PV panels on future building stock')
        )
        self.add_graph_card(
            id='production',
            title='Aurinkopaneelien sähköntuotanto',
            title_i18n=dict(en='PV panel energy production')
        )
        self.add_graph_card(
            id='emission-impact',
            title='Aurinkopaneelien päästövaikutukset',
            title_i18n=dict(en='Emission impact of PV energy production')
        )

    def get_content(self):
        grid = ConnectedCardGrid()

        grid.make_new_row()
        c1a = self.get_card('existing-buildings')
        c1b = self.get_card('new-buildings')
        grid.add_card(c1a)
        grid.add_card(c1b)

        grid.make_new_row()
        c2a = self.get_card(id='production')
        grid.add_card(c2a)
        c1a.connect_to(c2a)
        c1b.connect_to(c2a)

        grid.make_new_row()
        c3a = self.get_card(id='emission-impact')
        grid.add_card(c3a)
        c2a.connect_to(c3a)

        return grid.render()

    def get_summary_vars(self):
        return dict(label=_('PV energy production'), value=self.solar_production_forecast, unit='GWh/a')

    def refresh_graph_cards(self):
        # First see what the maximum solar production capacity is to set the
        # Y axis maximum.
        set_variable('solar_power_existing_buildings_percentage', 100)
        set_variable('solar_power_new_buildings_percentage', 100)
        kwp_max_df = predict_solar_power_production()

        # Then predict with the given percentages.
        existing_card = self.get_card('existing-buildings')
        set_variable('solar_power_existing_buildings_percentage', existing_card.get_slider_value())

        future_card = self.get_card('new-buildings')
        set_variable('solar_power_new_buildings_percentage', future_card.get_slider_value())

        df = predict_solar_power_production()

        forecast_df = df[df.Forecast]
        hist_df = df[~df.Forecast]
        years_left = forecast_df.index.max() - hist_df.index.max()
        ekwpa = (forecast_df.SolarPowerExisting.iloc[-1] - hist_df.SolarPowerExisting.iloc[-1]) / years_left
        nkwpa = forecast_df.SolarPowerNew.iloc[-1] / years_left

        cd = CardDescription()
        city_owned = get_variable('building_area_owned_by_org') / 100
        cd.set_values(
            existing_building_perc=existing_card.get_slider_value(),
            org_existing_building_kwp=1000 * ekwpa * city_owned,
            others_existing_building_kwp=1000 * ekwpa * (1 - city_owned)
        )
        existing_card.set_description(cd.render("""
        Kun aurinkopaneeleita rakennetaan {existing_building_perc:noround} % kaikesta vanhan
        rakennuskannan kattopotentiaalista, {org_genitive} tulee rakentaa aurinkopaneeleita
        {org_existing_building_kwp} kWp vuodessa skenaarion toteutumiseksi. Muiden kuin {org_genitive}
        tulee rakentaa {others_existing_building_kwp} kWp aurinkopaneeleita vuodessa.
        """))

        cd.set_values(
            new_building_perc=future_card.get_slider_value(),
            org_new_building_kwp=1000 * nkwpa * city_owned,
            others_new_building_kwp=1000 * nkwpa * (1 - city_owned)
        )
        future_card.set_description(cd.render("""
        Kun uuteen rakennuskantaan rakennetaan aurinkopaneeleja {new_building_perc:noround} %
        kaikesta kattopotentiaalista, {org_genitive} tulee rakentaa aurinkopaneeleja
        {org_new_building_kwp} kWp vuodessa skenaarion toteutumiseksi. Muiden kuin {org_genitive}
        tulee rakentaa {others_new_building_kwp} kWp aurinkopaneeleita vuodessa.
        """))

        ymax = kwp_max_df.SolarPowerExisting.iloc[-1]
        fig = PredictionFigure(
            sector_name='ElectricityConsumption', unit_name='MWp',
            y_max=ymax, color_scale=2
        )
        fig.add_series(df=df, trace_name=_('Peak power'), column_name='SolarPowerExisting', color_idx=0)
        existing_card.set_figure(fig)

        fig = PredictionFigure(
            sector_name='ElectricityConsumption', unit_name='MWp',
            y_max=ymax, color_scale=2
        )
        fig.add_series(df=df, trace_name=_('Peak power'), column_name='SolarPowerNew', color_idx=1)
        future_card.set_figure(fig)

        pv_kwh_wp = get_variable('yearly_pv_energy_production_kwh_wp')
        df.SolarPowerNew = df.SolarPowerNew * pv_kwh_wp
        df.SolarPowerExisting = df.SolarPowerExisting * pv_kwh_wp
        df.loc[~df.Forecast, 'SolarPowerNew'] = np.nan

        card = self.get_card('production')
        fig = PredictionFigure(
            sector_name='ElectricityConsumption', unit_name='GWh',
            stacked=True, fill=True, color_scale=2
        )
        fig.add_series(df=df, trace_name=_('Existing buildings'), column_name='SolarPowerExisting', color_idx=0)
        fig.add_series(df=df, trace_name=_('Future buildings'), column_name='SolarPowerNew', color_idx=1)
        card.set_figure(fig)

        card = self.get_card('emission-impact')
        fig = PredictionFigure(
            sector_name='ElectricityConsumption', unit_name='kt',
            fill=True
        )
        ef_df = predict_electricity_emission_factor()
        df['NetEmissions'] = -df['SolarProduction'] * ef_df['EmissionFactor'] / 1000
        fig.add_series(df=df, column_name='NetEmissions', trace_name=_('Emissions'))
        card.set_figure(fig)

        s = df.SolarProduction
        self.solar_production_forecast = s.iloc[-1] * get_variable('yearly_pv_energy_production_kwh_wp')
