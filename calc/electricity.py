from datetime import timedelta
import pandas as pd

from utils.data import find_consecutive_start

from . import calcfunc
from .population import predict_population
from .solar_power import predict_solar_power_production


@calcfunc(
    variables=['municipality_name', 'target_year'],
    datasets=dict(
        ghg_emissions='jyrjola/hsy/pks_khk_paastot',
    )
)
def predict_electricity_emission_factor(variables, datasets):
    df = datasets['ghg_emissions']
    df = df[df.Kaupunki == variables['municipality_name']].drop(columns='Kaupunki')
    df = df[df.Sektori1 == 'Sähkö']
    df['EmissionFactor'] = df['Päästöt'] / df['Energiankulutus'] * 1000
    s = df.groupby('Vuosi')['EmissionFactor'].mean()
    df = pd.DataFrame(s)

    """
    PAST_VALUES = [
        214.60, 261.20, 285.80, 349.80, 298.30, 205.00, 307.90, 278.50, 214.40, 229.10,
        269.80, 226.90, 166.90, 199.90, 173.10, 134.90, 146.00, 131.40
    ]
    START_YEAR = 2000

    df = pd.DataFrame(
        PAST_VALUES,
        index=range(START_YEAR, START_YEAR + len(PAST_VALUES)),
        columns=['EmissionFactor']
    )
    """

    df['Forecast'] = False
    start_year = find_consecutive_start(df.index)
    df = df.reindex(pd.Index(range(start_year, variables['target_year'] + 1)))
    df.Forecast = df.Forecast.fillna(True)
    df.loc[2030, 'EmissionFactor'] = 70  # g CO2e/kWh
    df.loc[2035, 'EmissionFactor'] = 45  # g CO2e/kWh

    df['EmissionFactor'] = df['EmissionFactor'].interpolate()

    return df


@calcfunc(
    variables=['municipality_name'],
    datasets=dict(
        energy_consumption='jyrjola/ymparistotilastot/e03_energian_kokonaiskulutus'
    )
)
def prepare_electricity_consumption_dataset(variables, datasets):
    df = datasets['energy_consumption']
    muni_name = variables['municipality_name']
    df = df[df.Alue == muni_name]
    df = df[df.Sektori == 'Kulutussähkö']
    df = df[df.Muuttuja == 'Kokonaiskulutus (GWh)']
    df = df.rename(columns=dict(Vuosi='Year'))
    df['Year'] = df.Year.astype(int)
    s = df.set_index('Year')['value']
    s.name = 'ElectricityConsumption'
    return s


@calcfunc(
    variables=['target_year', 'electricity_consumption_per_capita_adjustment'],
    funcs=[prepare_electricity_consumption_dataset, predict_population],
)
def predict_electricity_consumption(variables):
    pop_df = predict_population()
    target_year = variables['target_year']

    el_s = prepare_electricity_consumption_dataset()
    el_per_capita = (el_s / pop_df['Population']).dropna()
    el_per_capita *= 1000000  # GWh to kWh

    last_year = el_per_capita.index.max()
    per_capita_adj = variables['electricity_consumption_per_capita_adjustment']

    """
    # Do a logarithmic regression
    s = np.log(el_per_capita)

    # Look at the last 10 years
    rs = s.loc[s.index >= s.index.max() - 10]
    res = scipy.stats.linregress(rs.index, rs)

    last_year = s.index.max()
    last_val = s.loc[last_year]
    for year_idx in range(1, target_year - last_year + 1):
        year = last_year + year_idx
        per_capita_log = last_val + res.slope * year_idx
        s.loc[year] = per_capita_log

    for year_idx in range(last_year)

    s = np.exp(s)
    """
    last_per = el_per_capita[last_year]
    for year in range(last_year + 1, target_year + 1):
        last_per *= 1 + (per_capita_adj / 100)
        el_per_capita.loc[year] = last_per

    el_per_capita.name = 'ElectricityConsumptionPerCapita'

    df = pd.DataFrame(el_per_capita)
    df.name = 'Electricity consumption'
    df['ElectricityConsumption'] = el_s
    df['Population'] = pop_df['Population']
    df['Forecast'] = False
    df.loc[df.index > last_year, 'Forecast'] = True

    df.loc[df.Forecast, 'ElectricityConsumption'] = df['Population'] * df['ElectricityConsumptionPerCapita'] / 1000000
    df = df.dropna()
    return df


