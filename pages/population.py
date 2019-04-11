import pandas as pd
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash.dependencies import Input, Output

from variables import get_variable, set_variable
from utils.quilt import load_datasets
from . import page_callback, Page


INPUT_DATASETS = [
    'jyrjola/aluesarjat/hginseutu_va_ve01_vaestoennuste_pks',
]
population_forecast = None


# Adjusted datasets
def get_population_forecast():
    correction_perc = get_variable('population_forecast_correction')
    target_year = get_variable('target_year')

    df = population_forecast[population_forecast.index <= target_year].copy()
    forecast = df.loc[df.Forecast]
    n_years = forecast.index.max() - forecast.index.min()
    base = (1 + (correction_perc / 100)) ** (1 / n_years)
    multipliers = [base ** year for year in range(n_years + 1)]
    m_series = pd.Series(multipliers, index=forecast.index)
    df.loc[df.Forecast, 'Population'] *= m_series
    df.Population = df.Population.astype(int)
    return df


def prepare_population_forecast_dataset(df):
    df = df.copy()
    df.Vuosi = df.Vuosi.astype(int)
    df.value = df.value.astype(int)
    df.loc[df.Vuosi <= 2018, 'Forecast'] = False
    df.loc[df.Vuosi > 2018, 'Forecast'] = True
    df = df.query("""
        Alue == '{municipality}' & Laadintavuosi == 'Laadittu 2018' &
        Vaihtoehto == 'Perusvaihtoehto' & Sukupuoli == 'Molemmat sukupuolet'
    """.replace('\n', '').format(municipality=get_variable('municipality_name')))
    df = df.set_index('Vuosi')
    df = df.query("Ikä == 'Väestö yhteensä'")[['value', 'Forecast']].copy()
    df.rename(columns=dict(value='Population'), inplace=True)
    return df


def process_input_datasets():
    global population_forecast

    pop_in = load_datasets(INPUT_DATASETS)
    population_forecast = prepare_population_forecast_dataset(pop_in)


def generate_population_forecast_graph(pop_df):
    hist_df = pop_df.query('~Forecast')
    hist = go.Scatter(
        x=hist_df.index,
        y=hist_df.Population,
        mode='lines',
        name='Väkiluku',
        line=dict(
            color='#9fc9eb',
        )
    )

    forecast_df = pop_df.query('Forecast')
    forecast = go.Scatter(
        x=forecast_df.index,
        y=forecast_df.Population,
        mode='lines',
        name='Väkiluku (enn.)',
        line=dict(
            color='#9fc9eb',
            dash='dash'
        )
    )
    fig = go.Figure(data=[hist, forecast])
    return fig


  
population_page_content = dbc.Container([
    dbc.Card([
      dbc.CardHeader(children=[
          'Väestön määrä vuonna %s: ' % get_variable('target_year'),
          html.Strong(id='population-count-target-year')]),
      dbc.CardBody([
        dcc.Graph(
            id='population-graph',
            config={
                'displayModeBar': False,
                'showLink': False,
            }
        ),
      ]),
      dbc.CardFooter(children=[
        html.H6('Väestöennusteen korjausprosentti'),
        html.Div(children=[
            dcc.Slider(
                id='population-slider',
                min=-20,
                max=20,
                step=5,
                value=0,
                marks={x: '%d %%' % x for x in range(-20, 20 + 1, 5)},
            ),
        ],style=dict(padding='0 1em 2em')),
      ]),
    ]),
])


@page_callback(
    [Output('population-graph', 'figure'), Output('population-count-target-year', 'children')],
    [Input('population-slider', 'value')])
def population_callback(value):
    set_variable('population_forecast_correction', value)
    pop_df = get_population_forecast()
    pop_in_target_year = pop_df.loc[[get_variable('target_year')]].Population
    fig = generate_population_forecast_graph(pop_df)

    return fig, pop_in_target_year.round()


process_input_datasets()
page = Page('Väestö', population_page_content, [population_callback])
