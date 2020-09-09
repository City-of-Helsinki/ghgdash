import dash_bootstrap_components as dbc
import dash_html_components as html
import numpy as np
from babel.numbers import format_decimal
from dash.dependencies import Input, Output
from flask_babel import lazy_gettext as _

from calc.district_heating import predict_district_heating_emissions
from calc.district_heating_consumption import predict_district_heat_consumption
from calc.geothermal import predict_geothermal_production
from components.card_description import CardDescription
from components.cards import ConnectedCardGrid, GraphCard
from components.graphs import PredictionFigure
from components.stickybar import StickyBar
from variables import get_variable, set_variable

from .base import Page

DISTRICT_HEATING_GOAL = 251


def draw_existing_building_unit_heat_factor_graph(df):
    graph = PredictionFigure(
        sector_name='BuildingHeating',
        unit_name='kWh/k-m²',
        title=_('Existing building stock heat efficiency'),
        color_scale=2,
    )
    graph.add_series(
        df=df, column_name='ExistingBuildingHeatUsePerNetArea', trace_name=_('Heat efficiency'),
        color_idx=1
    )
    return graph.get_figure()


def draw_new_building_unit_heat_factor_graph(df):
    graph = PredictionFigure(
        sector_name='BuildingHeating',
        unit_name='kWh/k-m²',
        title=_('Future building stock heat efficiency'),
        color_scale=2,
    )
    graph.add_series(
        df=df, column_name='NewBuildingHeatUsePerNetArea', trace_name=_('Heat efficiency'),
        color_idx=1
    )
    return graph.get_figure()


def draw_heat_consumption(df):
    df.loc[~df.Forecast, 'NewBuildingHeatUse'] = np.nan
    graph = PredictionFigure(
        title=_('District heat net consumption'),
        unit_name='GWh',
        sector_name='BuildingHeating',
        smoothing=True,
        stacked=True,
        fill=True,
        color_scale=2,
    )

    graph.add_series(
        df=df, column_name='ExistingBuildingHeatUse', trace_name=_('Existing buildings'),
        color_idx=0,
    )
    graph.add_series(
        df=df, column_name='NewBuildingHeatUse', trace_name=_('Future buildings'),
        color_idx=1
    )

    return graph.get_figure()


def draw_district_heat_consumption_emissions(df):
    graph = PredictionFigure(
        sector_name='BuildingHeating',
        unit_name='kt', title=_('District heating emissions'),
        smoothing=True, allow_nonconsecutive_years=True,
        fill=True,
    )
    graph.add_series(
        df=df, column_name='NetEmissions', trace_name=_('Emissions')
    )
    return graph.get_figure()


def make_unit_emissions_card(df):
    last_emission_factor = df['Emission factor'].iloc[-1]
    last_year = df.index.max()

    return dbc.Card([
        html.A(dbc.CardBody([
            html.H4(_('District heating emission factor'), className='card-title'),
            html.Div([
                html.Span(
                    '%s g (CO₂e) / kWh' % (format_decimal(last_emission_factor, format='@@@', locale='fi_FI')),
                    className='summary-card__value'
                ),
                html.Span(' (%s)' % last_year, className='summary-card__year')
            ])
        ]), href='/kaukolammon-tuotanto')
    ], className='summary-card')


def make_bottom_bar(df):
    s = df['NetEmissions']
    last_emissions = s.iloc[-1]
    target_emissions = DISTRICT_HEATING_GOAL

    bar = StickyBar(
        label=_('District heating emissions'),
        value=last_emissions,
        # goal=target_emissions,
        unit='kt (CO₂e.)',
        current_page=page
    )
    return bar.render()


def generate_page():
    grid = ConnectedCardGrid()

    existing_card = GraphCard(
        id='district-heating-existing-building-unit-heat-factor',
        slider=dict(
            min=-60,
            max=20,
            step=5,
            value=get_variable('district_heating_existing_building_efficiency_change') * 10,
            marks={x: '%.1f %%' % (x / 10) for x in range(-60, 20 + 1, 10)},
        )
    )
    new_card = GraphCard(
        id='district-heating-new-building-unit-heat-factor',
        slider=dict(
            min=-60,
            max=20,
            step=5,
            value=get_variable('district_heating_new_building_efficiency_change') * 10,
            marks={x: '%.1f %%' % (x / 10) for x in range(-60, 20 + 1, 10)},
        ),
    )
    geo_card = GraphCard(
        id='district-heating-geothermal-production',
        link_to_page=('BuildingHeating', 'GeothermalHeating')
    )

    row = grid.make_new_row()
    row.add_card(existing_card)
    row.add_card(new_card)
    row.add_card(geo_card)

    consumption_card = GraphCard(
        id='district-heating-consumption',
        extra_content=html.Div(id='district-heating-unit-emissions-card')
    )
    existing_card.connect_to(consumption_card)
    new_card.connect_to(consumption_card)
    geo_card.connect_to(consumption_card)

    row = grid.make_new_row()
    row.add_card(consumption_card)

    emissions_card = GraphCard(id='district-heating-consumption-emissions')
    consumption_card.connect_to(emissions_card)
    row = grid.make_new_row()
    row.add_card(emissions_card)

    return html.Div([
        grid.render(),
        html.Div(id='district-heating-sticky-page-summary-container')
    ])


