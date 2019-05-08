import dash_table
import dash_daq as daq
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objs as go
from dash_table.Format import Format, Scheme
from dash.dependencies import Input, Output

from calc.district_heating import calc_district_heating_unit_emissions_forecast
from variables import get_variable, set_variable
from . import page_callback, Page


def generate_district_heating_forecast_graph(df):
    s = df['District heat consumption emissions']
    trace = go.Bar(x=s.index, y=s)
    layout = go.Layout(
        title='Kaukolämmön kulutuksen päästöt',
        yaxis=dict(
            title='kt CO2e',
            hoverformat='.3r',
        ),
        margin=go.layout.Margin(
            t=0,
            r=15,
            l=40,
        ),
    )

    return go.Figure(
        data=[trace],
        layout=layout
    )


def generate_production_mix_graph(df):
    last_year = df.loc[df.index.max()]
    last_year = last_year.map(lambda x: np.nan if x < 1 else x).round()
    trace = go.Pie(
        labels=last_year.index,
        values=last_year,
        hole=0.6,
        sort=False,
        hovertemplate='%{label}<br />%{value} GWh<br />%{percent}'
    )
    layout = go.Layout(
        title=str(last_year.name),
        margin=go.layout.Margin(
            t=0,
            r=15,
            l=40,
        ),
    )

    return go.Figure(
        data=[trace],
        layout=layout
    )


def generate_district_heating_forecast_table(df):
    last_hist_year = df[~df.Forecast].index.max()
    df.index.name = 'Year'

    data_columns = list(df.columns)
    data_columns.remove('Forecast')
    data_columns.insert(0, 'Year')

    last_forecast_year = df[df.Forecast].index.max()
    table_df = df.loc[df.index.isin([last_hist_year, last_forecast_year - 5, last_forecast_year - 10, last_forecast_year])]
    table_data = table_df.reset_index().to_dict('rows')
    table_cols = []
    for col_name in data_columns:
        col = dict(id=col_name, name=col_name)
        if col_name == 'Year':
            pass
        else:
            col['type'] = 'numeric'
            col['format'] = Format(precision=0, scheme=Scheme.fixed)
        table_cols.append(col)
    table = dash_table.DataTable(
        data=table_data,
        columns=table_cols,
        style_cell={
            'minWidth': '0px', 'maxWidth': '70px',
            'whiteSpace': 'normal'
        },
        css=[{
            'selector': '.dash-cell div.dash-cell-value',
            'rule': 'display: inline; white-space: inherit; overflow: inherit; text-overflow: inherit;'
        }],
        style_header={
            'fontWeight': 'bold'
        },
        style_cell_conditional=[
            {
                'if': {'column_id': 'Year'},
                'fontWeight': 'bold',
            }
        ]
    )
    return table


ratio_sliders = []


def generate_ratio_sliders():
    ratios = get_variable('district_heating_target_production_ratios')
    eles = []
    for method, ratio in ratios.items():
        header = html.H5(method, className='mt-4')
        slug = method.lower().replace(' ', '_')
        slider = dcc.Slider(
            id='district-heating-%s' % slug,
            max=100,
            min=0,
            step=5,
            value=ratio,
        )
        slider.method = method
        ratio_sliders.append(slider)
        eles.append(header)
        eles.append(slider)
    return eles


district_heat_page_content = dbc.Row([
    dbc.Col([
        dcc.Graph(id='district-heating-graph'),
        html.Div(id='district-heating-table-container'),
    ], md=8),
    dbc.Col([
        html.H5('Biopolttoaine päästötöntä'),
        daq.ToggleSwitch(
            id='district-heating-emissionless-bio',
            value=get_variable('bio_is_emissionless')
        ),
        html.H5('Kaukolämmön kulutus', className='mt-4'),
        dcc.Slider(
            id='district-heating-demand-slider',
            min=-50,
            max=50,
            step=5,
            value=0,
            marks={x: '%d %%' % x for x in range(-50, 50 + 1, 25)},
        ),
        *generate_ratio_sliders(),
        html.H5('Tuotantotapaosuudet 2035', className='mt-4'),
        dcc.Graph(id='district-heating-production-source-graph'),
    ], md=4),
])


@page_callback(
    [
        Output('district-heating-graph', 'figure'),
        Output('district-heating-table-container', 'children'),
        Output('district-heating-production-source-graph', 'figure'),
    ], [
        Input('district-heating-demand-slider', 'value'),
        Input('district-heating-emissionless-bio', 'value'),
        *[Input(s.id, 'value') for s in ratio_sliders]
    ]
)
def district_heating_callback(demand_value, emissionless_bio, *args):
    set_variable('district_heating_target_demand_change', demand_value)
    set_variable('bio_is_emissionless', emissionless_bio)

    ratios = get_variable('district_heating_target_production_ratios')

    total_sum = sum(args)
    shares = [val / total_sum for val in args]

    for slider, share in zip(ratio_sliders, shares):
        ratios[slider.method] = int(share * 100)

    print(ratios)
    diff = 100 - sum(ratios.values())
    ratios[list(ratios.keys())[0]] += diff

    set_variable('district_heating_target_production_ratios', ratios)

    production_stats, production_source = calc_district_heating_unit_emissions_forecast()
    fig = generate_district_heating_forecast_graph(production_stats)
    table = generate_district_heating_forecast_table(production_stats)

    fuel_fig = generate_production_mix_graph(production_source)

    return fig, table, fuel_fig


page = Page('Kaukolämpö', district_heat_page_content, [district_heating_callback])
