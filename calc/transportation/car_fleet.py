import numpy as np
import pandas as pd
import scipy.optimize
from calc import calcfunc
from calc.population import (
    prepare_population_forecast_dataset, predict_population
)
from calc.transportation.parking import predict_parking_fee_impact


ENGINE_TYPE_MAP = {
    'Bensiini': 'gasoline',
    'Bensiini/CNG': 'gasoline',
    'Bensiini/Etanoli': 'gasoline',
    'Bensiini/Sähkö (ladattava hybridi)': 'PHEV/gasoline',
    'Diesel/Sähkö (ladattava hybridi)': 'PHEV/diesel',
    'Diesel': 'diesel',
    'Sähkö': 'BEV',
}


@calcfunc(
    datasets=dict(
        newly_registered_cars='jyrjola/traficom/tf020_ensirek_tau_102',
    ),
    variables=['municipality_name'],
)
def prepare_newly_registered_cars(variables, datasets):
    df = datasets['newly_registered_cars'].copy()
    df.Vuosi = df.Vuosi.astype(int)
    df.Käyttövoima = df.Käyttövoima.map(lambda x: ENGINE_TYPE_MAP.get(x, 'other'))
    assert len(df.Käyttövoima.unique()) > 3
    df = df.rename(columns=dict(Käyttövoima='EngineType', Vuosi='Year'))
    df = df[df.Alue == variables['municipality_name']].groupby(['EngineType', 'Year'])['value'].sum()
    df = df.unstack('EngineType').fillna(0)
    return df


@calcfunc(
    datasets=dict(
        cars_per_resident='jyrjola/ymparistotilastot/l10_autotiheys'
    ),
    variables=['municipality_name'],
    funcs=[prepare_population_forecast_dataset, prepare_newly_registered_cars],
)
def prepare_cars_per_resident_dataset(variables, datasets):
    df = datasets['cars_per_resident']
    df = df[df.Kunta == variables['municipality_name']]
    df = df[df.Muuttuja == 'Liikennekäytössä olevat hlö autot (kpl)']
    df = df[['Vuosi', 'value']].rename(columns=dict(Vuosi='Year', value='NumberOfCars'))
    df.Year = df.Year.astype(int)
    df = df.set_index('Year')

    pop_df = prepare_population_forecast_dataset()
    df['CarsPerResident'] = df['NumberOfCars'].div(pop_df['Population'], axis=0)

    new_df = prepare_newly_registered_cars()
    total = new_df.sum(axis=1)
    df['NewlyRegisteredCars'] = total
    df['YearlyTurnover'] = df['NewlyRegisteredCars'] / df['NumberOfCars']

    return df


@calcfunc(
    datasets=dict(
        cars_in_use='jyrjola/traficom/tf010_kanta_tau_101',
    ),
    variables=['municipality_name'],
)
def prepare_cars_in_use_dataset(variables, datasets):
    df = datasets['cars_in_use']
    df = df[df.Alue == variables['municipality_name']].drop(columns='Alue')

    df = df[df.Käyttöönottovuosi != 'Yhteensä']
    df.Käyttöönottovuosi = df.Käyttöönottovuosi.map(lambda x: x if x != '1959 ja ennen' else '1959').astype(int)

    df = df[df.Käyttövoima != 'Yhteensä']
    df = df.rename(columns=dict(Käyttövoima='EngineType', Käyttöönottovuosi='Year'))
    df.EngineType = df.EngineType.map(lambda x: ENGINE_TYPE_MAP.get(x, 'other'))
    df = df.groupby(['Year', 'EngineType'])['value'].sum()
    df = df.unstack('EngineType').fillna(0)
    df = df.sort_index()
    return df