page = Page(
    id='district-heating',
    name=_('District heat consumption'),
    content=generate_page,
    path='/kaukolampo',
    emission_sector=('BuildingHeating', 'DistrictHeat')
)


@page.callback(inputs=[
    Input('district-heating-existing-building-unit-heat-factor-slider', 'value'),
    Input('district-heating-new-building-unit-heat-factor-slider', 'value'),
], outputs=[
    Output('district-heating-existing-building-unit-heat-factor-graph', 'figure'),
    Output('district-heating-existing-building-unit-heat-factor-description', 'children'),
    Output('district-heating-new-building-unit-heat-factor-graph', 'figure'),
    Output('district-heating-new-building-unit-heat-factor-description', 'children'),
    Output('district-heating-geothermal-production-graph', 'figure'),
    Output('district-heating-geothermal-production-description', 'children'),
    Output('district-heating-consumption-graph', 'figure'),
    Output('district-heating-unit-emissions-card', 'children'),
    Output('district-heating-consumption-emissions-graph', 'figure'),
    Output('district-heating-sticky-page-summary-container', 'children'),
])
def district_heating_consumption_callback(existing_building_perc, new_building_perc):
    set_variable('district_heating_existing_building_efficiency_change', existing_building_perc / 10)
    set_variable('district_heating_new_building_efficiency_change', new_building_perc / 10)

    df = predict_district_heat_consumption()
    geo_df = predict_geothermal_production()
    geo_df = geo_df[geo_df.Forecast]
    df['GeoEnergyProductionExisting'] = geo_df['GeoEnergyProductionExisting']
    df['GeoEnergyProductionNew'] = geo_df['GeoEnergyProductionNew']

    df['ExistingBuildingHeatUse'] -= df['GeoEnergyProductionExisting'].fillna(0)
    df['NewBuildingHeatUse'] -= df['GeoEnergyProductionNew'].fillna(0)

    first_forecast = df[df.Forecast].iloc[0]
    last_forecast = df[df.Forecast].iloc[-1]
    last_history = df[~df.Forecast].iloc[-1]

    cd = CardDescription()
    org_owned = get_variable('building_area_owned_by_org') / 100
    geo_production = last_forecast.GeoEnergyProductionExisting + last_forecast.GeoEnergyProductionNew
    cd.set_values(
        existing_renovation=get_variable('district_heating_existing_building_efficiency_change'),
        new_improvement=get_variable('district_heating_new_building_efficiency_change'),
        existing_next_year_reduction=(1 - (first_forecast.ExistingBuildingHeatUse - last_history.ExistingBuildingHeatUse)) * org_owned,
        new_area=last_forecast.NewBuildingNetArea,
        existing_area=last_forecast.ExistingBuildingNetArea,
        geo_production=geo_production,
        geo_percentage=(geo_production / last_forecast.TotalHeatConsumption) * 100,
    )
    existing_desc = cd.render("""
        Skenaarion mukaan nykyistä rakennuskantaa remontoidaan siten, että rakennuksien
        energiatehokkuus paranee {existing_renovation:noround} % vuodessa. Ensi vuonna {org_genitive}
        omistamien rakennuksien lämmönkulutuksen pitää pudota {existing_next_year_reduction} GWh.
    """)
    new_desc = cd.render("""
        Uuden rakennuskannan energiatehokkuus paranee skenaariossa {new_improvement:noround} % vuodessa.
        Vuonna {target_year} nykyistä rakennuskantaa on {existing_area} milj. kem² ja uutta rakennuskantaa
        {new_area} milj. kem².
    """)
    geo_desc = cd.render("""
        Vanhassa ja uudessa rakennuskannassa korvataan kaukolämpöä paikallisesti tuotetulla
        maalämmöllä siten, että vuonna {target_year} kaukolämpöä korvataan {geo_production} GWh
        ({geo_percentage} % sen vuoden kaukolämmönkulutuksesta).
    """)

    fig1 = draw_existing_building_unit_heat_factor_graph(df)
    fig2 = draw_new_building_unit_heat_factor_graph(df)

    geo_fig = PredictionFigure(
        sector_name='BuildingHeating',
        unit_name='GWh',
        title=_('District heating replaced by geothermal'),
        fill=True,
    )
    geo_fig.add_series(
        df=geo_df, column_name='GeoEnergyProduction', trace_name=_('Geothermal production'),
    )

    fig3 = draw_heat_consumption(df)

    df = predict_district_heating_emissions()
    unit_emissions_card = make_unit_emissions_card(df)
    fig4 = draw_district_heat_consumption_emissions(df)
    sticky = make_bottom_bar(df)

    return [
        fig1, dbc.Col(existing_desc, style=dict(minHeight='8rem')),
        fig2, dbc.Col(new_desc, style=dict(minHeight='8rem')),
        geo_fig.get_figure(), dbc.Col(geo_desc, style=dict(minHeight='8rem')),
        fig3, unit_emissions_card, fig4, sticky
    ]
