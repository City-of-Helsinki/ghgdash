import pandas as pd
import scipy.stats

from . import calcfunc
from .population import get_adjusted_population_forecast


def generate_forecast_series(historical_series, year_until):
    s = historical_series
    start_year = s.index.min()
    res = scipy.stats.linregress(s.index, s)

    years = list(range(start_year, year_until + 1))
    predictions = pd.Series([res.intercept + res.slope * year for year in years], index=years)
    return predictions


@calcfunc(
    datasets=dict(
        buildings='jyrjola/aluesarjat/a01s_hki_rakennuskanta',
    )
)
def prepare_historical_building_area_dataset(datasets):
    df = datasets['buildings']
    df = df.loc[df.Alue == '091 Helsinki'].drop(columns='Alue')
    df = df.loc[df.Valmistumisvuosi != 'Yhteensä'].copy()
    df = df.rename(columns={'Käyttötarkoitus ja kerrosluku': 'Käyttötarkoitus'})
    df = df[~df['Käyttötarkoitus'].str.contains('yhteensä')]
    df = df[df['Käyttötarkoitus'] != 'Kaikki rakennukset']

    return df


@calcfunc(
    variables=dict(
        target_year='target_year',
    ),
    funcs=[prepare_historical_building_area_dataset, get_adjusted_population_forecast]
)
def generate_building_floor_area_forecast(variables):
    target_year = variables['target_year']

    df = prepare_historical_building_area_dataset()
    building_total = df.groupby(['Käyttötarkoitus', 'Vuosi']).sum()\
        .unstack('Käyttötarkoitus').dropna(axis=1, how='all')

    building_total.index = building_total.index.astype(int)
    building_total.columns = list(building_total.columns.get_level_values(1))

    pop_s = get_adjusted_population_forecast().Population
    # Replace negative population change with zero so that we don't
    # start bulldozing buildings.
    pop_diff = pop_s.diff().clip(lower=0).dropna()

    newly_built = building_total.diff().dropna()
    df = newly_built.div(pop_diff, axis=0).dropna()
    df = df.loc[df.index >= df.index.max() - 10]  # look at the last 10 years
    new_area_per_capita = df.mean()

    # Make the forecast of newly-built building net area by multiplying
    # the forecast of the yearly population increase by the amount of
    # new building area per capita.
    forecast_years = range(newly_built.index.max() + 1, target_year + 1)
    df = pd.DataFrame([new_area_per_capita] * len(forecast_years), index=forecast_years)
    building_forecast = df.multiply(pop_diff, axis=0).dropna()

    building_forecast.iloc[0] += building_total.iloc[-1]
    df = pd.concat([building_total, building_forecast.cumsum()], sort=True)

    df.index.name = 'Year'
    df['Forecast'] = False
    df.loc[df.index >= forecast_years[0], 'Forecast'] = True

    df['Asuinkerrostalot'] = df['Asuinkerrostalot alle 4 kerrosta'] + df['Asuinkerrostalot 4 + kerrosta']
    df = df.drop(columns=['Asuinkerrostalot alle 4 kerrosta', 'Asuinkerrostalot 4 + kerrosta'])

    return df


@calcfunc(
    datasets=dict(
        energy_use='jyrjola/ymparistotilastot/e12_helsingin_kaukolammon_sahkonkulutus',
        building_stock='jyrjola/aluesarjat/a01s_hki_rakennuskanta'
    ),
    variables=['municipality_name', 'target_year', 'district_heating_existing_building_efficiency_change']
)
def generate_heat_use_per_net_area_forecast_existing_buildings(variables, datasets):
    assert variables['municipality_name'] == 'Helsinki'

    bdf = datasets['building_stock'].query('Alue == "091 Helsinki" & Yksikkö == "Kerrosala"')
    bdf = bdf.loc[bdf['Käyttötarkoitus ja kerrosluku'] == "Kaikki rakennukset"]
    net_area = bdf.query('Valmistumisvuosi == "Yhteensä"').set_index('Vuosi').value

    muni_energy_use = datasets['energy_use'].query('Kunta == "Helsinki" & Energiamuoto == "Kaukolämpö"')\
        .drop(columns=['Energiamuoto', 'Kunta'])
    edf = muni_energy_use
    edf = edf.loc[edf.Sektori.isin(['Ominaiskulutus sääkorjaamaton (kWh/m3)', 'Ominaiskulutus sääkorjattu (kWh/m3)'])]
    edf = edf.pivot(index='Vuosi', columns='Sektori', values='value').dropna()
    heating_need_correction_factor = edf['Ominaiskulutus sääkorjattu (kWh/m3)'] / edf['Ominaiskulutus sääkorjaamaton (kWh/m3)']

    heat_use = muni_energy_use.query('Sektori == "Kulutus yhteensä (GWh)"').set_index('Vuosi').value
    heat_use *= 1000000  # convert to kWh

    # FIXME: Käytä keskiarvoistettua ominaislämmönkulutusta
    heat_use_per_net_area = heat_use.div(net_area, axis='index').dropna()
    heat_use_per_net_area.name = 'HeatUsePerNetArea'
    df = pd.DataFrame(heat_use_per_net_area)
    df['Forecast'] = False
    df.index = df.index.astype(int)
    df = df.reindex(range(df.index.min(), variables['target_year'] + 1))
    df.loc[df.Forecast != False, 'Forecast'] = True

    change_perc = variables['district_heating_existing_building_efficiency_change']
    df['HeatUsePerNetArea'] = df['HeatUsePerNetArea'].fillna(heat_use_per_net_area.iloc[-1])
    first_forecast_year = df[df.Forecast].index.min()
    for year in df[df.Forecast].index:
        factor = (1 + (change_perc / 100)) ** (year - first_forecast_year + 1)
        df.loc[year, 'HeatUsePerNetArea'] *= factor

    return df


@calcfunc(
    variables=['target_year', 'district_heating_new_building_efficiency_change']
)
def generate_heat_use_per_net_area_forecast_new_buildings(variables):
    target_year = variables['target_year']

    heat_use_per_net_area = 95
    start_year = 2018
    years = range(start_year, target_year + 1)

    vals = []
    change_perc = variables['district_heating_new_building_efficiency_change']

    for year in years:
        factor = (1 + (change_perc / 100)) ** (year - start_year + 1)
        vals.append(heat_use_per_net_area * factor)

    return pd.Series(vals, index=years)


if __name__ == '__main__':
    print(generate_building_floor_area_forecast() / 1000000)
    print(generate_heat_use_per_net_area_forecast_existing_buildings())