@calcfunc(
    variables=['target_year'],
    funcs=[
        prepare_cars_per_resident_dataset,
        prepare_cars_in_use_dataset,
        predict_population
    ]
)
def predict_cars_in_use(variables):
    pop_df = predict_population()
    df = prepare_cars_per_resident_dataset()

    last_hist_year = df.index.max()
    last_5_years = df.iloc[-6:-1]
    df = df.reindex(range(df.index.min(), variables['target_year'] + 1))
    df['Population'] = pop_df['Population']
    df.loc[df.index.max(), 'CarsPerResident'] = last_5_years['CarsPerResident'].mean()
    df.loc[df.index.max(), 'YearlyTurnover'] = last_5_years['YearlyTurnover'].mean()
    df['CarsPerResident'] = df['CarsPerResident'].interpolate()
    df['YearlyTurnover'] = df['YearlyTurnover'].interpolate()
    s = df['Population'] * df['CarsPerResident']
    df.loc[df.index > last_hist_year, 'NumberOfCars'] = s
    df['NumberOfCars'] = df['NumberOfCars'].astype(int)
    s = df['NumberOfCars'] * df['YearlyTurnover']
    df.loc[df.index > last_hist_year, 'NewlyRegisteredCars'] = s
    df['NewlyRegisteredCars'] = df['NewlyRegisteredCars'].astype(int)
    df['Forecast'] = False
    df.loc[df.index > last_hist_year, 'Forecast'] = True

    return df


def fsigmoid(x, a, b, saturation_level=1.0):
    return (1.0 / (1.0 + np.exp(-a * (x - b)))) * saturation_level


def predict_sigmoid(s, start_year, target_year, saturation_level=1.0):
    x0 = s.index.min()
    x = list(s.index - x0)
    y = list(s.values)

    def sigmoid_fit(guess):
        a, b = guess
        return y - fsigmoid(x, a, b, saturation_level)

    res = scipy.optimize.least_squares(
        sigmoid_fit, (0.5, 5), bounds=((-1, -1), (5, 50))
    )
    a, b = res.x

    x = np.array(range(start_year - x0, target_year - x0 + 1))
    out = fsigmoid(x, a, b, saturation_level)

    x += x0
    pred = pd.Series(out, index=x)

    return pred


@calcfunc(
    variables=['target_year', 'share_of_ev_charging_station_demand_built'],
    funcs=[
        predict_cars_in_use,
        prepare_newly_registered_cars,
        predict_population,
        predict_parking_fee_impact,
    ]
)
def predict_newly_registered_cars(variables):
    target_year = variables['target_year']
    nr_cars = predict_cars_in_use()

    df = prepare_newly_registered_cars().copy()
    df['PHEV'] = df.pop('PHEV/diesel') + df.pop('PHEV/gasoline')

    total = df.sum(axis=1)
    df = df.div(total, axis=0)
    last_hist_year = df.index.max()

    ev_total = df['PHEV'] + df['BEV']
    ev_total_pred = predict_sigmoid(ev_total.tail(10), last_hist_year + 1, target_year)

    s = df['BEV'].tail(10)

    pdf = predict_parking_fee_impact()
    # subsidies for 10 years
    extra_subsidy = pdf[pdf.Forecast]['ParkingSubsidyForEVs'][0:10].sum()
    # Take the subsidies into account based on the EV Policy Modelling Tool
    s[2027] = .194 + (min(extra_subsidy, 8000) / 8000) * .083
    s[2035] = .449 + (min(extra_subsidy, 8000) / 8000) * .134

    stations_built_perc = variables['share_of_ev_charging_station_demand_built']

    # Amount of EV charging stations impact from the EV Policy Modelling Tool
    s[2027] += (stations_built_perc / 100) * 0.063
    s[2035] += (stations_built_perc / 100) * 0.123

    bev_pred = predict_sigmoid(s, last_hist_year + 1, target_year)

    df = df.reindex(range(df.index.min(), target_year + 1))
    df.loc[df.index > last_hist_year, 'BEV'] = bev_pred

    df['EV Total'] = ev_total
    df.loc[df.index > last_hist_year, 'EV Total'] = ev_total_pred

    df.loc[df.index > last_hist_year, 'PHEV'] = (df['EV Total'] - df['BEV']).clip(lower=0)

    bev = df.pop('BEV')
    phev = df.pop('PHEV')
    df.pop('EV Total')
    rest = 1 - (bev + phev)

    df = df.div(rest, axis=0)
    df = df.fillna(method='pad')
    df = df.mul(rest, axis=0)
    df['BEV'] = bev
    df['PHEV'] = phev

    df = df.mul(nr_cars['NewlyRegisteredCars'], axis=0).dropna()
    df = df.astype(int)
    df['Forecast'] = False
    df.loc[df.index > last_hist_year, 'Forecast'] = True

    return df


