from flask_babel import lazy_gettext as _

from calc.district_heating import predict_district_heating_emissions
from calc.electricity import predict_electricity_emission_factor
from calc.geothermal import predict_geothermal_production
from components.card_description import CardDescription
from components.cards import ConnectedCardGrid
from components.graphs import PredictionFigure
from variables import get_variable

from .base import Page


class GeothermalPage(Page):
    id = 'geothermal-heating'
    path = '/maalampo'
    emission_sector = ('BuildingHeating', 'GeothermalHeating')
    name = _('Geothermal heat production')

    def make_cards(self):
        max_perc = 40
        self.add_graph_card(
            id='renovated-per-year',
            title=_('Floor area heated by geothermal in existing building stock'),
            slider=dict(
                min=0,
                max=max_perc,
                step=1,
                value=int(self.get_variable('geothermal_existing_building_renovation') * 10),
                marks={x: '%d %%' % (x / 10) for x in range(0, max_perc + 1, 10)},
            ),
        )
        self.add_graph_card(
            id='new-building-installation',
            title=_('Floor area heated by geothermal in future building stock'),
            slider=dict(
                min=0,
                max=100,
                step=10,
                value=get_variable('geothermal_new_building_installation_share'),
                marks={x: '%d %%' % x for x in range(0, 100 + 1, 10)},
            ),
        )
        self.add_graph_card(
            id='geothermal-production',
            title=_('Geothermal heat energy production'),
        )
        self.add_graph_card(
            id='emissions',
            title=_('Net emissions from geothermal production'),
        )
        self.add_graph_card(
            id='electricity-emission-factor',
            title=_('Electricity production emission factor'),
        )
        self.add_graph_card(
            id='district-heat-emission-factor',
            title=_('District heating emission factor'),
            link_to_page=('BuildingHeating', 'DistrictHeat'),
        )

    def get_content(self):
        grid = ConnectedCardGrid()

        grid.make_new_row()
        c1a = self.get_card('renovated-per-year')
        grid.add_card(c1a)
        c1b = self.get_card('new-building-installation')
        grid.add_card(c1b)

        """
        grid.make_new_row()
        c2a = self.get_card('boreholes-existing-buildings')
        c2b = self.get_card('boreholes-new-buildings')
        grid.add_card(c2a)
        grid.add_card(c2b)
        c1a.connect_to(c2a)
        c1b.connect_to(c2b)
        """

        grid.make_new_row()
        c3a = self.get_card('geothermal-production')
        c3b = self.get_card('electricity-emission-factor')
        c3c = self.get_card('district-heat-emission-factor')
        grid.add_card(c3a)
        grid.add_card(c3b)
        grid.add_card(c3c)
        c1a.connect_to(c3a)
        c1b.connect_to(c3a)

        grid.make_new_row()
        c4 = self.get_card('emissions')
        grid.add_card(c4)
        c3a.connect_to(c4)
        c3b.connect_to(c4)
        c3c.connect_to(c4)

        return grid.render()

    def get_summary_vars(self):
        return dict()

    def refresh_graph_cards(self):
        ecard = self.get_card('renovated-per-year')
        self.set_variable('geothermal_existing_building_renovation', ecard.get_slider_value() / 10)
        ncard = self.get_card('new-building-installation')
        self.set_variable('geothermal_new_building_installation_share', ncard.get_slider_value())

        df = predict_geothermal_production()
        print(df)

        fig = PredictionFigure(
            sector_name='BuildingHeating',
            unit_name='milj. k-m²',
            smoothing=True,
            y_max=25,
        )
        fig.add_series(
            df=df, column_name='GeoBuildingNetAreaExisting', trace_name='Kerrosala',
        )
        ecard.set_figure(fig)

        org_owned = self.get_variable('building_area_owned_by_org') / 100
        cd = CardDescription()

        first_forecast = df[df.Forecast].iloc[0]
        last_forecast = df.iloc[-1]
        last_hist_year = df[~df.Forecast].index.max()
        last_forecast_year = df[df.Forecast].index.max()

        cd.set_values(
            existing_building_perc=self.get_variable('geothermal_existing_building_renovation'),
            existing_building_area=last_forecast.GeoBuildingNetAreaExisting,
            boreholes_org=first_forecast.BoreholesPerYear * org_owned,
            boreholes_others=first_forecast.BoreholesPerYear * (1 - org_owned),
            borehole_area=last_forecast.BoreholeAreaNeeded,
            borehole_depth=self.get_variable('geothermal_borehole_depth'),
            new_building_perc=self.get_variable('geothermal_new_building_installation_share'),
            new_building_area=last_forecast.GeoBuildingNetAreaNew,
            geothermal_production=last_forecast.GeoEnergyProduction,
            perc_dh=last_forecast.GeoEnergyProduction
        )
        ecard.set_description(cd.render("""
        Kun olemassaolevasta rakennuskannasta remontoidaan {existing_building_perc:noround} %
        joka vuosi ja vaihdetaan lämmitystavaksi maalämpö, vuonna {target_year} maalämmöllä
        lämmitetään {existing_building_area} milj. kerrosneliömetriä. Skenaarion toteutumiseksi
        {org_genitive} pitää rakentaa ensi vuonna {boreholes_org} maalämpökaivoa, kun oletetaan kaivon
        syvyydeksi {borehole_depth} m. Muiden pitää rakentaa ensi vuonna {boreholes_others} kaivoa.
        """))

        ncard.set_description(cd.render("""
        Kun uudesta rakennuskannasta {new_building_perc:noround} % rakennetaan maalämmöllä,
        vuonna {target_year} lämmitetään maalämmöllä {new_building_area} milj. kerrosneliömetriä.
        |p|Vanhan ja uuden rakennuskannan maalämpökaivot tarvitsevat silloin yhteensä {borehole_area} km²
        pinta-alaa.
        """))
        fig = PredictionFigure(
            sector_name='BuildingHeating',
            unit_name='milj. k-m²',
            smoothing=True,
            y_max=10,
        )
        fig.add_series(
            df=df, column_name='GeoBuildingNetAreaNew', trace_name='Kerrosala',
        )
        ncard.set_figure(fig)

        card = self.get_card('geothermal-production')
        fig = PredictionFigure(
            sector_name='BuildingHeating',
            unit_name='GWh',
            smoothing=True,
            fill=True,
            stacked=True,
            color_scale=2,
        )
        fig.add_series(
            df=df, column_name='GeoEnergyProductionExisting', trace_name='Vanha rakennuskanta',
            color_idx=0,
        )
        fig.add_series(
            df=df, column_name='GeoEnergyProductionNew', trace_name='Uusi rakennuskanta',
            color_idx=1,
        )
        card.set_figure(fig)
        card.set_description(cd.render("""
            Vuonna {target_year} maalämpöpumpuilla tuotetaan {geothermal_production} GWh lämpöä.
            Skenaariossa se käytetään korvaamaan kaukolämpöä.
        """))

        # District heat
        dhdf = predict_district_heating_emissions()
        card = self.get_card('district-heat-emission-factor')
        fig = PredictionFigure(
            sector_name='BuildingHeating',
            unit_name='g/kWh',
            smoothing=True,
        )
        fig.add_series(
            df=dhdf, column_name='Emission factor', trace_name=_('Emission factor')
        )
        card.set_figure(fig)
        last_dhdf_hist_year = dhdf[~dhdf.Forecast].index.max()
        dhef_target = dhdf.loc[last_forecast_year, 'Emission factor']
        dhef_hist = dhdf.loc[last_dhdf_hist_year, 'Emission factor']
        cd.set_values(
            dh_emission_factor_target=dhef_target,
            dh_emission_factor_hist=dhef_hist,
            perc_change=((dhef_target / dhef_hist) - 1) * 100
        )
        cd.set_variables(
            last_dhdf_hist_year=last_dhdf_hist_year,
        )
        card.set_description(cd.render("""
            Skenaariossa paikallisella maalämmöllä korvataan pelkästään kaukolämpöä.
            Vuonna {target_year} kaukolämmöntuotannon päästökerroin on {dh_emission_factor_target}
            g/km. Muutos vuoteen {last_dhdf_hist_year} on {perc_change} %.
        """))

        # Electricity
        edf = predict_electricity_emission_factor()
        card = self.get_card('electricity-emission-factor')
        fig = PredictionFigure(
            sector_name='ElectricityConsumption',
            unit_name='g/kWh',
            smoothing=True,
        )
        fig.add_series(
            df=edf, column_name='EmissionFactor', trace_name=_('Emission factor'),
        )
        card.set_figure(fig)
        cd.set_values(
            heat_pump_el=last_forecast.ElectricityUse,
            elef=edf.loc[last_forecast_year].EmissionFactor,
        )
        card.set_description(cd.render("""
            Vuonna {target_year} maalämpöpumput käyttävät sähköä {heat_pump_el} GWh.
            Sähkönkulutuksesta aiheutuvat päästöt määräytyvät sähkönhankinnan päästökertoimen
            mukaan ({elef} g/kWh vuonna {target_year}).
        """))

        card = self.get_card('emissions')
        fig = PredictionFigure(
            sector_name='BuildingHeating',
            unit_name='kt',
            smoothing=True,
            fill=True,
        )
        fig.add_series(
            df=df, column_name='NetEmissions', trace_name=_('Emissions'),
        )
        card.set_figure(fig)
