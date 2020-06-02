import dash
from common import cache
import os
import pandas as pd
import dash_table
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash.dependencies import Input, Output, State
from flask_babel import Babel, lazy_gettext as _

from calc import calcfunc
from calc.electricity import calculate_electricity_supply_emission_factor
from components.cards import GraphCard
from components.graphs import make_layout
from utils.quilt import load_datasets


app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True
server = app.server
babel = Babel(server)
with server.app_context():
    server.config.from_object('common.settings')

    cache.init_app(server)


DEFAULT_PRICE_PER_KWH = 12
INITIAL_INSTALL_PRICE = 5000
PRICE_PER_PEAK_KW = 1000
PEAK_WATTS_PER_M2 = 150


hel_buildings, hsy_buildings, fingrid_price = load_datasets([
    'jyrjola/karttahel/buildings', 'jyrjola/hsy/buildings', 'jyrjola/fingrid_hourly/price'
])


def read_nuuka_data():
    DATA_DIR = 'data/nuuka'

    buildings = pd.read_parquet(DATA_DIR + '/buildings.parquet')
    sensors = pd.read_parquet(DATA_DIR + '/sensors.parquet')

    def is_building_needed(b_id):
        if os.path.exists('data/nuuka/%s.parquet' % b_id):
            return True
        else:
            return False

    buildings['HasData'] = buildings.index.map(is_building_needed)
    buildings = buildings[buildings.HasData].drop(columns='HasData')

    return buildings, sensors


buildings, sensors = read_nuuka_data()
electricity_sensors = sensors.query('category == "electricity"')
heating_sensors = sensors.query('category == "heating"')


def combine_buildings():
    buildings['VTJPRT'] = None
    hel_buildings['BuildingID'] = None

    for property_number, counts in buildings.property_number.value_counts().items():
        property_buildings = buildings.query('property_number == "%s"' % property_number)
        property_numbers = property_number.split(', ')
        hdf = hel_buildings[hel_buildings.c_kiinteistotunnus.isin(property_numbers)]
        if hdf.empty:
            print("no match for %s:" % property_numbers)
            # display(property_buildings)
            continue

        if counts == 1:
            assert len(property_buildings) == 1
            hel_buildings.loc[hdf.index, 'BuildingID'] = property_buildings.index[0]
            continue

        property_buildings = property_buildings.query('area_gross >= 100')

        for b_id, b in property_buildings.iterrows():
            prt = None
            if len(hdf) == 1:
                prt = hdf.iloc[0].VTJPRT

            if prt is None:
                hb = hdf[(hdf.Kerrosala == b.area_net) & (hdf.Rakennustilavuus == b.volume)]
                if len(hb) == 1:
                    prt = hdf.iloc[0].VTJPRT

            if prt is None:
                hb = hdf[hdf.Rakennustilavuus == b.volume]
                if len(hb) == 1:
                    prt = hdf.iloc[0].VTJPRT

            if prt is None:
                print("no match for %s (area %s)" % (b.description, b.area_net))
                print('\t%s' % property_number)
                continue

            buildings.loc[b_id, 'VTJPRT'] = prt


@calcfunc()
def get_buildings_with_pv():
    combine_buildings()

    bdf = hel_buildings.dropna(subset=['BuildingID', 'VTJPRT'])
    hsydf = hsy_buildings.set_index('vtj_prt')[['panel_ala', 'elec_kwh_v']].dropna()
    bdf = bdf.merge(hsydf, left_on='VTJPRT', right_index=True, how='left')

    pv_df = bdf.groupby('BuildingID')[['panel_ala', 'elec_kwh_v']].sum()

    df = buildings.merge(pv_df, left_index=True, right_index=True)
    return df


@calcfunc(
    datasets=dict(
        radiation='jyrjola/fmi/solar_radiation_kumpula',
    )
)
def calculate_percentage_of_yearly_radiation(datasets):
    df = datasets['radiation']

    sol = df['Global radiation']
    sol = sol.clip(lower=0)  # replace negative values with zero
    sol = sol.loc[sol.index < '2019']
    yearly_pv = sol.groupby(pd.Grouper(freq='AS')).sum().reindex(sol.index).fillna(method='ffill')

    perc_sol = sol / yearly_pv
    perc_sol.name = 'SolarPercentage'

    return perc_sol