@calcfunc(
    datasets=dict(
        et_hourly='jyrjola/energiateollisuus/electricity_production_hourly',
        et_fuels='jyrjola/energiateollisuus/electricity_production_fuels'
    ),
    variables=['bio_emission_factor'],
)
def calculate_electricity_production_emissions(datasets, variables):
    et_fuels = datasets['et_fuels']
    df = et_fuels.copy()
    df['FuelEmissionFactor'] = df.Fuel.map({
        'Bio': 112 * (variables['bio_emission_factor'] / 100),
        'Coal': 106.0 * 0.99,
        'Oil': 79.2,
        'Natural gas': 55.3,
        'Peat': 107.6 * 0.99,
        'Other': 31.8 * 0.99
    })
    df['Emissions'] = df['FuelEmissionFactor'] * df['FuelUse'] / 1000

    df = df.groupby(['Date', 'Method'])[['Production', 'Emissions']].sum()
    df['EmissionFactor'] = df['Emissions'] / df['Production'] * 1000
    df = df['EmissionFactor'].unstack('Method')
    df.index += timedelta(days=14)
    df = df.resample('h').mean().interpolate()
    df.index = df.index.tz_localize('Europe/Helsinki', nonexistent='NaT', ambiguous='NaT')
    df = df.loc[df.index.notnull()]

    return df


@calcfunc(
    datasets=dict(
        et_hourly='jyrjola/energiateollisuus/electricity_production_hourly',
    ),
    funcs=[calculate_electricity_production_emissions]
)
def calculate_electricity_supply_emission_factor(datasets):
    df = datasets['et_hourly'].copy()

    hourly_emission_factors = calculate_electricity_production_emissions()
    chp_emissions = df[['CHP-Industry', 'CHP-District heating']].mul(hourly_emission_factors['CHP'], axis=0).dropna()
    separate_thermal_emissions = df['Separate Thermal Power'].mul(hourly_emission_factors['Separate Thermal'], axis=0).dropna()

    supply_emissions = chp_emissions.sum(axis=1) + separate_thermal_emissions
    df['Emissions'] = supply_emissions
    df['EmissionFactor'] = supply_emissions.div(df['Production'] + df['Import'], axis=0)
    return df


@calcfunc(
    funcs=[
        predict_electricity_consumption,
        predict_electricity_emission_factor,
        predict_solar_power_production,
    ]
)
def predict_electricity_consumption_emissions():
    cdf = predict_electricity_consumption()
    udf = predict_electricity_emission_factor()
    sdf = predict_solar_power_production()
    cdf['EmissionFactor'] = udf['EmissionFactor']
    cdf['SolarProduction'] = sdf['SolarProduction'][sdf.Forecast]
    cdf['SolarProduction'].fillna(0, inplace=True)
    cdf['NetConsumption'] = cdf['ElectricityConsumption'] - cdf['SolarProduction']

    cdf['Emissions'] = cdf['ElectricityConsumption'] * cdf['EmissionFactor'] / 1000
    cdf['SolarEmissionReductions'] = cdf['SolarProduction'] * cdf['EmissionFactor'] / 1000
    cdf['NetEmissions'] = cdf['Emissions'] - cdf['SolarEmissionReductions']
    cdf.index.name = 'Year'

    return cdf


if __name__ == '__main__':
    print(predict_electricity_consumption_emissions())
    # print(calculate_electricity_supply_emission_factor())
