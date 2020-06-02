import pandas as pd
from . import calcfunc
from .bass import generate_bass_diffusion
from .population import get_adjusted_population_forecast
from .electricity import predict_electricity_emission_factor


@calcfunc(
    datasets=dict(
        emissions='jyrjola/lipasto/emissions_by_municipality',
    ),
    variables=[
        'municipality_name'
    ]
)
def prepare_car_emissions_dataset(datasets, variables):
    df = datasets['emissions']
    df = df[df.Municipality == 'Helsinki'].copy()
    df.Vehicle = df.Vehicle.astype('category')
    df.Road = df.Road.astype('category')
    return df


@calcfunc(
    variables=[
        'target_year', 'municipality_name', 'cars_mileage_per_resident_adjustment'
    ],
    funcs=[get_adjusted_population_forecast, prepare_car_emissions_dataset],
)
def predict_cars_mileage(variables):
    target_year = variables['target_year']
    mileage_adj = variables['cars_mileage_per_resident_adjustment']

    df = prepare_car_emissions_dataset()
    df = df.loc[df.Vehicle == 'Cars', ['Year', 'Road', 'Mileage', 'CO2e']].set_index('Year')
    df = df.pivot(columns='Road', values='Mileage')
    df.columns = df.columns.astype(str)
    df['Forecast'] = False
    last_historical_year = df.index.max()
    df = df.reindex(range(df.index.min(), target_year + 1))
    pop_df = get_adjusted_population_forecast()
    df['Population'] = pop_df['Population']
    df['UrbanPerResident'] = df['Urban'] / df['Population']
    df['HighwaysPerResident'] = df['Highways'] / df['Population']
    df.loc[df.Forecast.isna(), 'Forecast'] = True
    for road in ('Highways', 'Urban'):
        s = df[road + 'PerResident'].copy()
        target_per_resident = s.loc[last_historical_year] * (1 + (mileage_adj / 100))
        s.loc[target_year] = target_per_resident
        s = s.interpolate()
        df.loc[df.Forecast, road + 'PerResident'] = s
        df.loc[df.Forecast, road] = df[road + 'PerResident'] * df['Population']

    df['Mileage'] = df['Highways'] + df['Urban']
    df['PerResident'] = df['UrbanPerResident'] + df['HighwaysPerResident']
    df.Forecast = df.Forecast.astype(bool)

    return df


def estimate_mileage_ratios(df, last_hist_year, target_year, bev_target_share):
    # Assume BEV share is increasing according to the Bass diffusion model
    # and that increase in share comes equally out of petrol and diesel engines
    # starting from the most polluting engine classes.

    last_bev_share = df.loc['electric'].sum().sum()
    bev_series = generate_bass_diffusion(
        last_hist_year, target_year, last_bev_share, bev_target_share,
        p=0.03, q=0.6
    )

    diesel = df.loc['diesel'].copy()
    gas = df.loc['gasoline'].copy()
    last_diesel_share = diesel.sum().sum()
    last_gas_share = gas.sum().sum()
    diesel_per_gas = last_diesel_share / (last_gas_share + last_diesel_share)

    out = []

    for year in range(last_hist_year + 1, target_year + 1):
        bev_share = bev_series.loc[year]
        bev_share_change = bev_share - last_bev_share

        share_left = dict(diesel=bev_share_change * diesel_per_gas)
        share_left['gasoline'] = bev_share_change - share_left['diesel']

        shares_per_engine = dict(diesel=diesel, gasoline=gas)

        for i in range(0, 6 + 1):
            key = 'EURO %d' % i
            for eng in ('diesel', 'gasoline'):
                if not share_left[eng]:
                    continue

                val = shares_per_engine[eng][key]
                decrease = min(val, share_left[eng])
                shares_per_engine[eng][key] -= decrease
                share_left[eng] -= decrease

        shares_per_engine['electric'] = {'EURO 6': bev_share}
        for eng in ('diesel', 'gasoline', 'electric'):
            z = dict(shares_per_engine[eng])
            z['Year'] = year
            z['Engine'] = eng
            out.append(z)

        last_bev_share = bev_share

    df['Year'] = last_hist_year
    df = df.reset_index().append(out)
    df = df.fillna(0).set_index(['Engine', 'Year'])
    df = df.unstack('Engine')
    df = df.fillna(method='ffill')
    df = df.stack('Engine')

    return df