try:
    buildings_with_pv = pd.read_parquet('data/nuuka/buildings_with_pv.parquet')
except Exception:
    buildings_with_pv = get_buildings_with_pv()
    buildings_with_pv.to_parquet('data/nuuka/buildings_with_pv.parquet')


app.layout = dbc.Container([dbc.Row([dbc.Col([
    dbc.Row([
        dbc.Col([
            html.H5('Rakennus'),
            dcc.Dropdown(
                id='building-selector-dropdown',
                options=[dict(label=b.description, value=b_id) for b_id, b in buildings_with_pv.iterrows()],
                value=buildings_with_pv.index[0]
            )
        ], className='mb-4'),
    ], className='mt-4'),
    dbc.Row([
        dbc.Col([
            dcc.Loading(id="loading-3", children=[
                html.Div(id="building-info-placeholder")
            ], type="default"),
        ]),
    ]),
    html.H4('Aurinkopaneelit'),
    dbc.Row([
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Alkukustannus', html_for='price-of-initial-installation'),
                dbc.InputGroup([
                    dbc.Input(
                        type='number',
                        id='price-of-initial-installation',
                        value=INITIAL_INSTALL_PRICE,
                    ),
                    dbc.InputGroupAddon("€", addon_type="append"),
                ]),
            ]),
        ], md=3),
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Piikkitehon marginaalikustannus', html_for='marginal-price-of-peak-power'),
                dbc.InputGroup([
                    dbc.Input(
                        type='number',
                        id='marginal-price-of-peak-power',
                        value=PRICE_PER_PEAK_KW,
                    ),
                    dbc.InputGroupAddon("€/kWp", addon_type="append"),
                ]),
            ]),
        ], md=5),
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Laitteiston pitoaika', html_for='investment-years'),
                dbc.InputGroup([
                    dbc.Input(
                        type='number',
                        id='investment-years',
                        value=20,
                    ),
                    dbc.InputGroupAddon("vuotta", addon_type="append"),
                ]),
            ]),
        ], md=4)
    ]),
    dbc.Row([
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Ostosähkön hinta', html_for='price-of-purchased-electricity'),
                dbc.InputGroup([
                    dbc.Input(
                        type='number',
                        id='price-of-purchased-electricity',
                        value=DEFAULT_PRICE_PER_KWH,
                        inputMode='numeric',
                    ),
                    dbc.InputGroupAddon("c/kWh", addon_type="append"),
                ]),
            ]),
        ], md=3),
        dbc.Col([
            dbc.FormGroup([
                dbc.Label('Ylijäämäsähkön myynti', html_for='grid-output-percentage'),
                dbc.InputGroup([
                    dbc.Input(
                        type='number',
                        id='grid-output-percentage',
                        value=90,
                        inputMode='numeric',
                    ),
                    dbc.InputGroupAddon("%", addon_type="append"),
                ]),
            ]),
        ], md=4),
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Button("Laske", id="calculate-button", className="float-right"),
        ])
    ]),
    dcc.Loading(id="loading-1", children=[
        html.Div(id="building-placeholder")
    ], type="default"),
], md=8)])])


def simulate_pv_production(percentage_power, df, variables, datasets):
    df['PanelProduction'] = df.MaxSolarProduction * percentage_power / 100

    grid_balance = df.Consumption - df['PanelProduction']
    df['GridOutput'] = -grid_balance.clip(upper=0) * variables['grid_output_percentage']
    df['GridInput'] = grid_balance.clip(lower=0)

    spot_price, _ = datasets['electricity_spot_price'].align(df.GridOutput, axis=0, fill_value=0, join='right')
    df['EnergySalesIncome'] = df.GridOutput.mul(spot_price / 1000) * 1.00

    df['GridInputReduction'] = df.Consumption - df.GridInput
    df['SolarEnergySupplied'] = df['GridInputReduction'] + df['GridOutput']
    ef = datasets['electricity_supply_emission_factor']
    df['EmissionsReduction'] = df['SolarEnergySupplied'].mul(ef, axis=0, fill_value=0)

    cols = [
        'PanelProduction', 'Consumption', 'GridOutput', 'GridInput',
        'GridInputReduction', 'SolarEnergySupplied', 'EnergySalesIncome', 'EmissionsReduction'
    ]
    df = df[cols]
    return df