@calcfunc(
    funcs=[
        prepare_cars_in_use_dataset,
        predict_newly_registered_cars,
        predict_cars_in_use
    ],
    variables=['target_year'],
)
def predict_cars_in_use_by_engine_type(variables):
    df = prepare_cars_in_use_dataset()
    in_use = predict_cars_in_use()

    df['PHEV'] = df.pop('PHEV/diesel') + df.pop('PHEV/gasoline')

    # Lump all cars made before 1992 (Euro 1) together
    df.loc[1992] += df.loc[df.index < 1992].sum(axis=0)
    df = df.loc[df.index >= 1992]

    # Lose the last year because it is not complete data
    cars_by_model_year = df.iloc[:-1].copy()
    cars_by_model_year.index.name = 'ModelYear'
    s = cars_by_model_year.stack()
    s.name = df.index.max()
    cars_by_model_year = pd.DataFrame(s).T

    df = df.cumsum().tail(1)
    total = df.sum(axis=1)
    df = df.div(total, axis=0)

    # Predict starting point
    df = df.mul(in_use['NumberOfCars'], axis=0).dropna().astype(int)

    new_df = predict_newly_registered_cars()

    in_use['FleetChange'] = in_use['NumberOfCars'].diff().shift(-1)
    in_use['RemoveOld'] = in_use['NewlyRegisteredCars'] - in_use['FleetChange']

    last_hist_year = df.index.max()
    current_cars = df.loc[last_hist_year]
    df = df.reindex(range(df.index.min(), variables['target_year'] + 1))
    new_df.pop('Forecast')

    for year in range(last_hist_year + 1, df.index.max() + 1):
        remove_old = in_use['RemoveOld'][year - 1]
        new_cars = new_df.loc[year - 1]

        # cars_by_model_year.loc[year - 1] = new_cars
        last_year = cars_by_model_year.loc[year - 1].unstack('EngineType')

        current_cars += new_cars
        for model_year in range(last_year.index.min(), last_year.index.max()):
            row = last_year.loc[model_year]
            if not row.sum():
                continue
            to_remove = ((row / row.sum()) * remove_old).astype(int)
            to_remove = row - (row - to_remove).clip(lower=0)

            current_cars = current_cars.sub(to_remove, axis=0)
            remove_old -= to_remove.sum()
            last_year.loc[model_year] = last_year.loc[model_year].sub(to_remove)
            if remove_old <= 1:
                break

        df.loc[year] = current_cars
        cars_by_model_year.loc[year] = last_year.stack('EngineType')
        for key in cars_by_model_year.columns.levels[1]:
            cars_by_model_year.loc[year, (year - 1, key)] = new_cars[key]

    return cars_by_model_year


@calcfunc(
    funcs=[
        predict_cars_in_use_by_engine_type
    ],
    variables=['share_of_ev_charging_station_demand_built'],
)
def predict_ev_charging_station_demand(variables):
    df = predict_cars_in_use_by_engine_type()
    df = df.sum(axis=1, level='EngineType')
    bev = df.pop('BEV') * 0.10
    df = pd.DataFrame(bev.values, index=bev.index, columns=['Demand'])
    df['Built'] = df['Demand'] * variables['share_of_ev_charging_station_demand_built'] / 100
    df = df.astype(int)
    df['Forecast'] = True
    return df


if __name__ == '__main__':
    # pd.set_option('display.max_rows', None)
    # df = predict_cars_in_use(skip_cache=True)
    df = predict_newly_registered_cars(skip_cache=True)
    #print(df.sum(axis=1, level='EngineType'))
    exit()
