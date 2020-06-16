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
from .modal_share import ModalSharePage
from .car_fleet import CarFleetPage

from calc.transportation.cars import predict_cars_emissions
from utils.colors import GHG_MAIN_SECTOR_COLORS, ENGINE_TYPE_COLORS

CARS_GOAL = 119  # kt CO2e


ENGINE_TYPES = {
    'electric': dict(name=_('Electric'), color=ENGINE_TYPE_COLORS['BEV']),
    'PHEV (gasoline)': dict(name=_('PHEV'), color=ENGINE_TYPE_COLORS['PHEV']),
    'gasoline': dict(name=_('Gasoline'), color=ENGINE_TYPE_COLORS['gasoline']),
    'diesel': dict(name=_('Diesel'), color=ENGINE_TYPE_COLORS['diesel']),
}


def draw_bev_chart(df):
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


def make_bottom_bar(df):
    last_emissions = df.iloc[-1].loc['Emissions']

    bar = StickyBar(
        label="Henkilöautojen päästöt",
        value=last_emissions,
        # goal=CARS_GOAL,
        unit='kt (CO₂e.) / a',
        current_page=page,
    )
    return bar.render()


def generate_page():
    grid = ConnectedCardGrid()
    bev_perc_card = GraphCard(
        id='cars-bev-percentage',
        title='Sähköautojen ajosuoriteosuus',
        title_i18n=dict(en='BEV mileage share'),
        slider=dict(
            min=0,
            max=100,
            step=5,
            value=get_variable('cars_bev_percentage'),
            marks={x: '%d %%' % x for x in range(0, 100 + 1, 10)},
        ),
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
    #grid.add_card(biofuel_card)
    grid.add_card(per_resident_card)
    grid.make_new_row()
    grid.add_card(emission_factor_card)
    grid.add_card(mileage_card)
    grid.make_new_row()
    grid.add_card(emissions_card)

    bev_perc_card.connect_to(emission_factor_card)
    #biofuel_card.connect_to(emission_factor_card)
    emission_factor_card.connect_to(emissions_card)

    per_resident_card.connect_to(mileage_card)
    mileage_card.connect_to(emissions_card)

    return html.Div([
        grid.render(),
        html.Div(id='cars-sticky-page-summary-container')
    ])


page = Page(
    id='cars',
    name='Henkilöautoilun päästöt',
    content=generate_page,
    path='/autot',
    emission_sector=('Transportation', 'Cars')
)


@page.callback(inputs=[
    Input('cars-bev-percentage-slider', 'value'),
], outputs=[
    Output('cars-bev-percentage-graph', 'figure'),
    Output('cars-bev-percentage-description', 'children'),
    # Output('cars-biofuel-percentage-graph', 'figure'),
    Output('cars-emission-factor-graph', 'figure'),
    Output('cars-mileage-per-resident-graph', 'figure'),
    Output('cars-mileage-per-resident-description', 'children'),
    Output('cars-total-mileage-graph', 'figure'),
    Output('cars-emissions-graph', 'figure'),
    Output('cars-sticky-page-summary-container', 'children'),
])
def cars_callback(bev_percentage):
    set_variable('cars_bev_percentage', bev_percentage)

    df = predict_cars_emissions()
    df['Mileage'] /= 1000000

    bev_chart = draw_bev_chart(df)
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

    sticky = make_bottom_bar(df)

    return [
        bev_chart, dbc.Col(bev_desc), emission_factor_chart,
        per_resident_chart, dbc.Col(pr_desc), mileage_chart,
        emissions_chart, sticky
    ]


if __name__ == '__main__':
    generate_page()
    draw_bev_chart()