def generate_pv_summary(percentage_power, building, sim_df, variables, datasets):
    nr_years = (sim_df.index.max() - sim_df.index.min()).days / 365

    peak_power = building.panel_ala * PEAK_WATTS_PER_M2 * percentage_power / 100

    installation_price = variables['price_of_initial_installation']
    installation_price += variables['marginal_price_of_peak_power'] * peak_power / 1000

    from_solar_sum = sim_df.GridInputReduction.sum()

    s = pd.Series(dict(
        SolarPeakPower=peak_power / 1000,  # in kW
        SolarEnergyProduction=sim_df.PanelProduction.sum() / nr_years,
        BuildingEnergyConsumption=sim_df.Consumption.sum() / nr_years,
        GridInputReduction=from_solar_sum / nr_years,
        GridEnergyOutput=sim_df.GridOutput.sum() / nr_years,
        EnergySalesIncome=sim_df.EnergySalesIncome.sum() / nr_years,
        EnergyCostSavings=from_solar_sum * variables['price_of_purchased_electricity'] / nr_years,
        InstallationPrice=installation_price,
    ), name=percentage_power)

    investment_per_year = s.InstallationPrice / variables['investment_years']
    s['NetCosts'] = investment_per_year - s.EnergySalesIncome - s.EnergyCostSavings

    s['EmissionsReduction'] = sim_df.EmissionsReduction.sum() / nr_years / 1000  # in kg
    s['EmissionReductionCost'] = s.NetCosts / s.EmissionsReduction  # € / kg

    return s


def analyze_building(building, consumption_df, perc_to_test, variables, datasets):
    print('analyzing')

    if not building.elec_kwh_v:
        return None

    df = consumption_df[consumption_df.building_id == building.name].set_index('time').copy()
    # Merge the data about the hourly solar radiation percentage
    df = df.merge(datasets['yearly_solar_radiation_ratio'], left_index=True, right_index=True, how='left')
    # Calculate maximum solar production potential
    df['MaxSolarProduction'] = building.elec_kwh_v * df['SolarPercentage']
    df = df.drop(columns='SolarPercentage').dropna()

    df = df.rename(columns=(dict(value='Consumption')))

    if perc_to_test is None:
        out = pd.DataFrame()
        perc_to_test = range(1, 100 + 1, 1)
        for perc in perc_to_test:
            sim_df = simulate_pv_production(perc, df, variables, datasets)
            summary = generate_pv_summary(perc, building, sim_df, variables, datasets)
            out = out.append(summary)
        return out
    else:
        sim_df = simulate_pv_production(perc_to_test, df, variables, datasets)
        summary = generate_pv_summary(perc_to_test, building, sim_df, variables, datasets)
        return dict(simulated=sim_df, summary=summary)


def visualize_building_pv_summary(building, df, variables):
    x = df.SolarPeakPower

    t1 = dict(
        type='scatter',
        x=x,
        y=df.InstallationPrice / variables['investment_years'] / 1000,
        mode='lines',
        name='Investointikustannukset (per vuosi, %d v)' % variables['investment_years'],
        marker=dict(color='red')
    )
    t2 = dict(
        type='scatter',
        x=x,
        y=(df.EnergyCostSavings + df.EnergySalesIncome) / 1000,
        mode='lines',
        name='Säästö (per vuosi)',
        marker=dict(color='green'),
    )
    t3 = dict(
        type='scatter',
        x=x,
        y=df.EmissionReductionCost,
        mode='lines',
        name='Päästövähennyksen hinta',
        yaxis='y2',
        marker=dict(color='grey'),
    )
    layout = make_layout(
        title='Aurinkopaneelien tuottoennuste: %s' % ' '.join(building.description.split(' ')[1:]),
        yaxis=dict(
            title='1 000 €',
            hoverformat='.3r',
            rangemode='tozero',
            separatethousands=True,
        ),
        yaxis2=dict(
            overlaying='y',
            side='right',
            title='€ / (kg / a)',
            rangemode='tozero',
            hoverformat='.2r',
            showgrid=False,
        ),
        xaxis=dict(
            title='kWp',
            hoverformat='.2r',
        ),
        separators=', ',
        margin=dict(
            t=30,
            r=60,
            l=60,
        ),
        showlegend=True,
        legend=dict(x=0, y=1),
    )

    fig = dict(data=[t1, t2, t3], layout=layout)

    card = GraphCard(id='pv-summary', graph=dict(config=dict(displayModeBar='hover', responsive=False)))
    card.set_figure(fig)
    return html.Div([
        dbc.Row([
            dbc.Col([
                card.render()
            ], md=12),
        ]),
        dcc.Loading(id="loading-2", children=[
            html.Div(id="pv-details-placeholder")
        ], type="default")
    ])


