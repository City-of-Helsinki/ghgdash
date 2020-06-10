import pandas as pd
from calc import calcfunc
from calc.population import get_adjusted_population_forecast
from calc.transportation.datasets import prepare_transportation_emissions_dataset
from calc.transportation.parking import predict_parking_fee_impact


DATA_YEAR = 2015
PASSENGER_KMS = 4346323463
MODAL_SPLIT = {
    'Walking': 6.9,
    'Cycling': 4.6,
    'Train': 3.7,
    'Metro': 9.1,
    'Tram': 2.8,
    'Bus': 12.2,
    'Taxi': 0.8,
    'Car': 59.9,
}


@calcfunc(
    datasets=dict(
        modal_share='jyrjola/ymparistotilastot/l27_matka_kulkutapa_pks_2000_2008',
    ),
)
def prepare_daily_trips_dataset(datasets):
    df = datasets['modal_share']
    df = df[df['Alue'] == 'Koko Helsinki'].drop(columns='Alue')
    df['Vuosi'] = df['Vuosi'].astype(int)
    df = df.rename(columns=dict(Muuttuja='Variable'))
    df['Variable'] = df.Variable.map({'Määrä (matkaa)': 'Trips'})
    df = df[df['Variable'] == 'Trips'].drop(columns='Variable')
    df = df.rename(columns=dict(value='Trips', Vuosi='Year', Kulkutapa='Mode'))

    MODE_MAP = {
        'Kävely': 'Walking',
        'Polkupyörä': 'Cycling',
        'Linja-auto': 'Bus',
        'Raitiovaunu': 'Tram',
        'Juna': 'Train',
        'Metro': 'Metro',
        'Taksi': 'Taxi',
        'Henk. Auto kulj.': 'Car_Driver',
        'Henk. Auto matk.': 'Car_Passenger',
        'Muu, mikä?': 'Other',
        'Eos': 'N/A',
        'Yht': 'Total',
    }

    df['Mode'] = df['Mode'].map(MODE_MAP)
    df = df[df['Year'] > 2008]
    df = df[df['Mode'] != 'Total']
    df['Trips'] = df['Trips'].astype(int)

    df = df.set_index(['Year', 'Mode'])
    df = df.unstack('Mode')
    df.columns = df.columns.levels[1]

    # Plug in data fro 2019
    DATA_2019 = {
        'Kävely': 690016,
        'Polkupyörä': 167306,
        'Linja-auto': 222807,
        'Metro': 145541,
        'Raitiovaunu': 99995,
        'Juna': 57397,
        'Henk. Auto kulj.': 298738,
        'Henk. Auto matk.': 77435,
        'Taksi': 14463,
        'Muu, mikä?': 11394,
    }
    d = {}
    for key, val in DATA_2019.items():
        d[MODE_MAP[key]] = val
    df.loc[2019] = d

    df['Car'] = df['Car_Driver'] + df['Car_Passenger']

    df = df.drop(columns=['Car_Driver', 'Car_Passenger'])

    return df


@calcfunc(
    funcs=[
        prepare_daily_trips_dataset, get_adjusted_population_forecast, predict_parking_fee_impact
    ],
    variables=['target_year'],
)
def predict_passenger_kms(variables):
    df = prepare_daily_trips_dataset()

    s = df.loc[DATA_YEAR]
    m = {key: val * PASSENGER_KMS / 1000 for key, val in MODAL_SPLIT.items()}
    passenger_kms_per_daily_trip = pd.Series(m).div(s).fillna(0)

    df *= passenger_kms_per_daily_trip

    first_hist_year = df.index.min()
    pop = get_adjusted_population_forecast()
    df['Population'] = pop['Population']
    hist_pop = df.pop('Population')

    total = df.sum(axis=1)

    kms_per_resident = total.iloc[-1] / hist_pop.iloc[-1]

    mdf = df.div(total, axis=0)

    last_hist_year = mdf.index.max()
    shares = mdf.loc[last_hist_year].to_dict()  # from last historical year

    pdf = predict_parking_fee_impact(skip_cache=True)

    TO_MODES = ['Cycling', 'Metro', 'Train', 'Tram']

    for year in range(last_hist_year + 1, variables['target_year'] + 1):
        prev = shares['Car']
        shares['Car'] *= pdf.loc[year]['CarMultiplier']
        change_per_mode = (prev - shares['Car']) / len(TO_MODES)
        for mode in TO_MODES:
            shares[mode] += change_per_mode
        mdf.loc[year] = shares

    mdf['Forecast'] = True
    mdf.loc[mdf.index <= last_hist_year, 'Forecast'] = False

    mdf['Population'] = pop['Population']

    mdf['Trips'] = total
    mdf.loc[mdf.Forecast, 'Trips'] = kms_per_resident * mdf['Population']

    fc = mdf.pop('Forecast')
    pop = mdf.pop('Population')
    total = mdf.pop('Trips')

    mdf = mdf.mul(total, axis=0).astype(int)
    mdf['KmsPerResident'] = total / pop
    mdf['Forecast'] = fc
    return mdf


@calcfunc(
    funcs=[predict_passenger_kms, prepare_transportation_emissions_dataset]
)
def predict_road_mileage():
    edf = prepare_transportation_emissions_dataset()[['Year', 'Vehicle', 'Road', 'Mileage']]
    edf = edf.set_index('Year')

    MODE_VEHICLE_MAP = (
        ('Bus', 'Buses'),
        ('Car', 'Cars'),
    )

    df = predict_passenger_kms()

    vehicle_km_per_passenger_km = {}

    for mode, vehicle in MODE_VEHICLE_MAP:
        mdf = edf[edf.Vehicle == vehicle][['Road', 'Mileage']]
        mdf['Trips'] = df[mode]
        mdf = mdf.dropna()
        mdf['KmPerTrip'] = mdf['Mileage'] / mdf['Trips']

        # out = mdf.groupby('Road')['KmPerTrip'].mean().dropna().to_dict()
        out = mdf[mdf.index == mdf.index.max()].set_index('Road')['KmPerTrip'].to_dict()
        vehicle_km_per_passenger_km[vehicle] = out

    last_hist_year = edf.index.max()
    edf = edf.reset_index().set_index(['Year', 'Vehicle', 'Road']).unstack(['Vehicle', 'Road'])
    edf.columns = edf.columns.droplevel()

    edf = edf.reindex(range(edf.index.min(), df.index.max() + 1))

    for mode, vehicle in MODE_VEHICLE_MAP:
        for road_type, per_trip in vehicle_km_per_passenger_km[vehicle].items():
            out = df.loc[df.index > last_hist_year, mode] * per_trip
            edf.loc[edf.index > last_hist_year, (vehicle, road_type)] = out

    edf.columns = edf.columns.to_list()

    edf['Forecast'] = False
    edf.loc[edf.index > last_hist_year, 'Forecast'] = True

    return edf


if __name__ == '__main__':
    pd.set_option('display.max_rows', None)
    df = predict_road_mileage(skip_cache=True)
    df.pop('Forecast')
    print(df / 1000000)