def estimate_bev_unit_emissions(unit_emissions, kwh_emissions):
    energy_consumption = dict(
        Highways=0.2,
        Urban=0.17
    )  # kWh/km

    df = pd.DataFrame(kwh_emissions)
    df['Highways'] = df['EmissionFactor'] * energy_consumption['Highways']
    df['Urban'] = df['EmissionFactor'] * energy_consumption['Urban']
    df.index.name = 'Year'
    df = df.drop(columns='EmissionFactor').reset_index().melt(id_vars='Year')
    df = df.rename(columns=dict(variable='Road', value='EURO 6'))
    df['Engine'] = 'electric'
    df = df.set_index(['Road', 'Engine'])

    df = unit_emissions.append(df, sort=True)
    df = df.reset_index().set_index(['Year', 'Road', 'Engine'])
    df = df.unstack(['Road', 'Engine']).fillna(method='pad')

    return df


def calculate_co2e_per_engine_type(mileage, ratios, unit_emissions):
    df = ratios.unstack('Engine')
    df_h = df.multiply(mileage['Highways'], axis='index')
    df_r = df.multiply(mileage['Urban'], axis='index')
    df_h['Road'] = 'Highways'
    df_r['Road'] = 'Urban'

    df = df_h.append(df_r).reset_index().set_index(['Year', 'Road']).unstack('Road')
    df.columns = df.columns.reorder_levels([0, 2, 1])

    df = df * unit_emissions
    df = df.stack('Road')

    df = (df.sum(axis=1) / 1000000000).unstack('Road')
    last_hist_year = mileage[~mileage.Forecast].index.max()
    df = df.loc[df.index > last_hist_year]
    mileage.loc[mileage.index > last_hist_year, 'HighwaysEmissions'] = df['Highways']
    mileage.loc[mileage.index > last_hist_year, 'UrbanEmissions'] = df['Urban']

    return mileage


@calcfunc(
    datasets=dict(
        mileage_per_engine_type='jyrjola/lipasto/mileage_per_engine_type',
        car_unit_emissions='jyrjola/lipasto/car_unit_emissions',
    ),
    variables=[
        'target_year', 'municipality_name',
        'cars_bev_percentage'
    ],
    funcs=[
        predict_electricity_emission_factor,
        predict_cars_mileage,
        prepare_car_emissions_dataset
    ]
)
def predict_cars_emissions(datasets, variables):
    target_year = variables['target_year']
    bev_percentage = variables['cars_bev_percentage']

    mileage_per_engine_type = datasets['mileage_per_engine_type']
    mileage_share_per_engine_type = mileage_per_engine_type.set_index(['Vehicle', 'Engine']).drop(columns='Sum')

    df = prepare_car_emissions_dataset()
    df = df.loc[df.Vehicle == 'Cars', ['Year', 'CO2e', 'Road']].set_index('Year')
    emissions_df = df.pivot(values='CO2e', columns='Road')

    df = predict_cars_mileage()
    for road in ('Highways', 'Urban'):
        df[road + 'Emissions'] = emissions_df[road] / 1000  # -> kt

    car_unit_emissions = datasets['car_unit_emissions'].set_index(['Engine', 'Road'])
    elec_df = predict_electricity_emission_factor()
    share_df = mileage_share_per_engine_type.copy().xs('Cars')

    last_hist_year = df[~df.Forecast].index.max()

    # Estimate mileage ratio shares between engine types
    share = estimate_mileage_ratios(share_df, last_hist_year, target_year, bev_percentage / 100.0)

    # Estimate emissions per km per engine type
    unit_df = car_unit_emissions.reset_index()
    unit_df = unit_df.groupby(['Road', 'Engine', 'Class']).mean()['CO2e'].unstack('Class')
    unit_df['Year'] = last_hist_year
    elec_df = elec_df.loc[elec_df.index >= last_hist_year]
    unit_df = estimate_bev_unit_emissions(unit_df, elec_df['EmissionFactor'])

    df = calculate_co2e_per_engine_type(df, share, unit_df)
    engine_shares = share.sum(axis=1).unstack('Engine')
    for engine_type in ('gasoline', 'diesel', 'electric'):
        df[engine_type] = engine_shares[engine_type]

    df['Emissions'] = (df['HighwaysEmissions'] + df['UrbanEmissions'])   # magic
    df.loc[df.Forecast, 'Emissions'] *= 0.97  # magic
    df['EmissionFactor'] = df['Emissions'] / (df['Urban'] + df['Highways']) * 1000000000  # g/km

    return df


if __name__ == '__main__':
    predict_cars_emissions()