@app.callback(
    Output('building-info-placeholder', 'children'),
    [
        Input('building-selector-dropdown', 'value'),
    ]
)
def building_base_info_callback(selected_building_id):
    datasets = dict(
        electricity_supply_emission_factor=calculate_electricity_supply_emission_factor()['EmissionFactor'],
    )

    if selected_building_id is None:
        el_s = datasets['electricity_supply_emission_factor']
        el_s = el_s.loc[el_s.index >= '2016']
        el_s = el_s.groupby(pd.Grouper(freq='d')).mean()
        trace = dict(
            type='scatter',
            y=el_s, x=el_s.index, mode='lines',
        )
        layout = make_layout(title='Sähkönhankinnan päästökerroin')
        fig = dict(data=[trace], layout=layout)

        card = GraphCard(id='electricity-supply-unit-emissions', graph=dict(config=dict(displayModeBar='hover')))
        card.set_figure(fig)

        return html.Div([
            dbc.Row([
                dbc.Col([card.render()]),
            ]),
        ])

    building = buildings_with_pv.loc[selected_building_id]

    samples = pd.read_parquet('data/nuuka/%s.parquet' % selected_building_id)
    samples = samples.query('time < "2019-01-01T00:00:00Z"')

    el_samples = samples[samples.sensor_id.isin(electricity_sensors.index)]
    el_samples = el_samples.groupby(['building_id', 'time']).value.sum().reset_index()
    el_samples = el_samples.set_index('time')
    el_samples['emissions'] = el_samples['value'].mul(datasets['electricity_supply_emission_factor'], axis=0, fill_value=0) / 1000

    dh_samples = samples[samples.sensor_id.isin(heating_sensors.index)].query('value < 30000')
    dh_samples = dh_samples.groupby(['building_id', 'time']).value.sum().reset_index()
    dh_samples = dh_samples.set_index('time')
    dh_samples['emissions'] = dh_samples['value'] * 200 / 1000

    group_freq = 'd'
    el_emissions = el_samples.emissions.groupby(pd.Grouper(freq=group_freq)).sum()

    t1 = dict(
        type='scatter',
        x=el_emissions.index,
        y=el_emissions,
        mode='lines',
        line=dict(width=0),
        stackgroup='one',
        name=_('Electricity consumption emissions'),
    )
    traces = [t1]

    if not dh_samples.empty:
        dh_emissions = dh_samples.emissions.groupby(pd.Grouper(freq=group_freq)).sum()

        t2 = dict(
            type='scatter',
            x=dh_emissions.index,
            y=dh_emissions,
            mode='lines',
            line=dict(width=0),
            stackgroup='one',
            name=_('Heat consumption emissions')
        )
        traces.append(t2)

    fig = dict(data=traces, layout=make_layout(
        title='Building energy consumption emissions: %s' % ' '.join(building.description.split(' ')[1:]),
        yaxis=dict(
            rangemode='normal',
            title='kg (CO₂e.)'
        ),
        xaxis=dict(
            fixedrange=False
        ),
        margin=dict(
            t=30,
            r=60,
            l=60,
        ),
        showlegend=True,
        legend=dict(
            x=0,
            y=1,
            bgcolor='#E2E2E2',
        ),
    ))

    card = GraphCard(id='building-all-emissions', graph=dict(config=dict(displayModeBar='hover', responsive=False)))
    card.set_figure(fig)
    return card.render()


@app.callback(
    Output('building-placeholder', 'children'),
    [
        Input('building-selector-dropdown', 'value'),
        Input('calculate-button', 'n_clicks'),
    ], [
        State('price-of-initial-installation', 'value'),
        State('marginal-price-of-peak-power', 'value'),
        State('price-of-purchased-electricity', 'value'),
        State('grid-output-percentage', 'value'),
        State('investment-years', 'value'),
    ]
)
def building_selector_callback(
    selected_building_id,
    n_clicks,
    price_of_initial_installation,
    marginal_price_of_peak_power,
    price_of_purchased_electricity,
    grid_output_percentage,
    investment_years
):
    print('callback')
    datasets = dict(
        yearly_solar_radiation_ratio=calculate_percentage_of_yearly_radiation(),
        electricity_supply_emission_factor=calculate_electricity_supply_emission_factor()['EmissionFactor'],
        electricity_spot_price=fingrid_price.purchase_price_of_production_imbalance_power,
    )

    variables = dict(
        price_of_initial_installation=price_of_initial_installation,
        marginal_price_of_peak_power=marginal_price_of_peak_power,
        price_of_purchased_electricity=price_of_purchased_electricity / 100,
        grid_output_percentage=grid_output_percentage / 100,
        investment_years=investment_years,
    )

    if selected_building_id is None:
        perc_sol = datasets['yearly_solar_radiation_ratio']
        trace = dict(y=perc_sol, x=perc_sol.index, mode='lines', type='scatter')
        layout = make_layout(title='Aurinkosäteily Kumpulassa')
        fig = dict(data=[trace], layout=layout)

        card = GraphCard(id='solar_radiation', graph=dict(config=dict(displayModeBar='hover')))
        card.set_figure(fig)

        return html.Div([
            dbc.Row([
                dbc.Col([card.render()]),
            ]),
        ])

    building = buildings_with_pv.loc[selected_building_id]

    df = pd.read_parquet('data/nuuka/%s.parquet' % selected_building_id)
    el_samples = df[df.sensor_id.isin(electricity_sensors.index)]
    el_samples = el_samples.groupby(['building_id', 'time']).value.sum().reset_index()

    sim = analyze_building(building, el_samples, None, variables, datasets)
    if sim is not None:
        out = html.Div([
            visualize_building_pv_summary(building, sim, variables)
        ])
    else:
        out = html.Div()

    return out


def translate_sum_col(n, unit=False):
    COLS = dict(
        SolarPeakPower='Järjestelmän huipputeho',
        SolarEnergyProduction='Vuosituotanto',
        BuildingEnergyConsumption='Rakennuksen vuosikulutus',
        GridInputReduction='Ostosähkön vähenemä',
        GridEnergyOutput='Sähkön tuotanto verkkoon',
        EnergySalesIncome='Tuotto sähkön myynnistä',
        EnergyCostSavings='Kustannussäästö',
        InstallationPrice='Investointikustannukset',
        NetCosts='Nettokustannukset',
        EmissionsReduction='Päästövähennykset',
        EmissionReductionCost='Päästövähennyksen nettokustannukset',
    )
    UNITS = dict(
        SolarPeakPower='kW',
        SolarEnergyProduction='MWh/a',
        BuildingEnergyConsumption='MWh/a',
        GridInputReduction='MWh/a',
        GridEnergyOutput='MWh/a',
        EnergySalesIncome='1 000 €/a',
        EnergyCostSavings='1 000 €/a',
        InstallationPrice='1 000 €',
        EmissionsReduction='kg (CO₂e.)/a',
        NetCosts='1 000 €/a',
        EmissionReductionCost='€/(kg/a)',
    )

    if not unit:
        return COLS[n]
    else:
        return UNITS[n]


@app.callback(
    Output('pv-details-placeholder', 'children'),
    [
        Input('pv-summary-graph', 'clickData'),
    ], [
        State('building-selector-dropdown', 'value'),
        State('price-of-initial-installation', 'value'),
        State('marginal-price-of-peak-power', 'value'),
        State('price-of-purchased-electricity', 'value'),
        State('grid-output-percentage', 'value'),
        State('investment-years', 'value'),
    ]
)
def pv_summary_graph_click(
    click_data,
    selected_building_id,
    price_of_initial_installation,
    marginal_price_of_peak_power,
    price_of_purchased_electricity,
    grid_output_percentage,
    investment_years
):
    print(click_data)
    if not click_data:
        return html.Div()
    perc = click_data['points'][0]['pointNumber']

    datasets = dict(
        yearly_solar_radiation_ratio=calculate_percentage_of_yearly_radiation(),
        electricity_supply_emission_factor=calculate_electricity_supply_emission_factor()['EmissionFactor'],
        electricity_spot_price=fingrid_price.purchase_price_of_production_imbalance_power,
    )

    variables = dict(
        price_of_initial_installation=price_of_initial_installation,
        marginal_price_of_peak_power=marginal_price_of_peak_power,
        price_of_purchased_electricity=price_of_purchased_electricity / 100,
        grid_output_percentage=grid_output_percentage / 100,
        investment_years=investment_years,
    )

    building = buildings_with_pv.loc[selected_building_id]

    df = pd.read_parquet('data/nuuka/%s.parquet' % selected_building_id)
    el_samples = df[df.sensor_id.isin(electricity_sensors.index)]
    el_samples = el_samples.groupby(['building_id', 'time']).value.sum().reset_index()

    res = analyze_building(building, el_samples, perc, variables, datasets)
    summary = res['summary']

    DIV_1000_COLS = (
        'SolarEnergyProduction', 'BuildingEnergyConsumption', 'GridInputReduction',
        'GridEnergyOutput', 'EnergySalesIncome', 'EnergyCostSavings', 'InstallationPrice',
        'NetCosts',
    )
    for col in DIV_1000_COLS:
        summary[col] /= 1000

    tbl = dash_table.DataTable(
        id='pv-details-table',
        columns=[{"name": [translate_sum_col(i), translate_sum_col(i, True)], "id": i} for i in summary.index],
        data=[summary.to_dict()],
        style_table={'overflowX': 'scroll'},
    )

    def fmt_val(x):
        s = '{0:.3}'.format(x)
        if 'e' in s:
            return '%d' % int(float(s))
        else:
            return s

    tbl = dash_table.DataTable(
        id='pv-details-table',
        columns=[{'name': '', 'id': 'name'}, {'name': '', 'id': 'value'}, {'name': 'Yksikkö', 'id': 'unit'}],
        data=[dict(name=translate_sum_col(key), value=fmt_val(val), unit=translate_sum_col(key, True)) for key, val in summary.items()],
    )

    df = res['simulated']

    t1 = dict(
        x=df.index,
        y=-df.Consumption,
        mode='lines',
        line=dict(width=0),
        stackgroup='one',
        name='Kiinteistön sähkönkulutus',
        type='scatter',
    )
    t2 = dict(
        x=df.index,
        y=df.PanelProduction,
        mode='lines',
        line=dict(width=0),
        stackgroup='one',
        name='Aurinkosähköjärjestelmän tuotanto',
        type='scatter',
    )

    fig = dict(data=[t1, t2], layout=make_layout(
        title='Simuloitu aurinkosähköjärjestelmä',
        yaxis=dict(
            rangemode='normal',
            title='kWh'
        ),
        xaxis=dict(
            fixedrange=False
        ),
        margin=dict(
            t=30,
            r=60,
            l=60,
        ),
        showlegend=True,
        legend=dict(
            x=0,
            y=1,
            bgcolor='#E2E2E2',
        ),
    ))

    card = GraphCard(id='simulated-pv-time-series', graph=dict(config=dict(displayModeBar='hover')))
    card.set_figure(fig)

    return html.Div(children=[
        html.Div(children=tbl, className='mb-4'),
        html.Div(children=card.render()),
    ])


if __name__ == '__main__':
    # Write the process pid to a file for easier profiling with py-spy
    with open('.helbuildings.pid', 'w') as pid_file:
        pid_file.write(str(os.getpid()))
    app.run_server(debug=True, port=8123)
